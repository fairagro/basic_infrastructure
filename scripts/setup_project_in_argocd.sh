#!/usr/bin/env bash

environment=$1

# figure out some paths
mydir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
environment_path="$mydir/../environments/$environment"

# Login to argocd
sops exec-env "${environment_path}/credentials/argocd_secrets.enc.yaml" 'argocd login $ARGOCD_SERVER --insecure --grpc-web-root-path $ARGOCD_PREFIX --username=$ARGOCD_ADMIN_USER --password=$ARGOCD_ADMIN_PASSWORD'

# Install keycloak app
argocd app create keycloak \
    --repo "git@github.com:fairagro/basic_infrastructure.git" \
    --revision HEAD \
    --path "helmcharts/zalf-keycloak" \
    --dest-server "https://kubernetes.default.svc" \
    --project fairagro \
    --dest-namespace fairagro-keycloak \
    --values "../../environments/${environment}/values/zalf-keycloak.yaml" \
    --values "../../environments/${environment}/values/zalf-keycloak.enc.yaml"