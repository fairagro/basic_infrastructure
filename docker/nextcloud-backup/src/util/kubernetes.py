"""
Shared functions for the backup and restore scripts.
"""

import logging
import time
from typing import List, Literal

import requests
from kubernetes import client, config
from kubernetes.stream import stream
from kubernetes.client import api
from kubernetes.watch import Watch


NEXTCLOUD_URL = "https://nextcloud.fizz.dataservice.zalf.de"
NEXTCLOUD_NAMESPACE = "fairagro-nextcloud"
NEXTCLOUD_CONTAINER_NAME = "nextcloud"
NEXTCLOUD_MAINTENANCE_COMMAND = ["/var/www/html/occ", "maintenance:mode"]
NEXTCLOUD_DEPLOYMENT_NAME = "nextcloud"
NEXTCLOUD_WAIT_FOR_STATUS_ATTEMPTS = 600
NEXTCLOUD_WAIT_FOR_STATUS_INTERVAL = 1
NEXTCLOUD_WAIT_FOR_STATUS_TIMEOUT = 10
NEXTCLOUD_MAINTENANCE_HTTP_STATUS_CODES = {
    'on': (500, 599),
    'off': (200, 399),
}
VELERO_PHASES_SUCCESS = ["Completed"]
VELERO_PHASES_ERROR = ["FailedValidation",
                       "PartiallyFailed", "Failed", "Deleting"]


logger = logging.getLogger(__name__)


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


def exec_command_in_nextcloud_container(
    core_api: client.CoreV1Api,
    pod_name: str,
    command: List[str],
    valid_responses: List[str] = None
) -> None:
    """
    Execute a command in a pod, using the kubernetes API.

    Parameters:
    core_api (CoreV1Api): The Kubernetes core API client.
    pod_name (str): The name of the pod.
    command (List[str]): The command to execute.
    valid_responses (List[str]): A list of valid responses from the command.

    Returns:
        None

    Raises:
        RuntimeError: If the response from the command is not in the valid_responses list.
    """
    resp = stream(core_api.connect_get_namespaced_pod_exec,
                  pod_name,
                  NEXTCLOUD_NAMESPACE,
                  container=NEXTCLOUD_CONTAINER_NAME,
                  command=command,
                  stderr=True,
                  stdin=False,
                  stdout=True,
                  tty=False)
    if valid_responses and resp not in valid_responses:
        raise RuntimeError(
            f"Unexpected response from nextcloud {command}: {resp}")


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
            "Maintenance mode already disabled\n"
        ]
    }
    command = NEXTCLOUD_MAINTENANCE_COMMAND + [f"--{on_off}"]
    exec_command_in_nextcloud_container(
        core_api, nextcloud_pod.metadata.name, command, valid_responses[on_off])


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
        codes = NEXTCLOUD_MAINTENANCE_HTTP_STATUS_CODES[on_off]
        if resp.status_code >= codes[0] and resp.status_code <= codes[1]:
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


def wait_for_container_to_be_running(
    core_api: client.CoreV1Api,
    pod_name: str,
    container_name: str
) -> None:
    """
    Wait for a specific container in a pod to be in the running state.

    Parameters:
    core_api (CoreV1Api): The Kubernetes core API client.
    pod_name (str): The name of the pod containing the container.
    container_name (str): The name of the container to check.

    This function uses a watch to continuously monitor the status of the specified
    container within the given pod until it is running.
    """
    logger.info("Waiting for container '%s' in pod '%s' to be running...",
                container_name, pod_name)
    w = Watch()
    # Stream updates for the pods in the specified namespace
    for pod in w.stream(
            core_api.list_namespaced_pod,
            namespace=NEXTCLOUD_NAMESPACE):
        # Check if the current pod is the one we're interested in
        if pod['object'].metadata.name == pod_name:
            # Iterate over the container statuses in the pod
            for container in pod['object'].status.container_statuses:
                # Check if the container is the one we're looking for and if it is running
                if container.name == container_name and \
                    container.state.running is not None:
                    # Stop the watch as the container is now running
                    w.stop()
