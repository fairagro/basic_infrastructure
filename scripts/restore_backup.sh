#!/usr/bin/env bash

backup=$1

namespace=fairagro-nextcloud
image=zalf/fairagro_nextcloud_backup-3.12@sha256:b7cc08729055f2fc1d6d3537c9d0bf5198b4855f02575dc1eceabed4fc5cef03

# create a service account and permissions 
sa=nextcloud-backup-account
kubectl create serviceaccount $sa -n $namespace
kubectl create role nextcloud-backup-role-1 \
  --namespace $namespace \
  --verb=get,list,create \
  --resource=pods,deployments
kubectl create role nextcloud-backup-role-2 \
  --namespace $namespace \
  --resource=postgresqls \
  --verb=get,list,patch,watch
kubectl create rolebinding nextcloud-backup-rolebinding-1 \
  --namespace $namespace \
  --role=nextcloud-backup-role-1 \
  --serviceaccount=$namespace:$sa
kubectl create rolebinding nextcloud-backup-rolebinding-2 \
  --namespace $namespace \
  --role=nextcloud-backup-role-2 \
  --serviceaccount=namespace:$sa
kubectl create clusterrolebinding fairagro-nextcloud-velero-clusterrolebinding \
  --clusterrole=velero-clusterrole \
  --serviceaccount=$namespace:$sa
account=system:serviceaccount:$namespace:$sa

# current_context=$(kubectl config current-context)
# account=$(kubectl config view -o json | jq -r ".contexts[] | select(.name == \"$current_context\") | .context.user")
timestamp=$(date +"%Y%m%d-%H%M%S")

kubectl run restore-${timestamp} --image=$image --as=$account -n $namespace -- python /nextcloud-backup/restore.py -b $backup