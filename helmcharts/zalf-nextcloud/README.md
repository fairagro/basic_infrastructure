## On backup ##

Currently we are only able to perform a manual backup.

All backup steps are peformed on one of the cluster nodes.

### basic preparations ###

All subsequent steps -- for preparation, back and restore -- are to be performed on a kuberentes cluster node
with `root` permissions. E.g.:

```bash
ssh ansible@10.10.84.64
sudo -i
```

### Software installations ###

We need some tools to perform backup and restore. These are `argocd`, `velero` and the PostgreSQL command line
tools.

#### Install `argocd` command line tool on a kuberentes cluster node ####

```bash
curl -sSL -o argocd-linux-amd64 https://github.com/argoproj/argo-cd/releases/latest/download/argocd-linux-amd64
install -m 555 argocd-linux-amd64 /usr/local/bin/argocd
rm -rf argocd-linux-amd64
```

#### Install `velero` command line tool on a kubernetes cluster node ####

1. Go to `https://github.com/vmware-tanzu/velero/releases/latest` and copy the URL of
   the desired distribution -- e.g. `velero-v1.15.0-linux-amd64.tar.gz`.
2. Login on cluster node, download and unpack:

   ```bash
   velero_url=https://github.com/vmware-tanzu/velero/releases/download/v1.15.0/velero-v1.15.0-linux-amd64.tar.gz
   curl -s -L $velero_url | tar xzv
   mv velero-v1.15.0-linux-amd64/velero /usr/local/bin
   rm -rf velero-v1.15.0-linux-amd64
   ```

#### Install PostgreSQL (including the command line tools) ####

```bash
dnf install -y https://download.postgresql.org/pub/repos/yum/reporpms/EL-9-x86_64/pgdg-redhat-repo-latest.noarch.rpm
dnf install postgresql15
```

### Creating the backup ###

The procedur to create a nextcloud backup is:

1. Preparations
2. Enter nextcloud maintenance mode
3. Backup nextcloud storage
4. Backup nextcloud database
5. Leave nextcloud maintenance mode

#### Preparations ####

##### Setup bash completion #####

These steps are useful to perform for each session:

```bash
PATH=$PATH:/usr/local/bin
source <(kubectl completion bash)
source <(velero completion bash)
```

##### Find pods to interact with #####

Find the pods we need to interact with:

```bash
nextcloud=$(kubectl get pods \
    -n fairagro-nextcloud \
    -l app.kubernetes.io/name=nextcloud \
    -o jsonpath='{.items[0].metadata.name}')
postgres=$(kubectl get pods \
    -n fairagro-nextcloud \
    -l cluster-name=fairagro-postgresql-nextcloud \
    -l spilo-role=master \
    -o jsonpath='{.items[0].metadata.name}')
```

##### Find database credentials #####

```bash
PGHOST=$(kubectl get services -n fairagro-nextcloud --template={{.spec.clusterIP}} fairagro-postgresql-nextcloud)
PGPASSWORD=$(kubectl get secrets \
    -n fairagro-nextcloud \
    --template={{.data.password}} \
    nextcloud.fairagro-postgresql-nextcloud.credentials.postgresql.acid.zalan.do \
    | base64 -d)
export PGPASSWORD
export PGHOST
export PGUSER=nextcloud
export PGDATA=nextcloud
```

#### Enter nextcloud maintenance mode ####

Now exec into it and enable maintenance mode:

```bash
kubectl exec -it -n fairagro-nextcloud $nextcloud -- /var/www/html/occ maintenance:mode --on
```

It's also a good idea to wait until the maintenance mode has become active:

```bash
timeout 300s bash -c \
'
url=https://nextcloud.fizz.dataservice.zalf.de
while ! curl -s -o /dev/null -w "%{http_code}" $url | grep -E "^5[0-9]{2}$"; do
  sleep 1
done
'
```

#### Backup nextcloud storage ####

In this step we make use of `velero` to backup the two nextcloud volumes (`nextcloud-nextcloud`
and `nextcloud-nextcloud-data`). Additionally we backup the PostgreSQL objects so we will have
a running database after restoring the backup. This will simplify the database restore a lot.
Note that we only backup the `PVCs` themnselves, without the actual backing storage. This done
by applying the `skip-postgres-volume-backup` `ConfigMap` as resource policy.

```bash
backup_name=fairagro-nextcloud-backup-$(date +"%Y%m%d-%H%M%S")
velero backup create $backup_name \
    --include-namespaces fairagro-nextcloud \
    --include-namespace-scoped-resources 'persistentvolumeclaims,postgresqls,secrets' \
    --resource-policies-configmap skip-postgres-volume-backup \
    --wait
```

#### Backup the PostgreSQL database ####

```bash
pg_dump -d nextcloud -Fc -f ${backup_name}.dump
```

#### Leave nextcloud maintenance mode ####

```bash
kubectl exec -it -n fairagro-nextcloud $nextcloud -- /var/www/html/occ maintenance:mode --off
```

### Restore the backup ###

To restore the backup, you have to start on a "green field". You cannot overwrite an existing
nextcloud and/or database instance.

The restore consists of these steps:

1. Prepare the environment
2. Restore the `velero` backup
3. Restore the PostgreSQL backup
4. Power up Nextcloud

#### Prepare the environment ####

The following steps assume that the namespace and user account created by the
ZALF [`misc`](https://github.com/zalf-rdm/misc) repo are already existing. So you will need to
run the script `kubernetes/cluster-create/05a_setup_argocd_project_permissions.sh` of that repo.
Please refer to the `misc` repo for more information.

Additionally we need to figure out the backup name to restore. E.g.:

```bash
velero backup get
backup_name=fairagro-nextcloud-backup-20241112-163525
```

#### Restore the `velero` backup ####

```bash
restore_name=${backup_name}-restored-$(date +"%Y%m%d-%H%M%S")
velero create restore $restore_name --from-backup=${backup_name} --wait
```

Now we delete everything from the restored backup that we do not need.
This is the OnlyOffice database and some secrets

```bash
kubectl delete postgresqls.acid.zalan.do \
    -n fairagro-nextcloud \
    nextcloud-fairagro-onlyoffice-postgresql
kubectl delete secrets \
    -n fairagro-nextcloud \
    nextcloud \
    nextcloud-fairagro-onlyoffice-jwt-secret \
    nextcloud-redis \
    nextcloud-tls-secret
```

#### Restore the PostgreSQL database ####

It may take a while until the `PostgreSQL` operator has setup the database.
Please wait for the 'status' to be 'Running':

```bash
kubectl wait \
    --for=jsonpath='{.status.PostgresClusterStatus}'=Running \
    --timeout=300s \
    --namespace=fairagro-nextcloud \
    postgresqls.acid.zalan.do fairagro-postgresql-nextcloud
```

Now we need to establish the credentials for the running nextcloud database.
Please refer to [the corresponding backup section](#find-database-credentials).

To actually restore the database:

```bash
pg_restore -C -d nextcloud ${backup_name}.dump
```

#### Synchronize argocd ####

As the velero restore has only restored a tiny fraction of all needed kubernetes
objects, we need to perform an argocd sync. Currently this needs to be done
manually, as otherwise we needed to deal with argocd login credentials on the
command line.

#### Finalize Nextcloud ####

Nextcloud should come up after a while, but some final steps are missing. Please
log into the nextcloud container:

```bash
nextcloud=$(kubectl get pods \
    -n fairagro-nextcloud \
    -l app.kubernetes.io/name=nextcloud \
    -o jsonpath='{.items[0].metadata.name}')
kubectl exec -it -n fairagro-nextcloud -c nextcloud $nextcloud -- /var/www/html/occ maintenance:mode --off
timeout 300s bash -c \
'
url=https://nextcloud.fizz.dataservice.zalf.de
while ! curl -s -o /dev/null -w "%{http_code}" $url | grep -E "^(2|3)[0-9]{2}$"; do
  sleep 1
done
'
kubectl exec -it -n fairagro-nextcloud -c nextcloud $nextcloud -- /var/www/html/occ maintenance:data-fingerprint
```
