param (
    [Parameter(Mandatory = $true)] [string] $cluster,
    [Parameter(Mandatory = $true)] [string] $namespace,
    [Parameter(Mandatory = $true)] [string] $username,
    [string] $environment = "${cluster}_${namespace}",
    [string] $user_kubeconfig = "$env:USERPROFILE\.k8s_config\${cluster}_${namespace}.yaml",
    [string] $gpg_key
)

if (-not $gpg_key) {
    # Try to find a matching gpg key for the the given name in the user's gpg keyring
    $gpg_output = (gpg --with-colons --list-keys --fixed-list-mode) -join ""
    $pattern = "fpr(?::[^:]*){8}:([A-Z0-9]+):uid(?::[^:]*){8}:[^:]*${username}[^:]*:"
    $found = $gpg_output | Select-String -AllMatches -Pattern $pattern
    $count = $found.Matches.Count
    if ($count -eq 1) {
        $gpg_key = $found.Matches[0].Groups[1].Value
    } else {
        throw "Could not unambiguously find gpg key for user ${username}. Found ${count} matching keys."
    }
} 

# we need to deal with yaml...
#Install-Module -Name powershell-yaml -Scope CurrentUser -AllowClobber -Force
Import-Module powershell-yaml

# figure out some paths
$project_path = Split-Path $PSScriptRoot -Parent
$encrypted_admin_config = Join-Path $project_path -ChildPath "clusters" | Join-Path -ChildPath "${cluster}_admin.enc.yaml"
$environment_path = Join-Path $project_path -ChildPath "environments" | Join-Path -ChildPath $environment

# Check that the environment is actually known
if (-not (Test-Path -Path $environment_path -PathType Container)) {
    throw "The environement directory for environment ${environment} does not exist. Please consider to create the environment first. Exiting..."
}

# figure out gpg key user id
$gpg_output = (gpg --with-colons --list-keys --fixed-list-mode) -join ""
$pattern = "fpr(?::[^:]*){8}:${gpg_key}:uid(?::[^:]*){8}:([^:]*):"
$found = $gpg_output | Select-String -AllMatches -Pattern $pattern
$count = $found.Matches.Count
if ($count -eq 1) {
    $gpg_user_id = $found.Matches[0].Groups[1].Value
} else {
    throw "Could not find gpg key with id ${gpg_key}."
}
$pattern = "^(.*?)( \(.*?\))?(?: <(.*)>)?$"
$found = $gpg_user_id | Select-String -AllMatches -Pattern $pattern
$user = $found.Matches[0].Groups[1].Value -replace "[$([RegEx]::Escape([string][IO.Path]::GetInvalidFileNameChars()))]+","_"
# $comment = $found.Matches[0].Groups[2].Value -replace "[$([RegEx]::Escape([string][IO.Path]::GetInvalidFileNameChars()))]+","_"
# $email = $found.Matches[0].Groups[3].Value -replace "[$([RegEx]::Escape([string][IO.Path]::GetInvalidFileNameChars()))]+","_"

# output public gpg key to context key files
$public_key_file_name = "${gpg_key}_${user}.asc"
$public_key_file = Join-Path $environment_path -ChildPath "public_keys" | Join-Path -ChildPath $public_key_file_name 
gpg --batch --yes --armor --export --output $public_key_file $gpg_key

# add gpg key to .sops.yaml
$sopsYamlFile = Join-Path $environment_path -ChildPath ".sops.yaml"
$sopsYaml = Get-Content $sopsYamlFile | ConvertFrom-Yaml
$creation_rules = $sopsYaml['creation_rules']
$index = -1
for ($i = 0; $i -lt $creation_rules.Count; $i++) {
    if ($creation_rules[$i].path_regex -eq '\.enc\.yaml$') {
        $index = $i
        break
    }
}
if ($creation_rules[$index].pgp) {
    $pgpKeys = $creation_rules[$index].pgp -split ", "
} else {
    $pgpKeys = @()
}
if ($pgpKeys -notcontains $gpg_key) {
    $pgpKeys += $gpg_key
}
$sopsYaml['creation_rules'][$index]['pgp'] = $pgpKeys -join ", "
$sopsYaml | ConvertTo-Yaml | Set-Content $sopsYamlFile

# create private key and csr for new user
$key_file = (New-TemporaryFile).FullName
try {
    $csr_file = (New-TemporaryFile).FullName
    try {
        openssl req -new -newkey ed25519 -nodes -out $csr_file -keyout $key_file -subj "/CN=${username}/O=admin"

        # decrypt the kubernetes cluster admin config and write to temp file for usage
        $admin_config = (New-TemporaryFile).FullName
        try {
            sops -d $encrypted_admin_config | Out-File -FilePath $admin_config

            # issue certificate request
            $csr = (Get-Content $csr_file) -join "`n"
            $csrBase64 = [System.Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($csr))
            @"
apiVersion: certificates.k8s.io/v1
kind: CertificateSigningRequest
metadata:
    name: ${username}
spec:
    request: ${csrBase64}
    signerName: kubernetes.io/kube-apiserver-client
    expirationSeconds: 86400
    usages:
        - client auth
"@ | kubectl create --kubeconfig $admin_config -f -
            if ($LASTEXITCODE -ne 0) {
                throw "Failed to issue certificate request. Exiting..."
            }

            # approve certificate request
            kubectl certificate approve $username --kubeconfig $admin_config

            # assign certificate/user to role
            @"
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
    name: admin-user-binding-${username}
    namespace: ${namespace}
subjects:
    -   kind: User
        name: ${username}
        apiGroup: rbac.authorization.k8s.io
roleRef:
    kind: ClusterRole
    name: admin
    apiGroup: rbac.authorization.k8s.io
"@ | kubectl apply --kubeconfig $admin_config -f -

            # retrieve signed certificate
            $certResult = kubectl get csr/$username -o json --kubeconfig $admin_config | ConvertFrom-Json
            $cert = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($certResult.status.certificate))

            # write certificate to temp file
            $cert_file = (New-TemporaryFile).FullName
            try {
                $cert | Set-Content -Path $cert_file

                # create credentials in kubeconfig
                kubectl config set-credentials $username --client-key=$key_file --client-certificate=$cert_file --embed-certs --kubeconfig=$user_kubeconfig
            } finally {
                Remove-Item $cert_file
            }

            # read in admin_config so we can access the cluster config
            $config_yaml = Get-Content $admin_config
            $config = $config_yaml | ConvertFrom-Yaml

        } finally {
            Remove-Item $admin_config
        }
    } finally {
        Remove-Item $csr_file
    } 
} finally {
    Remove-Item $key_file
}

# write cluster ca cert to temp file
$ca_cert_file = (New-TemporaryFile).FullName
try {
    $ca_cert = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($config.clusters[0].cluster['certificate-authority-data']))
    $ca_cert | Set-Content -Path $ca_cert_file

    # create kubernetes cluster in kubeconfig
    $server_endpoint = $config.clusters[0].cluster.server
    kubectl config set-cluster $cluster --server=$server_endpoint --certificate-authority=$ca_cert_file --embed-certs --kubeconfig=$user_kubeconfig
} finally {
    Remove-Item $ca_cert_file
}

# create kubernetes context in kubeconfig
kubectl config set-context $environment --cluster=$cluster --namespace=$namespace --user=$username --kubeconfig=$user_kubeconfig
