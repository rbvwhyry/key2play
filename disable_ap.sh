#!/bin/bash

set -exo pipefail

sleep 1

# disable the AP
sudo cp config/hostapd.disabled /etc/default/hostapd
sudo cp config/dhcpcd.conf.disabled /etc/dhcpcd.conf
sudo cp config/dnsmasq.conf.disabled /etc/dnsmasq.conf

# load wlan configuration
sudo cp config/wpa_disable_ap.conf /etc/wpa_supplicant/wpa_supplicant.conf

set +e # unset e to keep running commands after one returns error, seems like they do that
sleep 1
sudo wpa_cli -i wlan0 reconfigure
sudo wpa_cli -i p2p-dev-wlan0
sleep 2
sudo ifconfig wlan0 down
sleep 2
sudo ifconfig wlan0 up