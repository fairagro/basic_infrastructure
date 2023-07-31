param (
    [Parameter(Mandatory = $true)] [string] $cluster,
    [Parameter(Mandatory = $true)] [string] $namespace,
    [string] $environment= "${cluster}_${namespace}",
    [string] $kubectl_version = "1.24.15",
    [string] $helm_version = "3.12.1",
    [string] $sops_version = "3.7.3",
    [string] $binary_path = "$env:USERPROFILE\local",
    [string] $user_kubeconfig = "$env:USERPROFILE\.k8s_config\${cluster}_${namespace}.yaml"
)

# This script needs to be dot-sourced to be effective. So check this
if (-not ($MyInvocation.InvocationName -eq '.' -or $MyInvocation.Line -eq '')) {
    throw "This script is intended to be dot-sourced. Exiting..."
}

# figure out some paths
$project_path = Split-Path $PSScriptRoot -Parent
$environments_path = Join-Path $project_path "environments"
$environment_path = Join-Path $environments_path -ChildPath $environment

# Check that the context is actually known
if (-not (Test-Path -Path $environment_path -PathType Container)) {
    throw "The environement directory for cluster ${cluster}, namespace ${namespace} does not exist. Exiting..."
}

# set KUBECONFIG environment variable to the actual cluster config file
$env:KUBECONFIG = $user_kubeconfig

# make the desired kubectl and helm versions available in terms of the commands 'kubectl' and 'helm'
$kubectl_binary_path = Join-Path $binary_path -ChildPath "kubectl-v${kubectl_version}.exe"
$helm_binary_path = Join-Path $binary_path -ChildPath "helm-v${helm_version}.exe"
$sops_binary_path = Join-Path $binary_path -ChildPath "sops-v${sops_version}.exe"
$helmfile_binary_path = Join-Path $binary_path -ChildPath "helmfile.exe"
Set-Alias -Name kubectl -Value $kubectl_binary_path
Set-Alias -Name helm -Value $helm_binary_path
Set-Alias -Name sops -Value $sops_binary_path
Set-Alias -Name helmfile -Value $helmfile_binary_path
$env:HELM_SECRETS_SOPS_PATH = $sops_binary_path
$env:HELM_SECRETS_HELM_PATH = $helm_binary_path

# set helmfile environment
$env:HELMFILE_ENV = $environment
$env:HELMFILE_HELM_PATH = $helm_binary_path

# import all public keyfiles into gpg keyring so sops can find them
$public_key_path = Join-Path $environment_path -ChildPath "public_keys"
Get-ChildItem -File -Path $public_key_path -Filter "*.asc" | ForEach-Object { gpg --import $_.FullName }

# Create Powershell autocompletion for kubectl and helm
kubectl completion powershell | Out-String | Invoke-Expression
helm completion powershell | Out-String | Invoke-Expression
helmfile completion powershell | Out-String | Invoke-Expression

# Set default namespace
kubectl config use-context $environment