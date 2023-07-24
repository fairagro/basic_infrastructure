param (
    [Parameter(Mandatory = $true)] [string] $k8s_cluster,
    [string] $k8s_namespace = "fairagro",
    [string] $kubectl_version = "1.24.15",
    [string] $helm_version = "3.12.1",
    [string] $binary_path = "$env:USERPROFILE\local"
)

# This script needs to be dot-sourced to be effective. So check this
if (-not ($MyInvocation.InvocationName -eq '.' -or $MyInvocation.Line -eq '')) {
    throw "This script is intended to be dot-sourced. Exiting..."
}

# figure out some paths
$mypath = $MyInvocation.MyCommand.Path
$script_path = Split-Path $mypath -Parent
$cluster_config_path = Join-Path $script_path "${k8s_cluster}.yaml"

# Check that the cluster is actually known
if (-not (Test-Path -Path $cluster_config_path -PathType Leaf)) {
    throw "The desired cluster ${k8s_cluster} does not exist. Exiting..."
}

# set KUBECONFIG environment variable to the actual cluster config file
$env:KUBECONFIG = $cluster_config_path

# make the desired kubectl and helm versions available in terms of the commands 'kubectl' and 'helm'
$kubectl_version_underscore = $kubectl_version -replace '\.', '_'
Set-Alias -Name kubectl -Value "${binary_path}\kubectl_v${kubectl_version_underscore}.exe"
$helm_version_underscore = $helm_version -replace '\.', '_'
Set-Alias -Name helm -Value "${binary_path}\helm_v${helm_version_underscore}.exe"

# Create Powershell autocompletion for kubectl and helm
kubectl completion powershell | Out-String | Invoke-Expression
helm completion powershell | Out-String | Invoke-Expression

# Set default namespace
kubectl config set-context --current --namespace=$k8s_namespace