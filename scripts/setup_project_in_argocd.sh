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

if [[ -f "${environment_path}/values/zalf-nextcloud.yaml" ]]; then
    # Install nextcloud app
    echo "Installing nextcloud app on ${environment}..."
    argocd app create fairagro-nextcloud \
        --upsert \
        --repo "git@github.com:fairagro/basic_infrastructure.git" \
        --revision HEAD \
        --path "helmcharts/zalf-nextcloud" \
        --dest-server "https://kubernetes.default.svc" \
        --project fairagro \
        --dest-namespace fairagro-nextcloud \
        --values "../../environments/${environment}/values/zalf-nextcloud.yaml" \
        --values "../../environments/${environment}/values/zalf-nextcloud.enc.yaml" \
        --sync-option CreateNamespace=true
fi

if [[ -f "${environment_path}/values/zalf-zammad.yaml" ]]; then
    # Install zammad app
    echo "Installing zammad app on ${environment}..."
    argocd app create fairagro-zammad \
        --upsert \
        --repo "git@github.com:fairagro/basic_infrastructure.git" \
        --revision HEAD \
        --path "helmcharts/zalf-zammad" \
        --dest-server "https://kubernetes.default.svc" \
        --project fairagro \
        --dest-namespace fairagro-zammad \
        --values "../../environments/${environment}/values/zalf-zammad.yaml" \
        --values "../../environments/${environment}/values/zalf-zammad.enc.yaml" \
        --sync-option CreateNamespace=true
fi

if [[ -f "${environment_path}/values/fairagro-datahub.yaml" ]]; then
    # Install datahub app
    echo "Installing datahub app on ${environment}..."
    argocd app create fairagro-datahub \
        --upsert \
        --repo "git@github.com:fairagro/basic_infrastructure.git" \
        --revision HEAD \
        --path "helmcharts/fairagro-datahub" \
        --dest-server "https://kubernetes.default.svc" \
        --project fairagro \
        --dest-namespace fairagro-datahub \
        --values "../../environments/${environment}/values/fairagro-datahub.yaml" \
        --values "../../environments/${environment}/values/fairagro-datahub.enc.yaml" \
        --sync-option CreateNamespace=true
fi

if [[ -f "${environment_path}/values/fairagro-survey.yaml" ]]; then
    # Install limesurvey app
    echo "Installing limesurvey app on ${environment}..."
    argocd app create fairagro-limesurvey \
        --upsert \
        --repo "git@github.com:fairagro/basic_infrastructure.git" \
        --revision HEAD \
        --path "helmcharts/fairagro-survey" \
        --dest-server "https://kubernetes.default.svc" \
        --project fairagro \
        --dest-namespace fairagro-survey \
        --values "../../environments/${environment}/values/fairagro-survey.yaml" \
        --values "../../environments/${environment}/values/fairagro-survey.enc.yaml" \
        --sync-option CreateNamespace=true
fi