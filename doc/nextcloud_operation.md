# Running occ commands #

Sometimes you need to run an occ command on the Nextcloud container directly. You can do that by running commands as the user www-data via the kubectl exec command.

```bash
kubectl exec $NEXTCLOUD_POD -- su -s /bin/sh www-data -c "php /var/www/html/occ myocccomand"
```