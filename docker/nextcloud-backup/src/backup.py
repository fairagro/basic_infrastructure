"""
A backup script for Nextcloud, running in docker.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Literal

import requests
from jsonpickle import encode as json_encode
from kubernetes import client, config
from kubernetes.client import api
from kubernetes.stream import stream
from kubernetes.watch import Watch

NEXTCLOUD_URL = "https://nextcloud.fizz.dataservice.zalf.de"
NEXTCLOUD_NAMESPACE = "fairagro-nextcloud"
NEXTCLOUD_DEPLOYMENT_NAME = "nextcloud"
NEXTCLOUD_CONTAINER_NAME = "nextcloud"
NEXTCLOUD_MAINTENANCE_COMMAND = ["/var/www/html/occ", "maintenance:mode"]
NEXTCLOUD_POSTGRESQL_NAME = "fairagro-postgresql-nextcloud"
NEXTCLOUD_WAIT_FOR_STATUS_ATTEMPTS = 600
NEXTCLOUD_WAIT_FOR_STATUS_INTERVAL = 1
NEXTCLOUD_WAIT_FOR_STATUS_TIMEOUT = 10
NEXTCLOUD_MAINTENANCE_HTTP_STATUS_CODE = {
    'on': 503,
    'off': 302
}
VELERO_BACKUP_STORAGE_LOCATION = "default"
VELERO_BACKUP_TIME_TO_LIVE = "87600h0m0s"
VELERO_PHASES_SUCCESS = ["Completed"]
VELERO_PHASES_ERROR = ["FailedValidation",
                       "PartiallyFailed", "Failed", "Deleting"]
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


def change_nextcloud_maintenance_mode(
        core_api: client.CoreV1Api,
        nextcloud_pod: client.V1Pod,
        on_off: Literal["on", "off"]
) -> None:
    """
    Change the Nextcloud maintenance mode.

    Parameters:
    core_api (CoreV1Api): The Kubernetes core API client.
    nextcloud_pod (V1Pod): The Nextcloud pod object.
    on_off (Literal["on", "off"]): The desired maintenance mode state.

    Returns:
        None

    This function executes a command in the Nextcloud pod to change its
    maintenance mode to the specified state using Kubernetes API.
    """
    logger.info("About to change nextcloud maintenance mode to '%s'...", on_off)
    valid_responses = {
        "on": [
            "Maintenance mode enabled\n",
            "Maintenance mode already enabled\n"
        ],
        "off": [
            "Maintenance mode disabled\n",
            "Maintenance mode already enabled\n"
        ]
    }
    command = NEXTCLOUD_MAINTENANCE_COMMAND + [f'--{on_off}']
    resp = stream(core_api.connect_get_namespaced_pod_exec,
                  nextcloud_pod.metadata.name,
                  NEXTCLOUD_NAMESPACE,
                  container=NEXTCLOUD_CONTAINER_NAME,
                  command=command,
                  stderr=True,
                  stdin=False,
                  stdout=True,
                  tty=False)
    if resp not in valid_responses[on_off]:
        raise RuntimeError(
            f"Unexpected response from nextcloud {command}: {resp}")


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


def wait_nextcloud_maintenance_mode_to_change(on_off: Literal["on", "off"]) -> None:
    """
    Waits for the nextcloud maintenance mode to change to the desired state.

    :param on_off: The desired state of the maintenance mode, either 'on' or 'off'.
    """
    logger.info(
        "About to wait for nextcloud maintenance mode to switch to '%s'...", on_off)
    attempts = 0
    while attempts < NEXTCLOUD_WAIT_FOR_STATUS_ATTEMPTS:
        resp = requests.get(
            NEXTCLOUD_URL, timeout=NEXTCLOUD_WAIT_FOR_STATUS_TIMEOUT)
        if resp.status_code == NEXTCLOUD_MAINTENANCE_HTTP_STATUS_CODE[on_off]:
            break
        attempts += 1
        time.sleep(NEXTCLOUD_WAIT_FOR_STATUS_INTERVAL)


def get_nextcloud_pod(core_api: client.CoreV1Api, deployment: client.V1Deployment) -> client.V1Pod:
    """
    Get a pod associated with a Nextcloud deployment.

    Parameters:
    core_api (CoreV1Api): The Kubernetes core API client.
    deployment (V1Deployment): The Nextcloud deployment object.

    Returns:
    V1Pod: A pod associated with the Nextcloud deployment.
    """
    logger.info("About to get the pods associated with the deployment...")
    pods = core_api.list_namespaced_pod(
        NEXTCLOUD_NAMESPACE,
        label_selector=f"app.kubernetes.io/name={
            deployment.metadata.labels['app.kubernetes.io/name']}")
    nextcloud_pod: client.V1Pod = pods.items[0]
    return nextcloud_pod


def get_nextcloud_deployment(apps_api: api.AppsV1Api) -> client.V1Deployment:
    """
    Get a Nextcloud deployment object.

    Parameters:
    apps_api (api.AppsV1Api): The Kubernetes apps API client.

    Returns:
    client.V1Deployment: The Nextcloud deployment object.
    """
    logger.info("About to find the nextcloud deployment...")
    return apps_api.read_namespaced_deployment(
        NEXTCLOUD_DEPLOYMENT_NAME, NEXTCLOUD_NAMESPACE)


def load_kubeconf() -> None:
    """
    Load the Kubernetes configuration.

    This function attempts to load the Kubernetes configuration for the
    environment in which it is running. If running inside a Kubernetes pod,
    it loads the in-cluster configuration. If that fails, it falls back to
    loading the configuration from the KUBECONFIG environment variable, 
    which is typically used for out-of-cluster configurations.

    The function logs the progress and any exceptions encountered during 
    the configuration loading process.

    Returns:
        None
    """
    try:
        # Load in-cluster configuration when running in a pod
        logger.info("About to load in-cluster config...")
        config.load_incluster_config()
        logger.info("Loaded in-cluster config")
    except config.config_exception.ConfigException as e:
        logger.info(
            "Could not load in-cluster config, trying to load $KUBECONFIG...")
        logger.debug(e)
        # Load out-of-cluster configuration from KUBECONFIG
        config.load_kube_config()
        logger.info("Loaded out-of-cluster config from $KUBECONFIG. \
                    Note that we're not using the intended service account with \
                    its RBAC permissions, but the user from your $KUBECONFIG.")


if __name__ == '__main__':
    main()
