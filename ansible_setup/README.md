# Ansible Playbooks for Cloud-like Cluster

## Before using 
Check and update [hosts](hosts), [group_vars/all](group_vars/all) and [.ansible.cfg](.ansible.cfg) as needed.

## Before running playbook
```
export ANSIBLE_CONFIG=$PWD/.ansible.cfg 
export ANSIBLE_HOST_KEY_CHECKING=false
```
## Setup cluster
```
ansible-playbook 10-clean.yml
ansible-playbook 11-install.yml
ansible-playbook 12-node-init.yml
ansible-playbook 13-cluster-init.yml
```
## Setup Root CA
```
ansible-playbook 14-certificate.yml
```
## Post setup config
```
ansible-playbook 15-cluster-config.yml --limit 'all:!couchbase_new_nodes'
```
## Create users. See [vars/user_vars.yml](vars/user_vars.yml).
```
ansible-playbook 20-user.yml
```
## Create bucket. See [vars/bucket_vars.yml](vars/bucket_vars.yml).
```
ansible-playbook 21-bucket.yml
```
## Enable firewall. See [vars/ports_vars.yml](vars/ports_vars.yml).
```
ansible-playbook 30-firewall.yml
```
## Add new node/s
```
ansible-playbook 40-add-nodes.yml
```