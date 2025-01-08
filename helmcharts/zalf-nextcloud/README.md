# On this chart #

## On backup ##

Currently we are only able to perform a manual backup. The backup consists of two parts:

1. A backup on kuberentes level that consists of some essential kuberentes objects including the
   kubernetes volumes tha store the nextcloud user files. This backup is performed using the backup tool
   `velero`. It is wrtitten to S3 stoarge.
2. A backup of the nextcloud `PostgreSQL` databasebase. It is performed using the tool `pg_dump` and
   copied to S3 afterwards.

Note that we did not succeed to implement these two backup approaches:

* Leverage the automatic backup features of `spilo` (which is our `PostgreSQL` flavor) and link it to
  `velero` to create a fully automatic and continous backup solution.
* Use the nextcloud `backup` app which would simplify our current backup approach a lot. Unfortunately
  we encountered bugs in this app and had to recognize that it does not support the most recent nextcloud
  versions.

### prerquisites ###

We expect that there is a working `velero` setup in your kuberentes cluster as created by the ZALF
kuberentes repo [https://github.com/zalf-rdm/misc]. Also two S3 backup buckets are required:

1. The one used by `velero`, e.g. `fizz-velero`.
2. An additional bucket to copy database backups to, e.g. `fizz-nextcloud`.

### basic preparations ###

All subsequent steps - for preparation, backup and restore - are to be performed on a kuberentes cluster node
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

#### Install `s3cmd` ####

To copy PostgreSQL backups to S3, we need the tool `s3cmd`.
We will encrypt to data copied to S3, so we also need a (symmetric) encryption passphrase.
This is required when restoring the backup, so it should be entered into keepass.

1. We need S3 acceess credentials:

   ```bash
   S3_URL=http://10.10.84.134:9000
   S3_BUCKET_LOCATION=vmware
   S3_ACCESS_KEY=...
   S3_SECRET_KEY=...
   S3_GPG_PASSPHRASE=...
   ```

2. Now install and configure `s3cmd`:

    ```bash
    dnf install s3cmd
    cat > ~/.s3cfg << EOL
    access_key = ${S3_ACCESS_KEY}
    access_token =
    add_encoding_exts = 
    add_headers = 
    bucket_location = ${S3_BUCKET_LOCATION}
    ca_certs_file = 
    cache_file = 
    check_ssl_certificate = True
    check_ssl_hostname = True
    cloudfront_host = 
    connection_max_age = 5
    connection_pooling = True
    content_disposition = 
    content_type = 
    default_mime_type = binary/octet-stream
    delay_updates = False
    delete_after = False
    delete_after_fetch = False
    delete_removed = False
    dry_run = False
    enable_multipart = True
    encoding = UTF-8
    encrypt = True
    expiry_date = 
    expiry_days = 
    expiry_prefix = 
    follow_symlinks = False
    force = False
    get_continue = False
    gpg_command = /bin/gpg
    gpg_decrypt = %(gpg_command)s -d --verbose --no-use-agent --batch --yes --passphrase-fd %(passphrase_fd)s -o %(output_file)s %(input_file)s
    gpg_encrypt = %(gpg_command)s -c --verbose --no-use-agent --batch --yes --passphrase-fd %(passphrase_fd)s -o %(output_file)s %(input_file)s
    gpg_passphrase = ${S3_GPG_PASSPHRASE}
    guess_mime_type = True
    host_base = ${S3_URL}
    host_bucket = ${S3_URL}
    human_readable_sizes = False
    invalidate_default_index_on_cf = False
    invalidate_default_index_root_on_cf = True
    invalidate_on_cf = False
    keep_dirs = False
    kms_key = 
    limit = -1
    limitrate = 0
    list_allow_unordered = False
    list_md5 = False
    log_target_prefix = 
    long_listing = False
    max_delete = -1
    max_retries = 5
    mime_type = 
    multipart_chunk_size_mb = 15
    multipart_copy_chunk_size_mb = 1024
    multipart_max_chunks = 10000
    preserve_attrs = True
    progress_meter = True
    proxy_host = 
    proxy_port = 0
    public_url_use_https = False
    put_continue = False
    recursive = False
    recv_chunk = 65536
    reduced_redundancy = False
    requester_pays = False
    restore_days = 1
    restore_priority = Standard
    secret_key = ${S3_SECRET_KEY}
    send_chunk = 65536
    server_side_encryption = False
    signature_v2 = False
    signurl_use_https = False
    simpledb_host =
    skip_destination_validation = False
    skip_existing = False
    socket_timeout = 300
    ssl_client_cert_file = 
    ssl_client_key_file = 
    stats = False
    stop_on_error = False
    storage_class = 
    throttle_max = 100
    upload_id = 
    urlencoding_mode = normal
    use_http_expect = False
    use_https = False
    use_mime_magic = True
    verbosity = WARNING
    website_endpoint =
    website_error = 
    website_index = index.html
    EOL
    ```

Now an S3 bucket can be accessed using `s3cmd` using an URI like `s3://fizz-nextcloud`.

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
k8s_cluster=fizz
k8s_project=fairagro
k8s_app=nextcloud
k8s_namespace=${k8s_project}-${k8s_app}
```

##### Find pods to interact with #####

Find the pods we need to interact with:

```bash
nextcloud=$(kubectl get pods \
    -n $k8s_namespace \
    -l app.kubernetes.io/name=${k8s_app} \
    -o jsonpath='{.items[0].metadata.name}')
postgres=$(kubectl get pods \
    -n $k8s_namespace \
    -l cluster-name=fairagro-postgresql-nextcloud \
    -l spilo-role=master \
    -o jsonpath='{.items[0].metadata.name}')
```

##### Find database credentials #####

```bash
PGHOST=$(kubectl get services -n $k8s_namespace --template={{.spec.clusterIP}} fairagro-postgresql-nextcloud)
PGPASSWORD=$(kubectl get secrets \
    -n $k8s_namespace \
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
kubectl exec -it -n $k8s_namespace $nextcloud -- /var/www/html/occ maintenance:mode --on
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
Note that we only backup the `PVCs` themselves, without the actual backing storage. This done
by applying the `skip-postgres-volume-backup` `ConfigMap` as resource policy.

Note that we work with the so-called backup types `daily`, `weekly`, `monthly` and `yearly`.
They define the time (in number of hours) how long velero will keep a backup. Additionally they
determine the S3 bucket where the database backup is copied to. The idea behind this is that you
create these buckets with a lifecycle and retention policies that match the backup retention time
of velero, so no manual backup deletion is necessary.
These types are just a suggestion. Please feel free to define your own types.

```bash
backup_time=$(date +"%Y%m%d-%H%M%S")
backup_type=daily
case $backup_type in 
    "daily")
        backup_ttl=168h;;
    "weekly")
        backup_ttl=720h;;
    "monthly")
        backup_ttl=8760h;;
    "yearly")
        backup_ttl=87600h;;
    *)
        echo "unkown backup type: $backup_type!"
        false;;
esac \
&& backup_name=${k8s_project}-${k8s_app}-backup-${backup_type}-${backup_time} \
&& s3_bucket=${k8s_cluster}-${k8s_project}-${k8s_app}-backup-${backup_type} \
&& velero backup create $backup_name \
    --include-namespaces $k8s_namespace \
    --include-namespace-scoped-resources 'persistentvolumeclaims,postgresqls,secrets' \
    --resource-policies-configmap skip-postgres-volume-backup \
    --ttl ${backup_ttl} \
    --labels cluster=${k8s_cluster} \
    --labels project=${k8s_project} \
    --labels app=${k8s_app} \
    --labels database_backup_bucket=${s3_bucket} \
    --labels timestamp=${backup_time} \
    --labels type=${backup_type} \
    --wait
```

#### Backup the PostgreSQL database and move to S3 ####

To create the database dump and move it to S3:

```bash
pg_dump -d nextcloud -Fc -f ${backup_name}.dump
s3cmd put ${backup_name}.dump s3://${s3_bucket}
if [ $? -eq 0 ]; then
    rm -f ${backup_name}.dump
fi
```

#### Leave nextcloud maintenance mode ####

```bash
kubectl exec -it -n $k8s_namespace $nextcloud -- /var/www/html/occ maintenance:mode --off
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

Additionally we need to figure out the backup name to restore. You can either manually select the
backup:

```bash
velero backup get
backup_name=...
```

Or you can take the newest one:

```bash
backup_name=$(kubectl get backups.velero.io \
    --namespace velero \
    --sort-by=.metadata.creationTimestamp \
    -o custom-columns=:.metadata.name \
    | tail -1)
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
    -n $k8s_namespace \
    nextcloud-fairagro-onlyoffice-postgresql
kubectl delete secrets \
    -n $k8s_namespace \
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
    --namespace=${k8s_namespace} \
    postgresqls.acid.zalan.do fairagro-postgresql-nextcloud
```

Now we need to establish the credentials for the running nextcloud database.
Please refer to [the corresponding backup section](#find-database-credentials).

To actually restore the database:

```bash
s3_bucket=$(kubectl get backups.velero.io -n velero ${backup_name} -o jsonpath='{.metadata.labels.database_backup_bucket}')
s3cmd get --skip-existing s3://${s3_bucket}/${backup_name}.dump
pg_restore -c --if-exists -d nextcloud ${backup_name}.dump
if [ $? -eq 0 ]; then
    rm -f ${backup_name}.dump
fi
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
    -n $k8s_namespace \
    -l app.kubernetes.io/name=${k8s_app} \
    -o jsonpath='{.items[0].metadata.name}')
kubectl exec -it -n $k8s_namespace -c nextcloud $nextcloud -- /var/www/html/occ maintenance:mode --off
timeout 300s bash -c \
'
url=https://nextcloud.fizz.dataservice.zalf.de
while ! curl -s -o /dev/null -w "%{http_code}" $url | grep -E "^(2|3)[0-9]{2}$"; do
  sleep 1
done
'
kubectl exec -it -n $k8s_namespace -c nextcloud $nextcloud -- /var/www/html/occ maintenance:data-fingerprint
```
