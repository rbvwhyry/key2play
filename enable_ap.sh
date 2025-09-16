#!/usr/bin/env bash

set -exo pipefail

sleep 1

# enable the AP
sudo cp config/hostapd /etc/default/hostapd
sudo cp config/dhcpcd.conf /etc/dhcpcd.conf
sudo cp config/dnsmasq.conf /etc/dnsmasq.conf

# load wan configuration
sudo cp config/wpa_enable_ap.conf /etc/wpa_supplicant/wpa_supplicant.conf

set +e # unset e to keep running commands after one returns error, seems like they do that
sleep 1
sudo wpa_cli -i wlan0 reconfigure
sudo wpa_cli -i p2p-dev-wlan0 reconfigure
sleep 2
sudo ifconfig wlan0 down
sleep 3
sudo ifconfig wlan0 up
sleep 2

# Check if hostapd is masked, and unmask it if needed
if [[ $(sudo systemctl is-enabled hostapd) == "masked" ]]; then
  echo "Unmasking hostapd"
  sudo systemctl unmask hostapd
fi

sudo systemctl restart hostapd