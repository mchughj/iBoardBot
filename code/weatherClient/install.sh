#!/bin/bash
echo "This script will install the weatherClient as a service in linux land"
echo "Checking for virtual env named 'cv'"
FILE=/home/pi/.virtualenvs/cv
if [ ! -d $FILE ]; then
  echo "Unable to find directory: $FILE"
  exit 1
fi

echo "Checking for local 'keys' file"
FILE=keys
if [ ! -f $FILE ]; then
  echo "Unable to find keys file - it must be sourced and contain a single line like: export WEATHER_API_KEY=FOO"
  exit 1
fi

_dir="${1:-${PWD}}"
_user="${USER}"
_service="
[Unit]
Description=Boardbot Weather Client
After=network.target network-online.target
[Service]
User=root
ExecStart=${_dir}/runme.sh
Restart=on-failure
[Install]
WantedBy=multi-user.target
"
_file="/lib/systemd/system/weatherclient.service" 

echo "Creating Weather Client service"
if [ -f "${_file}" ]; 
then
    echo "Erasing old service file"
    sudo rm "${_file}"
fi

sudo touch "${_file}"
sudo echo "${_service}" | sudo tee -a "${_file}" > /dev/null

echo "Enabling WeatherClient service to run on startup"
sudo systemctl daemon-reload
sudo systemctl enable weatherclient.service
if [ $? != 0 ];
then
    echo "Error enabling WeatherClient service"
    exit 1
fi
sudo systemctl restart weatherclient.service
echo "WeatherClient service enabled"
echo "Use sudo journalctl -u weatherclient.service -f to see the logs"
exit 0
