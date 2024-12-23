# Purpose of ansible #

This ansible project is for installing the external nginx reverse proxy.

## Assumptions ##

* We're using an AlmaLinux VM
* The user 'ansible' exists, has passwordless sudo permissions and has an installed ssh key:

  ```bash
  $ useradd -c "Account used by remote ansible controller" -m -r -U -s /usr/bin/bash -p <password> ansible
  $ cat > /etc/sudoers.d/10-ansible <<EOL
  # user ansible has passwordless sudo permissions
  ansible ALL=(ALL)       NOPASSWD: ALL
  EOL
  $ mkdir /home/ansible/.ssh
  $ cat > /home/ansible/.ssh/authorized_keys <<EOL
  ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIBQqGq50yMo9LSIdx6Nwmgjr+bVfsTP+My5ME17cIOUc
  EOL
  $ chown -R ansible:ansible /home/ansible
  $ chmod 0700 /home/ansible/.ssh
  $ chmod 0600 /home/ansible/.ssh/authorized_keys
  ```

## Running ansible ##

To prepare a python venv that is able to run ansible:

```bash
cd ansible
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

To ansible ansible:

```bash
ansible-playbook -i hosts.yaml site.yaml
```

We expect that you've loaded the FAIRagro ansible controller ssh key into your local ssh agent.
