#!/usr/bin/env bash

environment=$1
age_secret_key=$2

restore_sops_vars() {
    export SOPS_AGE_KEY=$SOPS_AGE_KEY_BACKUP
    unset SOPS_AGE_KEY_BACKUP
}

if test -z ${age_secret_key}
then
    echo "Age secret key for secret decryption is not set. Assuming a private gpg key is available."
else
    echo "Preparing specified age secret key ..."
    export SOPS_AGE_KEY_BACKUP=$SOPS_AGE_KEY
    export SOPS_AGE_KEY=$age_secret_key

    # Ensure we reset the original environment variables after script exits...
    trap 'restore_sops_vars' RETURN
fi

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