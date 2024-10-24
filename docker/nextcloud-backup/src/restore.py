"""
A backup script for Nextcloud, running in docker.
"""

import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict

import requests
from jsonpickle import encode as json_encode
from kubernetes import client
from kubernetes.client import api
from kubernetes.watch import Watch

from util.kubernetes import (
    change_nextcloud_maintenance_mode,
    exec_command_in_nextcloud_container,
    get_nextcloud_deployment,
    get_nextcloud_pod,
    load_kubeconf,
    wait_nextcloud_maintenance_mode_to_change,
    NEXTCLOUD_URL,
    VELERO_PHASES_ERROR,
    VELERO_PHASES_SUCCESS
)


NEXTCLOUD_STATUS_URL = NEXTCLOUD_URL + "/status.php"
NEXTCLOUD_QUERY_STATUS_TIMEOUT = 10
NEXTCLOUD_CLIENT_SYNC_COMMAND = ["/var/www/html/occ", "maintenance:data-fingerprint"]
NEXTCLOUD_FILES_SCAN_COMMAND = ["/var/www/html/occ", "files:scan", "--all"]
VELERO_RESTORE_TIMEOUT = 300


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

    if check_nextcloud_is_running():
        logger.info("Nextcloud is already running. Exiting.")
        sys.exit(0)
    backup_name = get_newest_backup_name(custom_api)
    create_velero_restore(custom_api, backup_name)
    deployment: client.V1Deployment = get_nextcloud_deployment(apps_api)
    nextcloud_pod: client.V1Pod = get_nextcloud_pod(core_api, deployment)
    change_nextcloud_maintenance_mode(core_api, nextcloud_pod, "off")
    wait_nextcloud_maintenance_mode_to_change("off")
    exec_command_in_nextcloud_container(
        core_api, nextcloud_pod.metadata.name, NEXTCLOUD_FILES_SCAN_COMMAND
    )
    exec_command_in_nextcloud_container(
        core_api, nextcloud_pod.metadata.name, NEXTCLOUD_CLIENT_SYNC_COMMAND
    )

    logger.info("Restore finished")

def check_nextcloud_is_running() -> bool:
    """
    Check if Nextcloud is currently running.

    Checks the /status.php URL of the Nextcloud instance to see if it is currently running.

    Returns:
        bool: Whether Nextcloud is currently running.
    """
    logger.info("About to requery nextcloud status")
    try:
        resp = requests.get(NEXTCLOUD_STATUS_URL, timeout=NEXTCLOUD_QUERY_STATUS_TIMEOUT)
        status: Dict[str, Any] = resp.json()
        return status.get("installed", False)
    except requests.exceptions.RequestException:
        return False

def get_newest_backup_name(
    custom_api: client.CustomObjectsApi
) -> Dict[str, Any]:
    """Get the newest Velero backup.

    Args:
        custom_api (client.CustomObjectsApi): The Kubernetes custom objects API client.

    Returns:
        Dict: The newest Velero backup object.
    """
    backups = custom_api.list_namespaced_custom_object(
        group="velero.io",
        version="v1",
        namespace="velero",
        plural="backups")
    backup = max(backups["items"], key=lambda b: datetime.fromisoformat(b.get(
        "status", {}).get("completionTimestamp", datetime(2010, 1, 1).isoformat())))
    return backup["metadata"]["name"]

def create_velero_restore(
    custom_api: client.CustomObjectsApi,
    backup_name: str
) -> None:
    """Create a Velero restore.

    Args:
        custom_api (client.CustomObjectsApi): The Kubernetes custom objects API client.
        backup_name (str): The name of the Velero backup to restore.

    Returns:
        None
    """
    restore_time = datetime.now(timezone.utc)
    restore_name = f'{backup_name}-{restore_time.strftime("%Y%m%d%H%M%S")}'
    restore_object: Dict[str, Any] = {
        "apiVersion": "velero.io/v1",
        "kind": "Restore",
        "metadata": {
            "name": restore_name,
            "namespace": "velero"
        },
        "spec": {
            "backupName": backup_name,
            "excludedResources": [
                "nodes",
                "events",
                "events.events.k8s.io",
                "backups.velero.io,",
                "restores.velero.io",
                "resticrepositories.velero.io",
                "csinodes.storage.k8s.io",
                "volumeattachments.storage.k8s.io",
                "backuprepositories.velero.io"
            ],
            "hooks": {},
            "includedNamespaces": ["*"],
            "itemOperationTimeout": "4h0m0s",
            "uploaderConfig": {}
        }
    }
    custom_api.create_namespaced_custom_object(
        group="velero.io",
        version="v1",
        namespace="velero",
        plural="restores",
        body=restore_object
    )

    # Wait for restore to complete
    logger.info("Waiting for velero restore to be finished...")
    w = Watch()
    for restore in w.stream(
        custom_api.list_namespaced_custom_object,
        group="velero.io",
        version="v1",
        namespace="velero",
        plural="restores",
        timeout_seconds=VELERO_RESTORE_TIMEOUT
    ):
        if restore['object'].get('metadata', {}).get('name') == restore_name:
            restore_phase = restore['object'].get('status', {}).get('phase')
            if restore_phase in VELERO_PHASES_SUCCESS:
                logger.info("Restore complete")
                w.stop()
            if restore_phase in VELERO_PHASES_ERROR:
                logger.error("Restore failed with phase %s", restore_phase)
                w.stop()


if __name__ == '__main__':
    main()
