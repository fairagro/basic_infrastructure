#!/usr/bin/env bash

environment=$1

# figure out some paths
mydir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
environment_path="$mydir/../environments/$environment"

# Login to argocd
sops exec-env "${environment_path}/credentials/argocd_secrets.enc.yaml" 'argocd login $ARGOCD_SERVER --insecure --grpc-web-root-path $ARGOCD_PREFIX --username=$ARGOCD_ADMIN_USER --password=$ARGOCD_ADMIN_PASSWORD'

if [[ -f "${environment_path}/values/zalf-nextcloud.yaml" ]]; then
    # Install nextcloud app
    echo "Installing nextcloud app on ${environment}..."
    argocd app create fairagro-nextcloud \
        --upsert \
        --repo "git@github.com:fairagro/basic_infrastructure.git" \
        --revision HEAD \
        --path "helmcharts/fairagro-applications" \
        --dest-server "https://kubernetes.default.svc" \
        --project fairagro \
        --dest-namespace fairagro-applications \
        --values "../../environments/${environment}/values/fairagro-applications.yaml" \
        --sync-option CreateNamespace=true \
        --sync-option Prune=true
fi
