from kubernetes import client, config
from kubernetes.stream import stream

# Usage example
namespace = "fairagro-nexctloud"
deployment_name = "fairagro-nextcloud"
container_name = "nextcloud"
command = ["/var/www/html/occ", "maintenance:mode", "--on"]

def main():
    config.load_incluster_config()

    api_client = client.CoreV1Api()

    # Find desired deployment
    deployment = api_client.read_namespaced_deployment(deployment_name, namespace)

    # Get any pod associated with the deployment
    pods = api_client.list_namespaced_pod(namespace, label_selector=f"app={deployment.metadata.labels['app']}")
    pod = any(pods.items)

    # Execute the command in the container
    exec_command = ["/bin/sh", "-c"] + command
    resp = stream(api_client.connect_get_namespaced_pod_exec,
                  pod.metadata.name,
                  namespace,
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