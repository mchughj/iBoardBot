#!/bin/bash
echo "Checking for virtual env named 'cv'"
FILE=/home/pi/.virtualenvs/cv
if [ ! -d $FILE ]; then
  echo "Unable to find directory: $FILE"
  exit 1
fi

_dir="${1:-${PWD}}"
_user="${USER}"
_service="
[Unit]
Description=Boardbot Service
After=network.target network-online.target
[Service]
User=root
ExecStart=${_dir}/runme.sh
Restart=on-failure
[Install]
WantedBy=multi-user.target
"
_file="/lib/systemd/system/boardbot.service" 

echo "Creating Boardbot service"
if [ -f "${_file}" ]; 
then
    echo "Erasing old service file"
    sudo rm "${_file}"
fi

sudo touch "${_file}"
sudo echo "${_service}" | sudo tee -a "${_file}" > /dev/null

echo "Enabling Boardbot service to run on startup"
sudo systemctl daemon-reload
sudo systemctl enable boardbot.service
if [ $? != 0 ];
then
    echo "Error enabling BoardBot service"
    exit 1
fi
sudo systemctl restart boardbot.service
echo "Boardbot service enabled"
echo "Use sudo journalctl -u boardbot.service -f to see the logs"
exit 0
