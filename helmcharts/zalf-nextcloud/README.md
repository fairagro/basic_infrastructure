# Infos on helmchart `zalf-nextcloud` #

## Nextcloud backup and recovery ##

### On the backup process ###

The nextcloud backup relies on `velero` as main backup tool and on the `spilo` (aka Zalando PostgreSQL flavor)
integrated point-in-time backup.

`velero` will create backups of (nearly) all kubernetes objects that can be
found within the namespace `fairagro-nextcloud`. When it encounters a `PersistentVolume`, it will leverages
its `kopia` plugin to also backup the volume content. It is configured to skip `PersistentVolume`s that belong
to PostgreSQL databases, though. This is because `spilo` features its own backup procedure that cannot easily
be integrated with `velero`. The `spilo` backup procedure relies on PostgreSQL
base backups and additional WAL file backups (performed by the integrated tool `walg`) that enable
point-in-time-recovery.

All this is tied together with the `nextcloud-backup` script that is part of this repository. It is wriiten in
python and consumes the kuberentes API. It is distributed as docker image that gets deployed as kubernetes
`CronJob` that in turn will run once per night. It performs the following steps:

1. Enter nextcloud maintenace mode, so there are no database modifications during backup
2. Patch the kubernetes `postgresql` object of the nextcloud database to set the restore timestamp to the current
   backup time. During recovery this will tell `spilo` to create a point-in-time database recovery with the
   correct time.
3. Perform `velero` backup. This will backup all files stored within nextcloud.
4. Leave nextcloud maintenace mode.

### On the recovery process ###

Recovery will never replace existing kubernetes objects. So before recovery, the whole namespace
`fairagro-nextcloud` need to be deleted, if it already exists.

Disregard `argocd` completely during recovery process, it can be synced after everything is in place again. Please
be aware that in the current state of this project it is dangerous to have `argocd` auto-sync enabled for the
nextcloud app. This is because an unintentional restore triggered by `argocd` might render the backup unusable.

To trigger the restore there will be the `restore.py` script within in `nextcloud-backup` container. But for now
this script does still not exist, so we describe a manual restore here:

1. find the most recent `velero` backup:

   ```bash
   velero get backup
   ```

2. restore that backup:

   ```bash
   velero create restore restore-01 --from-backup=<backup name>
   ```

3. observe the restore process:

   ```bash
   velero describe restore restore-01
   velero logs restore restore-01
   ```

This will cause `velero` to restore all kubernetes objects from the backup, including the `PersistentVolume`
content of non-PostgreSQL volumes (i.e. all files hosted inside nextcloud). It will skip all PostgreSQL `Pods`
and `PersistentVolumes` but only restore the `PostgreSQL` object itself. This will then recreate all needed
resources and automatically recover the database content. The recovery timestamp is already included
in the `PostgreSQL` object (refer to bullet point 2 in the backup section).

### Backup/Recovery caveats ###

#### Start a new nextcloud instance from scratch ####

That means, you do not recover an existing backup, but do a fresh new nextcloud setup. In this case there is
no recovery timestamp included in the `PostgreSQL` object, so recovery in fact should be disabled. But `spilo`
will fail to initialize the database if it finds an existing backup in the backup storage. So you have to
delete it first.

#### Never recover a backup more than once ####

A PostgreSQL database backup consists of two parts: the base backup and the WAL files. There can be several
backup timelines in parallel -- i.e. several base backups with their corresponding WAL files. When spilo
performs the database recovery, it will always choose the newest base backup. When recovery is finished, it
will automatically create a new base backup. So a second recovery attempt will fail, because the desired
timestamp is not reachable from the newest base backup (point-in-time recovery can only go forward in time
from the chosen base backup).

There should be a solution for this: it is possible to set the backup timeline for restore by specifying the
environment variable `CLONE_TARGET_TIMELINE`. The timeline to choose can be queried by calling `wal-g` within
the database container:

```bash
su - postgres
envdir "/run/etc/wal-e.d/env" wal-g wal-show --detailed-json | jq '. | max_by(.id) | .id'
```

This needs to be done within the `PostgreSQL` object when also setting the recovery time.

#### Failing database and creation of new timeline during backup ####

This is just an information to prevent from confusion.

During backup you can observe that both database instances will terminate and restart. This is triggered by a
patch of the kubernetes PostgreSQL object. Restart of the primary database instance will trigger a failover.
This will implicitely create a new PostgreSQL timeline and cause a new basebackup of the new timetime once the
PostgreSQL cluster is restarted. It is yet unclear if this has any implications (except a waste of storage, CPU
and network resources because of the additional backup). During restore the original timelinewill be restored.

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
