#!/bin/sh

ln -snf /tornado/maint/vm/openbsd /vagrant

PACKAGES="
python2.7
py-pip
py-virtualenv
"

PIP_PACKAGES="
tox
"

for package in $PACKAGES; do
    pkg_add $package
done

pip install $PIP_PACKAGES

/tornado/maint/vm/shared-setup.sh