"""
A backup script for Nextcloud, running in docker.
"""

import logging
from kubernetes import client, config
from kubernetes.client import api
from kubernetes.stream import stream

# Usage example
NAMESPACE = "fairagro-nexctloud"
DEPLOYMENT_NAME = "fairagro-nextcloud"
CONTAINER_NAME = "nextcloud"
COMMAND = ["/var/www/html/occ", "maintenance:mode", "--on"]


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
        config.load_incluster_config()
    except config.config_exception.ConfigException:
        # Load out-of-cluster configuration from KUBECONFIG
        config.load_kube_config()

    # Create a Kubernetes API client configuration and enable debug output
    configuration = client.Configuration()
    configuration.debug = True

    api_client = client.ApiClient(configuration=configuration)
    core_api = client.CoreV1Api(api_client)
    apps_api = api.AppsV1Api(api_client)

    # Find desired deployment
    deployment = apps_api.read_namespaced_deployment(
        DEPLOYMENT_NAME, NAMESPACE)

    # Get any pod associated with the deployment
    pods = core_api.list_namespaced_pod(NAMESPACE, label_selector=f"app={
                                        deployment.metadata.labels['app']}")
    pod = any(pods.items)

    # Execute the command in the container
    exec_command = ["/bin/sh", "-c"] + COMMAND
    resp = stream(core_api.connect_get_namespaced_pod_exec,
                  pod.metadata.name,
                  NAMESPACE,
                  command=exec_command,
                  stderr=True,
                  stdin=False,
                  stdout=True,
                  tty=False,
                  _preload_content=False)

    while resp.is_open():
        resp.update(timeout=1)
        if resp.peek_stdout():
            print(f"STDOUT: {resp.read_stdout()}")
        if resp.peek_stderr():
            print(f"STDERR: {resp.read_stderr()}")
        else:
            break

    # resp.write_stdin("date\n")
    # sdate = resp.readline_stdout(timeout=3)
    # print(f"Server date command returns: {sdate}")
    # resp.write_stdin("whoami\n")
    # user = resp.readline_stdout(timeout=3)
    # print(f"Server user is: {user}")
    resp.close()


if __name__ == '__main__':
    main()
