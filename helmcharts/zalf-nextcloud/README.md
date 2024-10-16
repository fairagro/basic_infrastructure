# Infos on helmchart `zalf-nextcloud` #

## Some useful shell commands ##

### To trigger the nextcloud backup CronJob ###

e.g. for testing puposes:

```bash
kubectl create job backup-test -n fairagro-nextcloud --from=cronjob/nextcloud-backup-cronjob
```

### To create a test backup container and execute a shell within ###

This pod will run for 10 minutes, then it will change to state 'completed' and needs to be deleted:

```bash
kubectl apply -n fairagro-nextcloud -f helmcharts/zalf-nextcloud/tests/backup-pod-with-shell.yaml
kubectl exec -it -n fairagro-nextcloud temporary-nextcloud-backup-pod -- sh
```

To debug the service account token (should be `nextcloud-backup-account`):

```bash
kubectl exec -it -n fairagro-nextcloud temporary-nextcloud-backup-pod \
    -- cat /var/run/secrets/kubernetes.io/serviceaccount/token \
    | jq -R '.' \
    | jq 'split(".")|{header: .[0]|@base64d|fromjson, payload: .[1]|@base64d|fromjson}'
```

Note that `jq` is executed inside the pod. If it's not installed, consider using a local `jq` installation.

### To debug a failed backup ###

#### Check the cronjob pod logs ####

```bash
kubectl logs -n fairagro-nextcloud -l batch.kubernetes.io/job-name=backup-test
```

#### Check the backup state ####

First find your new backup:

```bash
velero backup get
```

Now investigate it:

```bash
velero backup describe <backup-name>
kubectl describe backups.velero.io -n fairagro-nextcloud <backup-name>
```

#### Investigate the backup logs ####

```bash
velero backup logs <backup-name>
```
