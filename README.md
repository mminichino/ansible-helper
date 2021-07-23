# ansible-helper

Lightweight CLI alternative to Ansible Tower. Allows you to create transportable Ansible packages that can be invoked on the command line or from a script.

If you are installing this on a new system or container, you can use the setup script to install the prerequisites and setup Ansible Vault.

````
$ ansible-helper.py playbook.yaml [ -p | -l | -s save_key | -r save_key ] | [ -c | -d ] --extra_var1 value --extra_var2 value
````

Option | Description
------ | -----------
-p | Print available options for the playbook
-l | List saved plays
-s | Create a new saved play with the name supplied
-r | Recall options from the saved play with the name supplied
-c | Enable check mode
-d | Enable debug mode
-a | Prompt for password (if the playbook is designed for password integration - see below)
-P | Retrieve password from the supplied variable in Ansible Vault (another password integration option)
-h | Run playbook on this host or hosts, separate multiple hosts with a comma (if supported by the playbook - see below)
-v | Force the use of Ansible Vault (if not auto detected - it will prompt for the vault password if it can not be automatically located)
-f | Run playbook and search for the fact supplied, and if found print the value - useful for playbooks designed to return a value
--cryptfile | path to Ansible Vault encrypted file
--parameter | Variable as defined in the playbook to provide the supplied value (see below)

A playbook requires a particular structure to work with the Ansible Helper. Variables are defined in the opening comments with the format ````var:var_name````. If you want to use the host parameter, set hosts to ````all```` in the playbook. Otherwise, set host to ````localhost```` and pass hostnames or IP addresses as variables (for example for modules that receive connection information from parameters).

````
---
#
# var:extra_var1
# var:extra_var2
# var:extra_var3
#
- name: My Playbook
  hosts: localhost | all
````

The Jinja2 format to support password integration is as follows.

````
password: "{{ ask_password if ask_password is defined else lookup('vars',password_var) if password_var is defined else None }}"
````

For example, putting it all together here is an example of a playbook that will install a software package on a Linux host. The hostname will be provided with the ````-h```` option, the user with sudo privilege is supplied by the ````user_name```` parameter, and password integration is used meaning you can either enter the password at run time with ````-a```` or you can provide an Ansible Vault variable with ````-P````.

````
---
#
# var:user_name
# var:rpm_file
#
- name: Install Software Package
  hosts: all
  vars:
    ansible_host_key_checking: False
    ansible_become: yes
    ansible_become_method: sudo
    ansible_become_pass: "{{ ask_password if ask_password is defined else lookup('vars',password_var) if password_var is defined else None }}"
    ansible_ssh_user: "{{ user_name if user_name is defined else 'admin' }}"
    ansible_ssh_pass: "{{ ask_password if ask_password is defined else lookup('vars',password_var) if password_var is defined else None }}"
  tasks:
- fail: msg="Full path to RPM is required."
  when: rpm_file is not defined
- name: Copy RPM to host
  ansible.builtin.copy:
    src: "{{ rpm_file }}"
    dest: "/var/tmp/{{ rpm_file | basename }}"
    mode: '0600'
- name: Install RPM
  yum:
    name: "/var/tmp/{{ rpm_file | basename }}"
    state: latest
    disable_gpg_check: yes
````

To run this on host ````host01```` using the vault variable ````password_variable```` with user ````jdoe```` as an example:
````
$ ansible-helper.py install-rpm.yaml -h host01 -P password_variable --user_name jdoe --rpm_file /home/jdoe/software.rpm
````
