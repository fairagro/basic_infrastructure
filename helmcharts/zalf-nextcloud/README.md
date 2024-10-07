# To trigger the CronJob #

e.g. for testing puposes:

```bash
kubectl create job backup-test -n fairagro-nextcloud --from=cronjob/nextcloud-backup-cronjob
```
