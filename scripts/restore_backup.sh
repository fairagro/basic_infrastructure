#!/usr/bin/env bash

# figure out some paths
mydir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)

backup=$1

namespace=fairagro-nextcloud
image=zalf/fairagro_nextcloud_backup-3.12@sha256:aa09c19973d9229629aaeec6ec3204a5217e6f23da4343c6caab6854d7db7f72

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