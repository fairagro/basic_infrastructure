# This script needs to be dot-sourced to be effective. So check this
if (-not ($MyInvocation.InvocationName -eq '.' -or $MyInvocation.Line -eq '')) {
    throw "This script is intended to be dot-sourced. Exiting..."
}

# The actual config to apply. Should probably be specified using command line options. 
$k8s_cluster = "corki"
$k8s_namespace = "fairagro"
$kubectl_version = "1_24_15"
$helm_version = "3_12_1"
$binary_path = "$env:USERPROFILE\local"

# figure out path of current script
$mypath = $MyInvocation.MyCommand.Path

# get the parent path and set KUBECONFIG environemtn variable to the actual cluster config file
$script_path = Split-Path $mypath -Parent
$env:KUBECONFIG = "${script_path}\${k8s_cluster}.yaml"

# make the desired kubectl and helm versions available in terms of the commands 'kubectl' and 'helm'
Set-Alias -Name kubectl -Value "${binary_path}\kubectl_v${kubectl_version}.exe"
Set-Alias -Name helm -Value "${binary_path}\helm_v${helm_version}.exe"

# Create Powershell autocompletion for kubectl
kubectl completion powershell | Out-String | Invoke-Expression

# Set default namespace
kubectl config set-context --current --namespace=$k8s_namespace