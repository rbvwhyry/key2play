#!/bin/bash

set -exo pipefail

# Function to display error message and exit
display_error() {
  echo "Error: $1" >&2
  exit 1
}


# Function to execute a command and handle errors, with optional internet connectivity check
execute_command() {
  local check_internet="$2"  # Check for internet if this argument is provided

  echo "Executing: $1"

  if [ "$check_internet" = "check_internet" ]; then
    local max_retries=18  # Total number of retries (18 retries * 10 seconds = 3 minutes)
    local retry_interval=10  # Retry interval in seconds

    for ((attempt = 1; attempt <= max_retries; attempt++)); do
      # Check for internet connectivity
      if ping -q -c 1 -W 1 google.com &>/dev/null; then
        # Internet is available, execute the command
        eval "$1"
        local exit_code=$?

        if [ $exit_code -eq 0 ]; then
          return 0  # Command executed successfully
        else
          echo "Command failed with exit code $exit_code."
          sleep $retry_interval  # Wait before retrying
        fi
      else
        echo "Internet not available, retrying in $retry_interval seconds (Attempt $attempt/$max_retries)..."
        sleep $retry_interval  # Wait before retrying
      fi
    done

    echo "Command failed after $((max_retries * retry_interval)) seconds of retries."
    exit 1  # Exit the script after multiple unsuccessful retries
  else
    eval "$1"  # Execute the command without internet connectivity check
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
      echo "Command failed with exit code $exit_code."
    fi
  fi
}

# Function to add debian bullseye sources
add_sources() {
  cat <<EOF | sudo tee "/etc/apt/sources.list.d/debian-bullseye.list"
  deb http://deb.debian.org/debian bullseye main contrib non-free
  deb http://deb.debian.org/debian bullseye-updates main contrib non-free
  deb http://deb.debian.org/debian bullseye-backports main contrib non-free
  deb http://security.debian.org/debian-security/ bullseye-security main contrib non-free
EOF
}


# Function to update the OS
update_os() {
  execute_command "sudo apt-get update" "check_internet"
  execute_command "sudo apt-get upgrade -y"
}


# Function to create and configure the autoconnect script
configure_autoconnect_script() {
  # Create connectall.py file
  cat <<EOF | sudo tee /usr/local/bin/connectall.py > /dev/null

  
#!/usr/bin/python3
import subprocess

ports = subprocess.check_output(["aconnect", "-i", "-l"], text=True)
port_list = []
client = "0"
for line in str(ports).splitlines():
    if line.startswith("client "):
        client = line[7:].split(":",2)[0]
        if client == "0" or "Through" in line:
            client = "0"
    else:
        if client == "0" or line.startswith('\t'):
            continue
        port = line.split()[0]
        port_list.append(client+":"+port)
for source in port_list:
    for target in port_list:
        if source != target:
            subprocess.call("aconnect %s %s" % (source, target), shell=True)
EOF
  execute_command "sudo chmod +x /usr/local/bin/connectall.py"

  # Create udev rules file
  echo 'ACTION=="add|remove", SUBSYSTEM=="usb", DRIVER=="usb", RUN+="/usr/local/bin/connectall.py"' | sudo tee -a /etc/udev/rules.d/33-midiusb.rules > /dev/null

  # Reload services
  execute_command "sudo udevadm control --reload"
  execute_command "sudo service udev restart"

  # Create midi.service file
  cat <<EOF | sudo tee /lib/systemd/system/midi.service > /dev/null
[Unit]
Description=Initial USB MIDI connect

[Service]
ExecStart=/usr/local/bin/connectall.py

[Install]
WantedBy=multi-user.target
EOF

  # Reload daemon and enable service
  execute_command "sudo systemctl daemon-reload"
  execute_command "sudo systemctl enable midi.service"
  execute_command "sudo systemctl start midi.service"
}

# Function to enable SPI interface
enable_spi_interface() {
  # Edit config.txt file to enable SPI interface
  execute_command "sudo sed -i '$ a\dtparam=spi=on' /boot/config.txt"
}

# Function to install required packages
install_packages() {
  execute_command "sudo apt-get install --fix-broken -y virtualenv ruby git python3-pip autotools-dev libtool autoconf libopenblas-dev libasound2-dev libusb-dev libdbus-1-dev libglib2.0-dev libudev-dev libical-dev libreadline-dev python3:arm64 libatlas-base-dev libopenjp2-7 libtiff6 libjack0 libjack-dev libasound2-dev fonts-freefont-ttf gcc make build-essential git scons swig libavahi-client3 abcmidi dnsmasq hostapd dhcpcd raspi-config" "check_internet"
}

# Function to disable audio output
disable_audio_output() {
  echo 'blacklist snd_bcm2835' | sudo tee -a /etc/modprobe.d/snd-blacklist.conf > /dev/null
  sudo sed -i 's/dtparam=audio=on/#dtparam=audio=on/' /boot/config.txt
}

# Function to install RTP-midi server
install_rtpmidi_server() {
  execute_command "cd /home/"
  execute_command "sudo wget https://github.com/davidmoreno/rtpmidid/releases/download/v23.12/rtpmidid_23.12_arm64.deb" "check_internet"
  execute_command "sudo dpkg -i rtpmidid_23.12_arm64.deb"
  execute_command "sudo apt install --fix-broken -y"
  execute_command "sudo rm rtpmidid_23.12_arm64.deb"
}

# Function to create Hot-Spot
create_hotspot() {
  echo 'interface wlan0 static ip_address=192.168.4.1/24' | sudo tee --append /etc/dhcpcd.conf > /dev/null
  sudo mv /etc/dnsmasq.conf /etc/dnsmasq.conf.orig
  sudo systemctl daemon-reload
  sudo systemctl restart dhcpcd
  echo 'interface=wlan0 dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h' | sudo tee --append /etc/dnsmasq.conf > /dev/null

  hotspot_config_content=$(cat <<EOT
interface=wlan0
driver=nl80211
ssid=key2play
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=key2play
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
EOT
  )

  # Use echo to send the content to the file with sudo
  echo "$hotspot_config_content" | sudo tee /etc/hostapd/hostapd.conf > /dev/null

  echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' | sudo tee --append /etc/default/hostapd > /dev/null
  execute_command "sudo systemctl unmask hostapd"
  execute_command "sudo systemctl enable hostapd && sudo systemctl enable dnsmasq"
}

configure_network_interfaces() {
  # Edit /etc/network/interfaces file
  local interfaces_file="/etc/network/interfaces"
  local interfaces_config="
auto wlan0
iface wlan0 inet manual
wpa-conf /etc/wpa_supplicant/wpa_supplicant.conf
"

  echo "$interfaces_config" | sudo tee -a "$interfaces_file" > /dev/null
  echo "Network interfaces configuration added to $interfaces_file."
}

# Function to install key2play
install_key2play() {
  execute_command "cd /home/"
  execute_command "sudo rm -rf key2play"
  execute_command "sudo git clone https://github.com/rbvwhyry/key2play" "check_internet"
  execute_command "sudo chown -R $USER:$USER /home/key2play"
  execute_command "sudo chmod -R a+rwx /home/key2play"
  execute_command "cd key2play"
  execute_command "virtualenv venv"
  execute_command "sudo venv/bin/pip3 install -r requirements.txt --break-system-packages" "check_internet"
  execute_command "sudo raspi-config nonint do_boot_behaviour B2"
  execute_command "sudo adduser plv"
  echo "plv ALL=(ALL) NOPASSWD: ALL" | sudo tee /etc/sudoers.d/plv > /dev/null
  cat <<EOF | sudo tee /lib/systemd/system/visualizer.service > /dev/null
[Unit]
Description=key2play
After=network-online.target
Wants=network-online.target

[Install]
WantedBy=multi-user.target

[Service]
ExecStart=sudo /home/key2play/venv/bin/python3 /home/key2play/visualizer.py
Restart=always
Type=simple
User=plv
Group=plv
EOF
  execute_command "sudo systemctl daemon-reload"
  execute_command "sudo systemctl enable visualizer.service"
  execute_command "sudo systemctl start visualizer.service"

  execute_command "sudo chmod a+rwxX -R /home/key2play/"

  execute_command "sudo chmod +x /home/key2play/disable_ap.sh"
  execute_command "sudo chmod +x /home/key2play/enable_ap.sh"
}

finish_installation() {
  echo "------------------"
  echo ""
  echo "Installation complete. Rasp Pi will auto restart in 30 seconds."
  echo "If Rasp Pi does not restart on its own, wait 2 minutes, then manually reboot."
  echo "After reboot, wait for up to 10 minutes. The Visualizer should start, and the Hotspot 'key2play' will become available."

  execute_command "sudo shutdown -r +1"
  execute_command "sudo /home/key2play/enable_ap.sh"
  sleep 30
  # Reboot Raspberry Pi
  execute_command "sudo reboot"
}


# Main script execution
add_sources
update_os
configure_autoconnect_script
enable_spi_interface
install_packages
disable_audio_output
install_rtpmidi_server
install_key2play
configure_network_interfaces
create_hotspot
finish_installation
