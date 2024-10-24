"""
A backup script for Nextcloud, running in docker.
"""

import logging
from datetime import datetime, timezone

from jsonpickle import encode as json_encode
from kubernetes import client
from kubernetes.client import api
from kubernetes.watch import Watch

from util.kubernetes import (
    change_nextcloud_maintenance_mode,
    get_nextcloud_deployment,
    get_nextcloud_pod,
    load_kubeconf,
    wait_nextcloud_maintenance_mode_to_change,
    NEXTCLOUD_DEPLOYMENT_NAME,
    NEXTCLOUD_NAMESPACE,
    VELERO_PHASES_ERROR,
    VELERO_PHASES_SUCCESS
)


NEXTCLOUD_POSTGRESQL_NAME = "fairagro-postgresql-nextcloud"
VELERO_BACKUP_STORAGE_LOCATION = "default"
VELERO_BACKUP_TIME_TO_LIVE = "87600h0m0s"
VELERO_BACKUP_TIMEOUT = 300
POSTGRESQL_RESTART_TIMEOUT = 300

logger = logging.getLogger(__name__)


def main() -> None:
    """
    Perform a Nextcloud backup.

    This function configures logging, loads Kubernetes configuration,
    creates necessary API clients, and performs the backup process for Nextcloud.
    """
    # Set the logging level to DEBUG
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(module)s %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    load_kubeconf()

    # Create a Kubernetes API client configuration
    api_client: client.ApiClient = client.ApiClient()
    # enable debug output
    # api_client.configuration.debug = True
    logger.debug("ApiClient configuration: %s",
                 json_encode(api_client.configuration.__dict__))

    logger.info("About to instantiate the needed Kubernetes APIs...")
    core_api: client.CoreV1Api = client.CoreV1Api(api_client)
    apps_api: api.AppsV1Api = api.AppsV1Api(api_client)
    custom_api: client.CustomObjectsApi = client.CustomObjectsApi(api_client)

    deployment: client.V1Deployment = get_nextcloud_deployment(apps_api)
    nextcloud_pod: client.V1Pod = get_nextcloud_pod(core_api, deployment)
    change_nextcloud_maintenance_mode(core_api, nextcloud_pod, "on")
    wait_nextcloud_maintenance_mode_to_change("on")
    backup_time: datetime = datetime.now(timezone.utc)
    patch_postgresql_object_with_restore_timestamp(custom_api, backup_time)
    create_velero_backup(custom_api, backup_time)
    change_nextcloud_maintenance_mode(core_api, nextcloud_pod, "off")

    logger.info("Backup finished")


def create_velero_backup(custom_api: client.CustomObjectsApi, backup_time: datetime) -> None:
    """
    Create a velero backup for the Nextcloud deployment.

    Parameters:
    custom_api (client.CustomObjectsApi): The Kubernetes custom objects API client.
    backup_time (datetime): The time the backup was taken.

    This function creates a velero backup for the specified Nextcloud deployment
    and waits for it to complete.

    Returns:
        None
    """
    logger.info("About to create velero backup...")
    backup_name = f'{NEXTCLOUD_NAMESPACE}-{NEXTCLOUD_DEPLOYMENT_NAME}-{
        backup_time.strftime("%Y-%m-%dt%H-%M-%S")}'
    backup_object = {
        "apiVersion": "velero.io/v1",
        "kind": "Backup",
        "metadata": {
            "labels": {
                "velero.io/storage-location": VELERO_BACKUP_STORAGE_LOCATION
            },
            "name": backup_name,
            "namespace": "velero"
        },
        "spec": {
            "csiSnapshotTimeout": "10m0s",
            "defaultVolumesToFsBackup": False,
            "includedNamespaces": [NEXTCLOUD_NAMESPACE],
            "includedResources": ["*"],
            "labelSelector": {
                "matchExpressions": [
                    {
                        "key": "batch.kubernetes.io/job-name",
                        "operator": "DoesNotExist"
                    }
                ],
            },
            "itemOperationTimeout": "4h0m0s",
            "resourcePolicy": {
                "kind": "configmap",
                "name": "skip-postgres-volume-backup"
            },
            "snapshotMoveData": True,
            "storageLocation": VELERO_BACKUP_STORAGE_LOCATION,
            "ttl": VELERO_BACKUP_TIME_TO_LIVE
        }
    }
    custom_api.create_namespaced_custom_object(
        group="velero.io",
        version="v1",
        namespace="velero",
        plural="backups",
        body=backup_object
    )

    # Wait for backup to complete
    logger.info("Waiting for velero backup to be finished...")
    w = Watch()
    for backup in w.stream(
        custom_api.list_namespaced_custom_object,
        group="velero.io",
        version="v1",
        namespace="velero",
        plural="backups",
        timeout_seconds=VELERO_BACKUP_TIMEOUT
    ):
        if backup['object'].get('metadata', {}).get('name') == backup_name:
            backup_phase = backup['object'].get('status', {}).get('phase')
            if backup_phase in VELERO_PHASES_SUCCESS:
                logger.info("Backup complete")
                w.stop()
            if backup_phase in VELERO_PHASES_ERROR:
                logger.error("Backup failed with phase %s", backup_phase)
                w.stop()


def patch_postgresql_object_with_restore_timestamp(
        custom_api: client.CustomObjectsApi,
        backup_time: datetime
) -> None:
    """
    Patches the nextcloud postgres object with the correct restore timestamp.

    This function writes the restore timestamp into the PostgreSQL object. This
    triggers a PostgreSQL cluster restart, including a failover and a new backup.
    The function waits for that to finish.

    Parameters:
    custom_api (client.CustomObjectsApi): The Kubernetes CustomObjectsApi instance.
    backup_time (datetime): The datetime object representing the time of the last backup.

    Returns:
    None
    """
    logger.info(
        "About to patch the nextcloud postgres object with the correct restore timestamp...")
    postgres_patch = {
        "spec": {
            "clone": {
                "cluster": NEXTCLOUD_POSTGRESQL_NAME,
                "timestamp": backup_time.strftime("%Y-%m-%dT%H:%M:%S%:z")}
        }
    }
    custom_api.patch_namespaced_custom_object(
        group="acid.zalan.do",
        version="v1",
        namespace=NEXTCLOUD_NAMESPACE,
        plural="postgresqls",
        name=NEXTCLOUD_POSTGRESQL_NAME,
        body=postgres_patch
    )

    # Patching the PostgreSQL object triggers a PostgreSQL cluster restart, including a
    # failover and a new backup. Wait for that to finish.
    logger.info("Waiting for PostgreSQL cluster restart to be finished...")
    w = Watch()
    for postgres in w.stream(
        custom_api.list_namespaced_custom_object,
        group="acid.zalan.do",
        version="v1",
        namespace=NEXTCLOUD_NAMESPACE,
        plural="postgresqls",
        timeout_seconds=POSTGRESQL_RESTART_TIMEOUT
    ):
        if postgres['object'].get('metadata', {}).get('name') == NEXTCLOUD_POSTGRESQL_NAME and \
                postgres['object'].get('status', {}).get('PostgresClusterStatus') == "Running":
            w.stop()


if __name__ == '__main__':
    main()
