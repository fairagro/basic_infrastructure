# fairagro-playground #

## How to deal with this project ##

This is a kubernetes project. You will need to have the following
tools available to deal with it:

- [kubectl](https://kubernetes.io/de/docs/tasks/tools/install-kubectl/)
- [helm](https://helm.sh/)
- [helmfile](https://github.com/helmfile/helmfile)
- [sops](https://github.com/getsops/sops#sops-secrets-operations)
- [gpg](https://gnupg.org/)
- [openssl](https://www.openssl.org/)
- [helm-secrets](https://github.com/jkroepke/helm-secrets)

Currently the project is being managed from Windows Powershell. So
this is the language of the scripts you find in the `scripts`
directory. All tools are also available for other platforms so you
are not forced to use Windows, though.

### `kubectl` ###

This is teh stabdard kubernetes command line tool for.

### `helm` ###

This is the kubernetes package manager, `helm` packages are called
`charts`. We use `helm` for third party packages and we also write
our own `helm` `charts` which can be found in the directory
`helmcharts`.

### `helmfile` ###

This describes the whole project within a single file -- the
`helmfile`. So it can be considers as project management tool. The
`helmfile` references all `helm` `charts` as well as the
correspoding configuration and secrets.

### `sops` ###

This tool is used for secret encrytion. It interfaces lower level
encryption tools like `gpg` and allows for multiuser features and
better `git` integration.

### `gpg` ###

This is the low-level encryption tool used by sops when involving
developer keys. Each developer has his or her own `gpg` key pair.
`sops` will encrypt all secrets using its a file-dependent master
key which in turn will be encrypted by the `gpg` keys of all
involved developers.

### `openssl` ###

`openssl` is needed when creating new kubernetes user accounts --
as in fact a kubernetes user is nothing more than as an X509
certificate signed by the kubernetes server.

### `helm-secrets` ###

This tool allows for the integration of `helm` and `sops`.

## Contexts, Environments and Users ##

This project is developed with kubernetes contexts in mind. A
context consists
of a kubernetes server, a namespace (usually the namespace
will be `fairagro`) and a user account. All components of this
project are always installed into the same namespace.
You can consider the combination of server and namespace as an
environment, each with its own
configurations and secrets. Currently the environment
'corki/fairagro'
is used for development/staging while the environment
'draven/fairagro' is used for production.

All active environments are kept with in the project in the
`environments` directory.

Each user (aka developer) will need to manage his own kubeconfig
files that include his personal access keys for kubernetes. The
included Windows Powershell scripts expect the kubeconfig file to
be stored in the folder
`%USERPROFILE%\.k8s_config\<servername>_<namespace>`.
So there will be one kubeconfig file per environment. It is
expected that each developer will only have one user account per
environment. This user will have admin right in the corresponding
namespace.

You can change the current context with the script
`set_context.ps1`. Note that it needs to be dot-sourced. E.g.:

    . scripts/set_context.ps1 corki fairagro

This script will also load all public gpg keys used by `sops` into
your `gpg` keyring and set command aliases for `kubectl`, `helm`,
`helmfile` and `sops`.

## Secrets management ##

Secrets are managed per environment (as other configuration). You
will
find a `secrets` folder within each environment. Secrets files are
encrypted with `sops` and always end in '.enc.yaml'. They are
referenced in the 'helmfile.yaml' for each release.

`sops` manages secret encryption using `gpg` for each developer.
There will also be secret encryption for the continuous deployment
pipeline which will probably use `age`.

Within each environment folder you will find a file '.sops.yaml'
that defines the behavior of `sops` for all files within the
directory as well as all sub-directories. You will notice that
files ending in '.enc.yaml' are encrypted using the gpg keys of all
active developers. Note that only the public keys of the developers
are needed for encryption, so every developer can encrypt secrets
for all other developers (as well as the CD pipeline). Only for
decryption the private key will be required. Note also that the
public keys of all active developers are included in the
`public_keys` folder of each environment. These keys will be loaded
automatically into your `gpg` keyring when you use the script
`set_context.ps1`.

Currently secrets files created by extracting secrets from
a 'values.yaml' file as needed by `helm`. These secrets are copied
to a corresponding secret file that has to be encrypted using
`sops`. Secret files are merged into the helm charts values upon
execution of `helm`/`helmfile`. If you use VisualStudio Code you
can install the 'vscode-sops' plugin that will automatically
encrypt all files according to the '.sops.yaml' file.

