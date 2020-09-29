#!/bin/bash
###############################################
# Description: Install the Python3 on CentOS 7
#
###############################################

PYTHON="python3.6"
PIP="pip3.6"

check_py3()
{
 yum -y install https://centos7.iuscommunity.org/ius-release.rpm
 yum list available > /tmp/available_pkgs.txt
 cat /tmp/available_pkgs.txt  |egrep python3
}

install_py3()
{
 yum -y install python36u
 $PYTHON --version
 yum -y install python36u-pip
 yum -y install python36u-devel
 $PYTHON -V
 ln -s /usr/bin/$PYTHON python3
}

setup_virtual_env()
{
 mkdir ~/environments
 cd ~/environments/
 $PYTHON -m venv my_env
 source ~/environments/my_env/bin/activate
 python -V
}

# Modules
install_py_modules()
{
  $PIP install requests
  $PIP install sgmllib3k
  $PIP install paramiko
  $PIP install httplib2
  $PIP install pytz
  $PIP install pyyaml
  $PIP install Geohash
  $PIP install python-geohash
  $PIP install deepdiff
}

install_tools()
{
  yum -y install wget git
}
#CSDK and Python SDK installation on new slave:
install_csdk()
{
  wget http://packages.couchbase.com/releases/couchbase-release/couchbase-release-1.0-6-x86_64.rpm
  rpm -iv couchbase-release-1.0-6-x86_64.rpm
  yum -y install libcouchbase-devel libcouchbase2-bin gcc gcc-c++
  $PIP install couchbase
}

other_steps()
{
  echo '** In file, /usr/lib64/$PYTHON/http/client.py , change chunk to chunk.encode()'
}

all()
{
  check_py3
  install_py3
  setup_virtual_env
  install_py_modules
  install_tools
  install_csdk
  other_steps
}
all
