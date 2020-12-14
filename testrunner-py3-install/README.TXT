Install ansible and Update hosts file, replace <IP> with actaul ip of the machine where you need python to be installed

Run the following ansible command:

ansible-playbook -i /root/ansible/hosts /root/ansible/install_python_3.7.6.yml