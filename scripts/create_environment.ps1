param (
    [Parameter(Mandatory = $true)] [string] $cluster,
    [Parameter(Mandatory = $true)] [string] $namespace,
    [string] $environment = "${cluster}_${namespace}"
)

# figure out some paths
$project_path = Split-Path $PSScriptRoot -Parent
$encrypted_admin_config = Join-Path $project_path -ChildPath "clusters" | Join-Path -ChildPath "${cluster}_admin.enc.yaml"

# decrypt the kubernetes cluster admin config and write to temp file for usage
$admin_config = (New-TemporaryFile).FullName
try {
    sops -d $encrypted_admin_config | Out-File -FilePath $admin_config

    # ensure the namespace exists
    @"
apiVersion: v1
kind: Namespace
metadata:
    name: ${namespace}
    labels:
        name: ${namespace}
"@ | kubectl apply --kubeconfig $admin_config -f -
} finally {
    Remove-Item $admin_config
}

# create the environment folder
$environment_path = Join-Path $project_path -ChildPath "environments" | Join-Path -ChildPath $environment
if (-not (Test-Path -Path $environment_path -PathType Container)) {
    # Create the directory if it does not exist
    New-Item -ItemType Directory -Path $environment_path
}

# create public_keys folder
$public_key_path = Join-Path $environment_path -ChildPath "public_keys"
if (-not (Test-Path -Path $public_key_path -PathType Container)) {
    # Create the directory if it does not exist
    New-Item -ItemType Directory -Path $public_key_path
}

# create secrets folder
$secrets_path = Join-Path $environment_path -ChildPath "secrets"
if (-not (Test-Path -Path $secrets_path -PathType Container)) {
    # Create the directory if it does not exist
    New-Item -ItemType Directory -Path $secrets_path
}

# create values folder
$values_path = Join-Path $environment_path -ChildPath "values"
if (-not (Test-Path -Path $values_path -PathType Container)) {
    # Create the directory if it does not exist
    New-Item -ItemType Directory -Path $values_path
}

# write .sops.yaml
$sopsYaml_path = Join-Path $environment_path -ChildPath ".sops.yaml"
@"
creation_rules:
- pgp: null
  path_regex: '\.enc\.yaml$'
"@ | Out-File -FilePath $sopsYaml_path