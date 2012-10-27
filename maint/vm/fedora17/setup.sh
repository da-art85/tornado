#!/bin/sh

set -e

YUM_PACKAGES="
libcurl-devel
python-devel
python-pip
python3
python3-devel
"

yum -y install $YUM_PACKAGES

PIP_PACKAGES="
futures
pycurl
tox
twisted
virtualenv
"

# Fedora uses a different name for pip
pip-python install $PIP_PACKAGES

/tornado/maint/vm/shared-setup.sh

