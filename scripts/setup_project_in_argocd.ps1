param (
    [Parameter(Mandatory = $true)] [string] $environment
)

# figure out some paths
$project_path = Split-Path $PSScriptRoot -Parent
$environments_path = Join-Path $project_path "environments"
$environment_path = Join-Path $environments_path -ChildPath $environment

# Login to argocd
$sops_env = "sops exec-env ${environment_path}\credentials\argocd_secrets.enc.yaml"
Invoke-Expression "${sops_env} 'argocd login %ARGOCD_SERVER% --insecure --grpc-web-root-path %ARGOCD_PREFIX% --username=%ARGOCD_ADMIN_USER% --password=%ARGOCD_ADMIN_PASSWORD%'"

# Install keycloak app
argocd app create keycloak `
    --repo "git@github.com:fairagro/basic_infrastructure.git" `
    --revision HEAD `
    --path "helmcharts/zalf-keycloak" `
    --dest-server "https://kubernetes.default.svc" `
    --project fairagro `
    --dest-namespace fairagro-keycloak `
    --values "../../environments/${environment}/values/zalf-keycloak.yaml" `
    --values "../../environments/${environment}/values/zalf-keycloak.enc.yaml"