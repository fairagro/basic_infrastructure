param (
    [Parameter(Mandatory = $true)] [string] $environment,
    [string] $kubectl_version = "1.27.3",
    [string] $helm_version = "3.12.1",
    [string] $sops_version = "3.7.3",
    [string] $argocd_version = "2.8.4",
    [string] $binary_path = "$env:USERPROFILE\local",
    [string] $docker_desktop_kubectl = "C:\Program Files\Docker\Docker\Resources\bin\kubectl.exe"
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
    throw "The environement directory for environement ${environment} does not exist. Exiting..."
}

if ($environment -eq "local_dev") {
    Remove-Item Env:\KUBECONFIG -ErrorAction SilentlyContinue
    Set-Alias -Name kubectl -Value $docker_desktop_kubectl
} else {
    # set KUBECONFIG environment variable to the actual cluster config file
    $kubeconfig = New-TemporaryFile
    sops -d "${environment_path}\credentials\project_admin.enc.yaml" > "$kubeconfig"
    $env:KUBECONFIG = $kubeconfig

    $kubectl_binary_path = Join-Path $binary_path -ChildPath "kubectl-v${kubectl_version}.exe"
    Set-Alias -Name kubectl -Value $kubectl_binary_path
}

# make the desired kubectl and helm versions available in terms of the commands 'kubectl' and 'helm'
$helm_binary_path = Join-Path $binary_path -ChildPath "helm-v${helm_version}.exe"
$sops_binary_path = Join-Path $binary_path -ChildPath "sops-v${sops_version}.exe"
$argocd_binary_path = Join-Path $binary_path -ChildPath "argocd-v${argocd_version}.exe"
$helmfile_binary_path = Join-Path $binary_path -ChildPath "helmfile.exe"
Set-Alias -Name helm -Value $helm_binary_path
Set-Alias -Name sops -Value $sops_binary_path
Set-Alias -Name argocd -Value $argocd_binary_path
Set-Alias -Name helmfile -Value $helmfile_binary_path
$env:HELM_SECRETS_SOPS_PATH = $sops_binary_path
$env:HELM_SECRETS_HELM_PATH = $helm_binary_path

# set helmfile environment
$env:HELMFILE_ENV = $environment
$env:HELMFILE_HELM_PATH = $helm_binary_path

# import all public keyfiles into gpg keyring so sops can find them
$public_key_path = Join-Path $environment_path -ChildPath "public_gpg_keys"
Get-ChildItem -File -Path $public_key_path -Filter "*.asc" | ForEach-Object { gpg --import $_.FullName }

# Create Powershell autocompletion for kubectl and helm
kubectl completion powershell | Out-String | Invoke-Expression
helm completion powershell | Out-String | Invoke-Expression
helmfile completion powershell | Out-String | Invoke-Expression

# Set default namespace
#kubectl config use-context $environment