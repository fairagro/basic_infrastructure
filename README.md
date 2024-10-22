# FAIRagro basic_infrastructure #

## How to deal with this project ##

This project delivers a `vscode` dev container that contains all tools needed. To use that container
you need a running docker installation and choose 'Clone in Volume' after opening it in `vscode`.
It will take quite some time to build the container.

As the project contains encrypted secrets (that are also instantiated when running the container),
you will need to enter your personal `gpg` passphrase. This of course requires that your pgp key
is registered within the project. If not, please ask a colleague to add your key. Any colleague
already registered for the project will be able to do so. You can find the list of registered people
within the `public_gpg_keys` folder of an `environment` (so every environment has his own list of
registered users).

## Add a new user to the project ##

To add a new user to the project, please peform these steps.

On the machine where you have generated your key:

* Find out the key fingerprint:

  ```bash
  userid=Any string that identifies yor gpg key
  fingerprint=$(gpg --list-keys -a $userid | sed '2!d' | tr -d " ")
  echo $fingerprint
  ```

  `userid` can be any sub-string that identifies your key, i.e. that is listed behind 'uid' when
  executing `gpg --list-keys` without the `-a` switch. In this example it coud be 'carsten':

  ```bash #2
  pub   ed25519 2023-07-24 [SC]
      CC7B10CE8D78010ABB043F8DB1C462E90012ECFE # the fingerprint
  uid           [ultimate] Carsten Scharfenberg <carsten.scharfenberg@zalf.de>  # the full user id
  sub   cv25519 2023-07-24 [E]
  ```

* Export the public key:

  ```bash
  username=Your_Name
  filename=${fingerprint}_${username}.asc
  gpg --export --armor -o $filename $fingerprint
  ```

  In this case `username` is the actual user name consisting of capitalized first and last name,
  divided by an underscore. E.g.: `Carsten_Scharfenberg`.

With in this project structure on any machine/dev container:

* Import the key manually by:

  ```bash
  gpg --import '<filename>`
  ```

* cd into an environment folder
* Add the public `gpg` key file to the folder `public_gpg_keys` without changing the filename
* Add the key fingerprint to the file `.sops.yaml`
* Re-encrypt all secret files:

  ```bash
  find . -name *.enc.yaml | xargs sops updatekeys
  ```

## `kubectl` cheat sheet ##

find some useful `kubectl` calls below.

### List everything within a namespace ###

The normal call to list 'everything' within a namespace is, e.g.:

```bash
kubectl get all -n fairagro-nextcloud
```

This won't really list everything. Instead you can use:

```bash
kubectl api-resources --namespaced=true --verbs=list -o name | xargs -n 1 kubectl get --show-kind --ignore-not-found -n fairagro-nextcloud
```

### Delete 'everything' from a namespace ###

To delete everything from a namespace you would normally call, e.g.

```bash
kubectl delete all --all -n fairagro-nextcloud
```

In fact this does not delete everything, but keeps, e.g., `ConfigMap`s, `Secret`s and
`PersistentVolumeClaim`s. You also could delete the whole namespace to really delete everything:

```bash
kubectl delete namespace fairagro-nextcloud
```

Only this is not ideal for this project, because it will also delete `Roles`s and `RoleBinding`s
that are created by the `zalf-rdm/misc` project and are thus not easy to re-create.

Instead this is a good alternative:

```bash
kubectl delete all,configmap,secret,pvc,ingress,serviceaccount --all -n fairagro-nextcloud
```

Consider to [list all resources](#list-everything-within-a-namespace) to check if really
everything except `Roles`s and `RoleBindings` has been deleted.
