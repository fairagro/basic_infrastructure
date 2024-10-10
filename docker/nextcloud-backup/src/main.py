"""
A backup script for Nextcloud, running in docker.
"""

import logging
from datetime import datetime
import jsonpickle
# import subprocess
from kubernetes import client, config
from kubernetes.client import api
from kubernetes.stream import stream

# Usage example
NAMESPACE = "fairagro-nextcloud"
DEPLOYMENT_NAME = "fairagro-nextcloud"
CONTAINER_NAME = "nextcloud"
MAINTENANCE_COMMAND = ["/var/www/html/occ", "maintenance:mode", "--on"]
BACKUP_STORAGE_LOCATION = "default"
BACKUP_TIME_TO_LIVE = "87600h0m0s"

logger = logging.getLogger(__name__)


def main():
    """
    Connects to a container running in a pod and runs a command there.

    This is a simple example of how to use the kubernetes python client to
    connect to a pod's container and run a command there. The command is
    executed in the default shell of the container.

    :raises: kubernetes.client.exceptions.ApiException
    """

    # Exceptions known to be raised:
    # * kubernetes.client.exceptions.ApiException
    # * kubernetes.config.config_exception.ConfigException

    # Set the logging level to DEBUG
    logging.basicConfig(level=logging.DEBUG)

    try:
        # Load in-cluster configuration when running in a pod
        logger.info("Trying to load in-cluster config")
        config.load_incluster_config()
    except config.config_exception.ConfigException as e:
        logger.info(
            "Could not load in-cluster config, trying to load $KUBECONFIG")
        logger.debug(e)
        # Load out-of-cluster configuration from KUBECONFIG
        config.load_kube_config()
        logger.info("Loaded out-of-cluster config from $KUBECONFIG. \
                    Note that we're not using the intended service account with \
                    its RBAC permissions, but the user from your $KUBECONFIG.")

    # Create a Kubernetes API client configuration and enable debug output
    api_client = client.ApiClient()
    # api_client.configuration.debug = True
    config_json = jsonpickle.encode(api_client.configuration.__dict__)
    logger.debug("ApiClient configuration: %s", config_json)

    core_api = client.CoreV1Api(api_client)
    apps_api = api.AppsV1Api(api_client)
    custom_api = client.CustomObjectsApi(api_client)

    # Find desired deployment
    deployment = apps_api.read_namespaced_deployment(
        DEPLOYMENT_NAME, NAMESPACE)

    # Get any pod associated with the deployment
    pods = core_api.list_namespaced_pod(NAMESPACE, label_selector=f"app.kubernetes.io/name={
                                        deployment.metadata.labels['app.kubernetes.io/name']}")
    pod = pods.items[0]

    backup_time = datetime.now()
    print(backup_time.isoformat())

    # Execute the command in the container
    resp = stream(core_api.connect_get_namespaced_pod_exec,
                  pod.metadata.name,
                  NAMESPACE,
                  container=CONTAINER_NAME,
                  command=MAINTENANCE_COMMAND,
                  stderr=True,
                  stdin=False,
                  stdout=True,
                  tty=False)

    backup_name=f'nextcloud-backup-{backup_time.strftime("%Y-%m-%dt%H-%M-%S")}'
    backup_object = {
        "apiVersion": "velero.io/v1",
        "kind": "Backup",
        "metadata": {
            "labels": {
                "velero.io/storage-location": BACKUP_STORAGE_LOCATION
            },
            "name": backup_name,
            "namespace": "velero"
        },
        "spec": {
            "csiSnapshotTimeout": "10m0s",
            "defaultVolumesToFsBackup": False,
            "includeClusterResources": True,
            "includedNamespaces": [NAMESPACE],
            "includedResources": ["*"],
            "itemOperationTimeout": "4h0m0s",
            "resourcePolicy": {
                "kind": "configmap",
                "name": "skip-postgres-volume-backup"
            },
            "snapshotMoveData": True,
            "storageLocation": BACKUP_STORAGE_LOCATION,
            "ttl": BACKUP_TIME_TO_LIVE
        }
    }

    resp = custom_api.create_namespaced_custom_object(
        group="velero.io",
        version="v1",
        namespace="velero",
        plural="backups",
        body=backup_object
    )


if __name__ == '__main__':
    main()
