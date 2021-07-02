#!/bin/sh
#
USERNAME=""
SETPASSWORD=0

if [ -f /etc/os-release ]; then
   . /etc/os-release
   case $NAME in
     "CentOS Linux")
       ;;
     "Red Hat Enterprise Linux")
       ;;
     "Oracle Linux Server")
       ;;
     *)
       echo "OS $NAME not supported."
       exit 1
       ;;
   esac
else
   echo "Can not determine OS version."
   exit 1
fi

if [ "$(id -u)" -ne 0 ]; then
   echo "Script must be run as root."
   exit 1
fi

while getopts "u:" opt
do
  case $opt in
    u)
      USERNAME=$OPTARG
      id -u $USERNAME > /dev/null 2>&1
      [ $? -ne 0 ] && echo "User $USERNAME does not exist." && exit 1
      ;;
    \?)
      err_end "Usage: $0 [ -u user ]"
      ;;
  esac
done

LOGFILE=$(mktemp)

echo "Log file: $LOGFILE"
echo "OS: $NAME"

echo -n "Install python ..."
yum -y install python36 >> $LOGFILE 2>&1
[ $? -ne 0 ] && echo "Can not install python-setuptools" && exit 1
echo "Ok."

echo -n "Install python-setuptools ..."
yum -y install python3-setuptools >> $LOGFILE 2>&1
[ $? -ne 0 ] && echo "Can not install python-setuptools" && exit 1
echo "Ok."

echo -n "Install python-pip ..."
yum -y install python3-pip >> $LOGFILE 2>&1
[ $? -ne 0 ] && echo "Can not install python-pip" && exit 1
echo "Ok."

echo -n "Install epel-release ..."
yum -y install epel-release >> $LOGFILE 2>&1
[ $? -ne 0 ] && echo "Can not install epel-release" && exit 1
echo "Ok."

echo -n "Install ansible ..."
yum -y install ansible >> $LOGFILE 2>&1
[ $? -ne 0 ] && echo "Can not install ansible" && exit 1
echo "Ok."

echo -n "Set default python ..."
alternatives --display python > /dev/null 2>&1
[ $? -eq 0 ] && alternatives --remove-all python
alternatives --install /usr/bin/python python /usr/bin/python3 1
echo "Ok."

while true; do
  echo -n "Setup Ansible Vault password file - create random, set password, or exit (r/s/e): "
  read ANSWER
  case $ANSWER in
    r)
      VAULTPASSWORD=$(tr -dc A-Za-z0-9 </dev/urandom | head -c 32)
      SETPASSWORD=1
      break
      ;;
    s)
      while true
      do
         echo -n "Password: "
         read -s PASSWORD
         echo ""
         echo -n "Retype Password: "
         read -s CHECK_PASSWORD
         echo ""
         if [ "$PASSWORD" != "$CHECK_PASSWORD" ]; then
            echo "Passwords do not match"
         else
            break
         fi
      done
      VAULTPASSWORD=$PASSWORD
      SETPASSWORD=1
      break
      ;;
    e)
      exit 0
      ;;
    *)
      echo ""
      echo "Unrecognized response."
      echo -n "Setup Ansible Vault password file - random,set, or exit (r/s/e): "
      ;;
  esac
done

if [ $SETPASSWORD -eq 1 ]; then
   [ ! -d /etc/ansible/ ] && mkdir -p /etc/ansible
   [ ! -f /etc/ansible/ansible.cfg ] && echo "[defaults]" > /etc/ansible/ansible.cfg
   grep vault_password_file /etc/ansible/ansible.cfg > /dev/null 2>&1
   if [ $? -ne 0 ]; then
      echo "vault_password_file = /etc/ansible/.vault_password" >> /etc/ansible/ansible.cfg
   else
      sed -i -e 's/^.*vault_password_file.*$/vault_password_file = \/etc\/ansible\/.vault_password/' /etc/ansible/ansible.cfg
   fi
   echo $VAULTPASSWORD > /etc/ansible/.vault_password
   chmod 440 /etc/ansible/.vault_password
   if [ -n "$USERNAME" ]; then
      GROUPNAME=$(id -g $USERNAME)
      chgrp $GROUPNAME /etc/ansible/.vault_password
   fi
fi
