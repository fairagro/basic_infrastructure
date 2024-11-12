#!/usr/bin/env bash

# figure out some paths
mydir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)

backup=$1

namespace=fairagro-nextcloud
image=zalf/fairagro_nextcloud_backup-3.12@sha256:c10742096f9a3a3cfe97bb51af2537a1ce3f3c1abf6eecc0981be0ca23c437c9

# create a service account and permissions 
yaml_definition_file="${mydir}/../helmcharts/zalf-nextcloud/templates/rbac.yaml"
sed -e "s/{{ .Release.Namespace }}/${namespace}/g" $yaml_definition_file | kubectl apply -f -

timestamp=$(date +"%Y%m%d-%H%M%S")

kubectl run restore-${timestamp} \
  --image=$image \
  --namespace $namespace \
  --restart=Never \
  --overrides='{ "spec": { "serviceAccount": "nextcloud-backup-account" }  }' \
  -- python /nextcloud-backup/restore.py -b $backup