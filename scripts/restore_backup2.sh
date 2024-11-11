#!/usr/bin/env bash

# figure out some paths
mydir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)

backup=$1

namespace=fairagro-nextcloud
image=zalf/fairagro_nextcloud_backup-3.12@sha256:7f0df06ae7f6c87194ffe2b299ef303dd21b0214f7f2b1a556e8f3476245c864

# create a service account and permissions 
yaml_definition_file="${mydir}/../helmcharts/zalf-nextcloud/templates/rbac.yaml"
sed -e "s/{{ .Release.Namespace }}/${namespace}/g" $yaml_definition_file | kubectl apply -f -

# current_context=$(kubectl config current-context)
# account=$(kubectl config view -o json | jq -r ".contexts[] | select(.name == \"$current_context\") | .context.user")
timestamp=$(date +"%Y%m%d-%H%M%S")

kubectl run restore-${timestamp} \
  --image=$image \
  --namespace $namespace \
  --restart=Never \
  --overrides='{ "spec": { "serviceAccount": "nextcloud-backup-account" }  }' \
  -- python /nextcloud-backup/restore.py -b $backup