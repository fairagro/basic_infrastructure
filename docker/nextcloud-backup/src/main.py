"""
A backup script for Nextcloud, running in docker.
"""

import logging
# import subprocess
from kubernetes import client, config
from kubernetes.client import api
from kubernetes.stream import stream

# Usage example
NAMESPACE = "fairagro-nextcloud"
DEPLOYMENT_NAME = "fairagro-nextcloud"
CONTAINER_NAME = "nextcloud"
SERVICE_ACCOUNT = "nextcloud-backup-account"
COMMAND = ["/var/www/html/occ", "maintenance:mode", "--on"]

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

    # kslogger = logging.getLogger('kubernetes')
    # console_h = logging.StreamHandler()
    # kslogger.addHandler(console_h)
    # kslogger.setLevel(logging.DEBUG)

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

    # Create a Kubernetes API client configuration and enable debug output
    api_client = client.ApiClient()
    api_client.configuration.debug = True

    # In case we're not running in a pod, the api_key is not set and has to be created
    # by issuing token request to the authentication API.
    # Therefore we assume that we have the required permissions.
    if not api_client.configuration.api_key:
        logger.info("No API key found, creating one")
        core_api = client.CoreV1Api(api_client)
        body = client.AuthenticationV1TokenRequest(
            spec=client.V1TokenRequestSpec(audiences=[""])
        )
        token = core_api.create_namespaced_service_account_token(
            SERVICE_ACCOUNT, NAMESPACE, body)
        # command = ["kubectl", "create", "token", "-n", NAMESPACE, SERVICE_ACCOUNT]
        # token = subprocess.check_output(command).decode("utf-8")
        api_client.configuration.api_key['authorization'] = token.status.token
        api_client.configuration.api_key_prefix['authorization'] = 'Bearer'
        api_client.configuration.key_file = None
        api_client.configuration.cert_file = None

    core_api = client.CoreV1Api(api_client)
    apps_api = api.AppsV1Api(api_client)

    # Find desired deployment
    deployment = apps_api.read_namespaced_deployment(
        DEPLOYMENT_NAME, NAMESPACE)

    # Get any pod associated with the deployment
    pods = core_api.list_namespaced_pod(NAMESPACE, label_selector=f"app.kubernetes.io/name={
                                        deployment.metadata.labels['app.kubernetes.io/name']}")
    pod = pods.items[0]

    # Execute the command in the container
    resp = stream(core_api.connect_get_namespaced_pod_exec,
                  pod.metadata.name,
                  NAMESPACE,
                  container=CONTAINER_NAME,
                  command=COMMAND,
                  stderr=True,
                  stdin=False,
                  stdout=True,
                  tty=False)

    print(resp)

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
