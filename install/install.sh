#!/usr/bin/bash
### CHAPPS installation script
#
### Root privilege required to run
#
# Root is used to add a 'chapps' user (and group) as a system user,
# Also to copy:
#  - the scripts
#  - Python package
#  - SystemD service profiles
# to their respective locations
#
# During operation, it is recommended that the chapps user be used
# to run the CHAPPS service(s), in order to avoid allowing a user with
# more permissions, such as postfix or root, run the service.
# This is implemented in the provided SystemD service profiles.

### Add CHAPPS user
sudo useradd -r chapps -d /home/chapps -p 'cH4pP$' -mU

### Install Python package
PYTHON_LIB_VER=`python3 --version | cut -f2 -d" " | cut -f1,2 -d"."`
PYTHON_LIB_PATH="/usr/local/lib/python${PYTHON_LIB_VER}/"
sudo cp -r ../chapps/ ${PYTHON_LIB_PATH}

### Create CHAPPS config location
sudo mkdir /etc/chapps
sudo chown chapps.chapps /etc/chapps

### Install CHAPPS scripts
sudo cp ../services/chapps_outbound_quota.py /usr/local/bin/chapps_outbound_quota
sudo cp ../services/chapps_greylisting.py /usr/local/bin/chapps_greylisting
sudo cp ../services/chapps_outbound_multi.py /usr/local/bin/chapps_outbound_multi

### Install SystemD service profiles
sudo cp ../install/chapps_oqp.service /usr/lib/systemd/system
sudo cp ../install/chapps_grl.service /usr/lib/systemd/system
sudo cp ../install/chapps_multi.service /usr/lib/systemd/system

sudo systemctl daemon-reload

echo "Please note: no services are enabled; use systemctl enable <service> to enable compatible services you want to run concurrently."
