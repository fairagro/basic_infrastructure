from kubernetes import client, config
from kubernetes.stream import stream

# Usage example
NAMESPACE = "test-ns"
POD_NAME = "test-pod"
SERVICE_ACCOUNT = "test-sa"
COMMAND = ["ls"]

def main():
    
    config.load_kube_config()

    # read $KUBECONFIG and instantiate core_api
    api_client = config.new_client_from_config()
    core_api = client.CoreV1Api(api_client)

    resp = stream(core_api.connect_get_namespaced_pod_exec,
                  POD_NAME,
                  NAMESPACE,
                  command=COMMAND,
                  stderr=True,
                  stdin=False,
                  stdout=True,
                  tty=False)
    print(resp.output)

    # impersonate a service account
    body = client.AuthenticationV1TokenRequest(
        spec=client.V1TokenRequestSpec(audiences=[""])
    )
    token = core_api.create_namespaced_service_account_token(SERVICE_ACCOUNT, NAMESPACE, body)
    api_client.configuration.api_key['authorization'] = token
    api_client.configuration.api_key_prefix['authorization'] = 'Bearer'
    api_client.configuration.key_file = None
    api_client.configuration.cert_file = None

    # re-instantiate core_api
    core_api = client.CoreV1Api(api_client)

    # No exception 
    core_api.list_namespaced_pod()

    # This triggers an exception, even though the corresponding kubectl call works:
    # kubectl exec -it -n test-ns test-pod --as system:serviceaccount:test-ns:test-sa -- ls
    #
    # kubernetes.client.exceptions.ApiException: (0)
    # Reason: Handshake status 401 Unauthorized
    # -+-+- 
    # {
    #   'audit-id': '760598c0-db3b-43b6-b9e0-0c18375d818b',
    #   'cache-control': 'no-cache, private',
    #   'content-type': 'application/json',
    #   'date': 'Wed, 09 Oct 2024 12:52:07 GMT',
    #   'content-length': '129'
    # }
    # -+-+-
    # b'{
    #   "kind":"Status",
    #   "apiVersion":"v1",
    #   "metadata":{},
    #   "status":"Failure",
    #   "message":"Unauthorized",
    #   "reason":"Unauthorized",
    #   "code":401
    # }\n
    resp = stream(core_api.connect_get_namespaced_pod_exec,
                  POD_NAME,
                  NAMESPACE,
                  command=COMMAND,
                  stderr=True,
                  stdin=False,
                  stdout=True,
                  tty=False)

    print(resp.output)

if __name__ == '__main__':
    main()
