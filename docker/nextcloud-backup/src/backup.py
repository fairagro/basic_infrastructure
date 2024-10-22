"""
A backup script for Nextcloud, running in docker.
"""

import logging
from datetime import datetime, timezone
from jsonpickle import encode as json_encode
# import subprocess
from kubernetes import client, config
from kubernetes.client import api
from kubernetes.stream import stream
from kubernetes.watch import Watch

# Usage example
NEXTCLOUD_NAMESPACE = "fairagro-nextcloud"
NEXTCLOUD_DEPLOYMENT_NAME = "nextcloud"
NEXTCLOUD_CONTAINER_NAME = "nextcloud"
NEXTCLOUD_MAINTENANCE_COMMAND = ["/var/www/html/occ", "maintenance:mode"]
NEXTCLOUD_POSTGRESQL_NAME = "fairagro-postgresql-nextcloud"
POSTGRESQL_TIMELINE_COMMAND = ["pg_controldata"]
VELERO_BACKUP_STORAGE_LOCATION = "default"
VELERO_BACKUP_TIME_TO_LIVE = "87600h0m0s"
VELERO_PHASES_SUCCESS = ["Completed"]
VELERO_PHASES_ERROR = ["FailedValidation",
                       "PartiallyFailed", "Failed", "Deleting"]
VELERO_BACKUP_TIMEOUT = 300

logger = logging.getLogger(__name__)


def main():
    """
    Perform a nextcloud backup.
    """

    # Exceptions known to be raised:
    # * kubernetes.client.exceptions.ApiException
    # * kubernetes.config.config_exception.ConfigException

    # Set the logging level to DEBUG
    logging.basicConfig(level=logging.DEBUG)

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

    # Create a Kubernetes API client configuration and enable debug output
    api_client = client.ApiClient()
    # api_client.configuration.debug = True
    logger.debug("ApiClient configuration: %s",
                 json_encode(api_client.configuration.__dict__))

    logger.info("About to instantiate the needed Kubernetes APIs...")
    core_api = client.CoreV1Api(api_client)
    apps_api = api.AppsV1Api(api_client)
    custom_api = client.CustomObjectsApi(api_client)

    # Find desired deployment
    logger.info("About to find the desired deployment...")
    deployment = apps_api.read_namespaced_deployment(
        NEXTCLOUD_DEPLOYMENT_NAME, NEXTCLOUD_NAMESPACE)

    # Get any pod associated with the PostgreSQL service
    logger.info("About to get the pods associated with the deployment...")
    pods = core_api.list_namespaced_pod(
        NEXTCLOUD_NAMESPACE,
        label_selector=f"app.kubernetes.io/name={
            deployment.metadata.labels['app.kubernetes.io/name']}")
    nextcloud_pod = pods.items[0]

    # Enter nextcloud mainenance mode
    logger.info("About to enter nextcloud maintenance mode..")
    resp = stream(core_api.connect_get_namespaced_pod_exec,
                  nextcloud_pod.metadata.name,
                  NEXTCLOUD_NAMESPACE,
                  container=NEXTCLOUD_CONTAINER_NAME,
                  command=NEXTCLOUD_MAINTENANCE_COMMAND + ["--on"],
                  stderr=True,
                  stdin=False,
                  stdout=True,
                  tty=False)

    # Get any pod associated with the deployment
    logger.info("About to get the pods associated with PostgreSQL...")
    pods = core_api.list_namespaced_pod(
        NEXTCLOUD_NAMESPACE,
        label_selector=f"cluster-name={NEXTCLOUD_POSTGRESQL_NAME}")
    postgres_pod = pods.items[0]

    # Query current PostgreSQL backup timeline
    logger.info("About to query most recent PostgreSQL backup timeline...")
    resp = stream(core_api.connect_get_namespaced_pod_exec,
                  postgres_pod.metadata.name,
                  NEXTCLOUD_NAMESPACE,
                  command=POSTGRESQL_TIMELINE_COMMAND,
                  stderr=True,
                  stdin=False,
                  stdout=True,
                  tty=False)
    timeline_id = 0
    for line in resp.splitlines():
        if line.startswith("Latest checkpoint's TimeLineID"):
            timeline_id = line.split(":")[1].strip()
    if timeline_id == 0:
        raise ValueError("Could not find latest PostgreSQL backup timeline")

    # Query current PostgreSQL object
    logger.info("About to query currebt PostgreSQL object...")
    postgres = custom_api.get_namespaced_custom_object(
        group="acid.zalan.do",
        version="v1",
        namespace=NEXTCLOUD_NAMESPACE,
        plural="postgresqls",
        name=NEXTCLOUD_POSTGRESQL_NAME)

    backup_time = datetime.now(timezone.utc)

    # Update postgres object with the correct restore timestamp
    # (Note: this timestamp will be stored in the velero backup and then applied by zalanda spilo
    # after the velero backup has been restored)
    logger.info(
        "About to patch the nextcloud postgres object with the correct restore timestamp...")
    # add or replace env var 'CLONE_TARGET_TIMELINE'
    env_vars = [v for v in postgres["spec"]["env"] if v["name"] != "CLONE_TARGET_TIMELINE"] + [{
        "name": "CLONE_TARGET_TIMELINE",
        "value": timeline_id
    }]
    postgres_patch = {
        "spec": {
            "env": env_vars,
            "clone": {
                "cluster": NEXTCLOUD_POSTGRESQL_NAME,
                "timestamp": backup_time.strftime("%Y-%m-%dT%H:%M:%S%:z")}
        }
    }
    # Actually we would like to ptach the PostgreSQL object using the merge strategy, because this
    # would reduce the need to query the object and raeading out the env vars before patching it.
    # But it results in an error. Maybe kubernetes-python does not support this?
    # postgres_patch = [
    #     {
    #         "op": "add",
    #         "path": "/spec/clone",
    #         "value": {
    #             "cluster": NEXTCLOUD_POSTGRESQL_NAME,
    #             "timestamp": backup_time.strftime("%Y-%m-%dT%H:%M:%S%:z")
    #         }
    #     },
    #     {
    #         "op": "add",
    #         "path": "/spec/env/-",
    #         "value": {
    #             "name": "CLONE_TARGET_TIMELINE",
    #             "value": timeline_id
    #         }
    #     }
    # ]
    resp = custom_api.patch_namespaced_custom_object(
        group="acid.zalan.do",
        version="v1",
        namespace=NEXTCLOUD_NAMESPACE,
        plural="postgresqls",
        name=NEXTCLOUD_POSTGRESQL_NAME,
        body=postgres_patch
    )

    # Create velero backup
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
                    # omit Pods that where created from backup jobs
                    {
                        "key": "batch.kubernetes.io/job-name",
                        "operator": "DoesNotExist"
                    }
                    # omit Pods and StatefulSets that belong to PostgreSQL databases
                    # unfortunetly this also includes posgtres Secrets which definitively must
                    # be backed up
                    # {
                    #     "key": "application",
                    #     "operator": "NotIn",
                    #     "values": ["spilo"]
                    # }
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
    resp = custom_api.create_namespaced_custom_object(
        group="velero.io",
        version="v1",
        namespace="velero",
        plural="backups",
        body=backup_object
    )

    # Wait for backup to complete
    logger.info("Waiting for velero backup to be finished...")
    backup_success = False
    w = Watch()
    for backup in w.stream(
        custom_api.list_namespaced_custom_object,
        group="velero.io",
        version="v1",
        namespace="velero",
        plural="backups",
        timeout_seconds=VELERO_BACKUP_TIMEOUT
    ):
        logger.debug("backup watcher: %s", json_encode(backup))
        if backup['object']['metadata']['name'] == backup_name:
            backup_phase = backup['object'].get('status', {}).get('phase')
            if backup_phase in VELERO_PHASES_SUCCESS:
                backup_success = True
                logger.info("Backup complete")
                w.stop()
            if backup_phase in VELERO_PHASES_ERROR:
                logger.error("Backup failed with phase %s", backup_phase)
                w.stop()

    # Leave nextcloud mainenance mode
    logger.info("About to leave nextcloud maintenance mode...")
    resp = stream(core_api.connect_get_namespaced_pod_exec,
                  nextcloud_pod.metadata.name,
                  NEXTCLOUD_NAMESPACE,
                  container=NEXTCLOUD_CONTAINER_NAME,
                  command=NEXTCLOUD_MAINTENANCE_COMMAND + ["--off"],
                  stderr=True,
                  stdin=False,
                  stdout=True,
                  tty=False)

    logger.info("Backup finished")


if __name__ == '__main__':
    main()
