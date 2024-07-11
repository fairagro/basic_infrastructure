# About DataPLANT DataHUB in the FAIRagro context #

DataHUB is a special gitlab version with predefined CI/CD-pipeline to validate ARCs.
DataPLANT offers dedicated docker images for DataHUB that are built on top of the official gitlab docker images.
Currently DataPLANT only offers its own versions of the "docker" docker images. There are also "kubernetes" docker images available for gitlab. The difference is that for kuberentes the many services that comprise gitlab are built into their own pods/containers whereas for docker all services are built into a single container. Also helm charts are available for the "kubernetes" docker containers but not for the "docker" docker container.
So we are in the unfortunate situation to install the "docker" docker images on kubernetes and write our own (this) helm chart.

## Installation caveats ##

Currently the installation cannot be performed fully automated. This is due to two reason:

* The configuration of gitlab itself can only be done via web interface or API (the configuration of all the services running on behave of gitlab, on the otehr hand, is done traditioanlly via config files). So it's not trivial to automate this via helm.
* For the CI/CD pipeline we need to setup a so-called gitlab runner. This is an additional pod/container that needs to be registered within gitlab. The registration workflow is the following:

  1. Create a runner authentication and an admin api token using the gitlab web page or API.
  2. Use these tokens within the gitlab runner and register it.

  This workflow cannot be represented by helm. There are gitlab runner operators available that might be able to fix this issue, but this was not yet investigated.

## Installation steps ##

Assuming that you're installing this helm chart via argocd:

1. Create the argocd app, possibly using the script `setup_project_in_argocd.sh`.
2. Synchronize the app. This will not succeed because the gitlab runner is still lacking its registration token. Still gitlab itself should be installed successfully so you can access the web interface.
3. In the gitlab web interface:
    1. login as root.
    2. Navigate to `Admin Area`->`CI/CD`->`Runners`.
    3. Add a new runner by clicking `New instance runner`.
    4. Activate the checkbox `Run untagged jobs` and finish runner creation by clicking `Create runner`.
    5. Copy and backup the runner authentication token that you are presented below `Step 1`.
    6. Navigate to `Edit profile`(click on your avatar picture)->`Access Tokens`.
    7. Create a new personal access token by clicking `Add new token`.
    8. Give the token a name -- e.g. 'datahub' -- and select the checkboxes `admin_mode` and `api`. It's also a good idea to extend the expiration date.
    9. Now copy and backup your personal admin access token that will be used by the datahub CI/CD pipeline to access the gitlab API.
4. Clone the `basic_infrastructure` repo if not done already and enter the runner authentication token:
    1. `git clone git@github.com:fairagro/basic_infrastructure.git`
    2. Edit the file `environments/<cluster name>/values/fairagro-datahub.enc.yaml`. Note that this file is sops-encrypted.
    3. Add/modify two lines:

        ```yaml
        gitlabRunnertoken: glrt-xxxx...
        datahub_api_token: glpat-xxxx...
        ```

    4. Commit and push your changes (possibly this requires filing a pull request).
5. Return to argocd and sync the datahub app again. Now the gitlab runner should be setup successfully.

Note that in principle to could enter both tokens directly into argocd instead of pushing them to the project. But in this case your argocd app will never be in sync.

## Configure gitlab ##

As mentioned before currently gitlab need to be configured using the web interface. Currently we impose these settings that can be accesses below `Admin Area`->`Settings`. Please do not forget to click `Save changes` for all settings:

* Below `General`->`Visibility and access controls` make these settings:

  * Disbable ssh access by setting `Enabled Git access protocols` to `Only HTTP(S)`. For the final version of our datahub we surely want ssh to be enabled, but currently it is not.
  * Enter the URL of your server below `Custom Git clone URL for HTTP(S)`. For the current version of this helm chart this is necessary as the `external_url` variable passed to the gitlab container uses the http protocol instead of https (refer to the corresponding [issue](https://github.com/fairagro/basic_infrastructure/issues/33)).

* Below `General`->`Account and limit`: uncheck `Gravatar enabled` and `Allow users to register any application to use GitLab as an OAuth provider. This setting does not affect group-level OAuth applications.` for security reasons.

* Below `General`->`Sign-up restrictions` uncheck `Sign-up enabled` to prevent from unwanted user registration attempts.

* Check `General`->`Customer experience improvement and third-party offers`->`Do not display content for customer experience improvement and offers from third parties`.

* Below `Network`->`Outbound requests` clear the checkboxes `Allow requests to the local network from webhooks and integrations` and `Allow requests to the local network from system hooks` for security reasons.

* Below `CI/CD`->`Continuous Integration and Deployment` activate the checkboxs `Default to Auto DevOps pipeline for all projects` and `Enable instance runners for new projects`. This will activate the ARC validation CI/CD pipeline for all repositories.

## Upgrade gitlab ##

Note that there is a [gitlab upgrade documentation](https://docs.gitlab.com/17.1/ee/update/) available. You should always start here if you want to perform an upgrade.

Nevertheless in a early state of our DataHUB installation we performed an upgrade from gitlab 17.1.1 to 17.1.2 by simply increasing the container image version and syncing with argocd.
There is one caveat: DataHUB images are not versioned, so we need to use the image digest instead of a version number. To obtain the digest of the most recent available version:

```bash
> docker image rm ghcr.io/nfdi4plants/datahub:main
...
> docker pull ghcr.io/nfdi4plants/datahub:main
...
> docker inspect ghcr.io/nfdi4plants/datahub:main
[
    {
        "Id": "sha256:104b7fa57bcf708f65cc90269a1ae30d661144ce86461322e46c0b3c1dfde65b",
        "RepoTags": [
            "ghcr.io/nfdi4plants/datahub:main"
        ],
        "RepoDigests": [
            "ghcr.io/nfdi4plants/datahub@sha256:7199a9783ec03c0fda0efb948e52e6cb4f69e12a2ff4808d49ed0d7c951b7287"
        ],
...
```

You're looking for the `RepoDigests`. Please edit the file `environments/<cluster name>/fairagro-datahub.yaml` and adapt the value `image.digest` accordingly.
