#!/usr/bin/env bash

# figure out some paths
mydir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)

backup=$1

namespace=fairagro-nextcloud
image=zalf/fairagro_nextcloud_backup-3.12@sha256:344ee00ee643e0aa4e32ad6c987e63ed475d8d23fc1efeedce5b3dfa7a68efbc

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