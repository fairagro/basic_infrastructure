param (
    [Parameter(Mandatory = $true)] [string] $environment,
    [string] $k8s_namespace = "fairagro",
    [string] $kubectl_version = "1.24.15",
    [string] $helm_version = "3.12.1",
    [string] $sops_version = "3.7.3",
    [string] $binary_path = "$env:USERPROFILE\local"
)

# This script needs to be dot-sourced to be effective. So check this
if (-not ($MyInvocation.InvocationName -eq '.' -or $MyInvocation.Line -eq '')) {
    throw "This script is intended to be dot-sourced. Exiting..."
}

# figure out some paths
$mypath = $MyInvocation.MyCommand.Path
$script_path = Split-Path $mypath -Parent
$cluster_path = Join-Path $script_path -ChildPath "environments" | Join-Path -ChildPath "${environment}"
$cluster_config_path = Join-Path $cluster_path  -ChildPath "cluster.yaml"

# Check that the environment is actually known
if (-not (Test-Path -Path $cluster_path -PathType Container)) {
    throw "The desired environment ${environment} does not exist. Exiting..."
}
if (-not (Test-Path -Path $cluster_config_path -PathType Leaf)) {
    throw "The k8s cluster config for environment ${environment} does not exist. Exiting..."
}

# set KUBECONFIG environment variable to the actual cluster config file
$env:KUBECONFIG = $cluster_config_path

# make the desired kubectl and helm versions available in terms of the commands 'kubectl' and 'helm'
$kubectl_binary_path = Join-Path $binary_path -ChildPath "kubectl-v${kubectl_version}.exe"
$helm_binary_path = Join-Path $binary_path -ChildPath "helm-v${helm_version}.exe"
$sops_binary_path = Join-Path $binary_path -ChildPath "sops-v${sops_version}.exe"
Set-Alias -Name kubectl -Value $kubectl_binary_path
Set-Alias -Name helm -Value $helm_binary_path
Set-Alias -Name sops -Value $sops_binary_path
$env:HELM_SECRETS_SOPS_PATH = $sops_binary_path
$env:HELM_SECRETS_HELM_PATH = $helm_binary_path

# set helmfile environment
$env:HELMFILE_ENV = $environment
$env:HELMFILE_HELM_PATH = $helm_binary_path

# Create Powershell autocompletion for kubectl and helm
kubectl completion powershell | Out-String | Invoke-Expression
helm completion powershell | Out-String | Invoke-Expression

# Set default namespace
kubectl config set-context --current --namespace=$k8s_namespace