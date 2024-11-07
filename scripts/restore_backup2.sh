#!/usr/bin/env bash

# figure out some paths
mydir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)

backup=$1

namespace=fairagro-nextcloud
image=zalf/fairagro_nextcloud_backup-3.12@sha256:b7cc08729055f2fc1d6d3537c9d0bf5198b4855f02575dc1eceabed4fc5cef03

# create a service account and permissions 
yaml_definition_file="${mydir}/../helmcharts/zalf-nextcloud/templates/rbac.yaml"
sed -e "s/{{ .Release.Namespace }}/${namespace}/g" $yaml_definition_file | kubectl apply -f -

# current_context=$(kubectl config current-context)
# account=$(kubectl config view -o json | jq -r ".contexts[] | select(.name == \"$current_context\") | .context.user")
timestamp=$(date +"%Y%m%d-%H%M%S")

kubectl run restore-${timestamp} --image=$image -n $namespace --overrides='{ "spec": { "serviceAccount": "nextcloud-backup-account" }  }' -- python /nextcloud-backup/restore.py -b $backup