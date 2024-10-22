(return 0 2>/dev/null) && sourced=1 || sourced=0
if [ $sourced -eq 0 ]; then
  echo "ERROR, this script is meant to be sourced."
  exit 1
fi

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

# Check that the context is actually known
if [ ! -d "$environment_path" ]; then
    echo "The environment directory for environment $environment does not exist. Exiting..."
    exit 1
fi

if [ "$environment" = "local_dev" ]; then
    # do special stuff for minicube
    echo "There is no implementation for a local cluster environment for Linux yet. Exiting..."
    exit 1
else
    # set KUBECONFIG environment variable to the actual cluster config file
    kubeconfig=$(mktemp)
    sops -d "${environment_path}/credentials/project_admin.enc.yaml" > "$kubeconfig"
    export KUBECONFIG="$kubeconfig"
fi

# set some environment variables for helm secrets and helmfile
export HELM_SECRETS_SOPS_PATH=$(which sops)
export HELM_SECRETS_HELM_PATH=$(which helm)
export HELMFILE_ENV="$environment"
export HELMFILE_HELM_PATH=$(which helm)

# import all public keyfiles into gpg keyring so sops can find them
public_key_path="$environment_path/public_gpg_keys"
for file in "$public_key_path"/*.asc; do
    gpg --import "$file"
done

# Create Bash autocompletion for installed tools
source /etc/bash_completion
source <(kubectl completion bash)
source <(helm completion bash)
source <(helmfile completion bash)
source <(argocd completion bash)
source <(velero completion bash)
source <(docker completion bash)

# Setup aliases
alias k=kubectl
alias d=docker

# Set bash completion for aliases
complete -o default -F __start_kubectl k
complete -o default -F __start_docker d

# Set default namespace
#kubectl config use-context $environment