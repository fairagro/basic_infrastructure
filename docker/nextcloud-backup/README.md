# On this imgae #

## To test the docker image locally ##

```powershell
docker run -d -p 5000:5000 --restart=always --name registry registry:2
docker build -t localhost:5000/nextcloud-backup .
docker push localhost:5000/nextcloud-backup
kubectl run nextcloud-backup --rm -it --image localhost:5000/nextcloud-backup -- python /nextcloud-backup/main.py
```

## How to create a service account token manually using `curl` from outside of kubernetes pod ##

```bash
$ yq e '.clusters[0].cluster.certificate-authority-data' $KUBECONFIG | base64 -d > ca.pem
$ yq e '.users[0].user.client-certificate-data' $KUBECONFIG | base64 -d > cert.pem
$ yq e '.users[0].user.client-key-data' $KUBECONFIG | base64 -d > key.pem
$ curl -v -X POST \
    https://10.10.84.64:6443/api/v1/namespaces/fairagro-nextcloud/serviceaccounts/nextcloud-backup-account/token \
    -H "User-Agent: kubectl/v1.28.6 (linux/amd64) kubernetes/be3af46" \
    -H "Accept: application/json, */*" \
    -H "Content-Type: application/json" \
    --cert cert.pem --key key.pem --cacert ca.pem \
    -d '
{
  "kind": "TokenRequest",
  "apiVersion": "authentication.k8s.io/v1",
  "metadata": {
    "creationTimestamp": null
  },
  "spec": {
    "audiences": null,
    "expirationSeconds": null,
    "boundObjectRef": null
  },
  "status": {
    "token": "",
    "expirationTimestamp": null
  }
}'
```

Obviously the kubernetes user is taken from the client cert fro the TLS connection.

## How to put nextcloud into maintenance mode using the kubernetes API ##

We use `kubectl` to obtain the token. Please refer to the previous section how to do it using `curl`.

```bash
$ jwt_token=$(kubectl create token -n fairagro-nextcloud nextcloud-backup-account)
$ curl -v -XPOST  \
    --cacert ca.pem \
    -H "X-Stream-Protocol-Version: v4.channel.k8s.io" \
    -H "X-Stream-Protocol-Version: v3.channel.k8s.io" \
    -H "X-Stream-Protocol-Version: v2.channel.k8s.io" \
    -H "X-Stream-Protocol-Version: channel.k8s.io" \
    -H "User-Agent: kubectl/v1.28.6 (linux/amd64) kubernetes/be3af46" \
    -H "Authorization: Bearer $jwt_token" \
    'https://10.10.84.64:6443/api/v1/namespaces/fairagro-nextcloud/pods/fairagro-nextcloud-7fbc75f9fc-mxbwt/exec?command=%2Fvar%2Fwww%2Fhtml%2Focc&command=maintenance%3Amode&command=--on&container=nextcloud&stdin=true&stdout=true&tty=true'
```
