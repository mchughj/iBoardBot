#!/bin/bash

echo "Checking for virtual env named 'env'"
FILE=`pwd`/env
if [ ! -d $FILE ]; then
  echo "Unable to find directory: $FILE"
  exit 1
fi

_service="Boardbot"
_dir="${1:-${PWD}}"
_user="${USER}"
_serviceSpec="
[Unit]
Description=${_service} Service
After=network.target network-online.target
[Service]
User=root
ExecStart=${_dir}/runme.sh
Restart=on-failure
[Install]
WantedBy=multi-user.target
"
_file="/lib/systemd/system/${_service}.service" 

echo "Creating ${_service} service"
if [ -f "${_file}" ]; 
then
    echo "Erasing old service file"
    sudo rm "${_file}"
fi

sudo touch "${_file}"
sudo echo "${_serviceSpec}" | sudo tee -a "${_file}" > /dev/null

echo "Enabling ${_service} to run on startup"
sudo systemctl daemon-reload
sudo systemctl enable ${_service}.service
if [ $? != 0 ];
then
    echo "Error enabling BoardBot service"
    exit 1
fi
sudo systemctl restart ${_service}.service

echo "Service enabled"
echo "Some shell scripts have been added:"
echo "  showLogs.sh"
echo "  restartService.sh"
echo "  stopService.sh"

echo "sudo journalctl -u ${_service}.service -f" > ${_dir}/showLogs.sh 
chmod +x ${_dir}/showLogs.sh

echo "sudo systemctl restart ${_service}.service" > ${_dir}/restartService.sh 
chmod +x ${_dir}/restartService.sh

echo "sudo systemctl stop ${_service}.service" > ${_dir}/stopService.sh 
chmod +x ${_dir}/stopService.sh

exit 0
