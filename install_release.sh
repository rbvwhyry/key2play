#!/usr/bin/env bash

set -e # this option quits the file if a process returns a non-zero exit code
set -o pipefail # sets the exit code of a pipeline to the rightmost non-zero exit code
set -u # treat unset variables as an error
set -x # print the commands being executed

cd $HOME

sudo apt-get update && sudo apt-get upgrade -y

set +e
sudo adduser key2play
set -e
sudo tee /etc/sudoers.d/key2play > /dev/null << 'EOF'
key2play ALL=(ALL) NOPASSWD: ALL
EOF

# Create connectall.py file
sudo tee /usr/local/bin/connectall.py >/dev/null << 'EOF'
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

sudo chmod +x /usr/local/bin/connectall.py

sudo tee -a /etc/udev/rules.d/33-midiusb.rules > /dev/null << 'EOF'
ACTION=="add|remove", SUBSYSTEM=="usb", DRIVER=="usb", RUN+="/usr/local/bin/connectall.py"
EOF
sudo udevadm control --reload
sudo service udev restart

sudo tee /lib/systemd/system/midi.service > /dev/null << 'EOF'
[Unit]
Description=Initial USB MIDI connect

[Service]
ExecStart=/usr/local/bin/connectall.py

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable midi.service
sudo systemctl start midi.service

PACKAGES=(
    abcmidi
    autoconf
    autotools-dev
    build-essential
    fonts-freefont-ttf
    gcc
    git
    iproute2
    jq
    libasound2
    libasound2-dev
    libavahi-client-dev
    libavahi-client3
    libavahi-common3
    libc6
    libdbus-1-dev
    libgcc-s1
    libglib2.0-dev
    libical-dev
    libjack-dev
    libjack0
    libopenblas-dev
    libopenjp2-7
    libreadline-dev
    libstdc++6
    libtiff6
    libtool
    libudev-dev
    libusb-dev
    make
    python3
    python3-pip
    python3-numpy
    ruby
    scons
    sqlite3
    swig
    virtualenv
)
sudo apt-get install --fix-broken -y ${PACKAGES[*]}

sudo sed -i '$ a\dtparam=spi=on' /boot/firmware/config.txt

echo 'blacklist snd_bcm2835' | sudo tee -a /etc/modprobe.d/snd-blacklist.conf > /dev/null
sudo sed -i 's/dtparam=audio=on/#dtparam=audio=on/' /boot/firmware/config.txt

sudo raspi-config nonint do_boot_behaviour B2


RELEASES_URL="https://rbvwhyry.github.io/key2play/releases.json"
LATEST_RELEASE_FILENAME="$(curl "${RELEASES_URL}" | jq '.[]' | sort -r | head -n 1 | tr -d '"')"
LATEST_RELEASE="${LATEST_RELEASE_FILENAME%.zip}"


TEMPFILE="$(mktemp "${LATEST_RELEASE_FILENAME}.XXXXXXXXX")"
curl "https://rbvwhyry.github.io/key2play/${LATEST_RELEASE_FILENAME}" -o "${TEMPFILE}"
unzip -d "${LATEST_RELEASE}" "${TEMPFILE}" # unzip into  $HOME/LATEST_RELEASE
if [ -d key2play ]; then
    rm -rf key2play
fi;
mv "${LATEST_RELEASE}" key2play

sudo chown -R $USER:$USER ./key2play
sudo chmod -R a+rwx ./key2play

pushd key2play

if [ ! -d venv ]; then
    virtualenv --system-site-packages venv
fi;

venv/bin/pip3 install -r requirements.txt

sudo tee /lib/systemd/system/key2play.service > /dev/null << 'EOF'
[Unit]
Description=key2play
After=network-online.target
Wants=network-online.target

[Install]
WantedBy=multi-user.target

[Service]
WorkingDirectory=/home/key2play/key2play
ExecStart=sudo /home/key2play/key2play/venv/bin/python3 -u /home/key2play/key2play/visualizer.py
Restart=always
Type=simple
User=key2play
Group=key2play
StandardError=journal
StandardOutput=journal
StandardInput=null
EOF

sudo systemctl daemon-reload
sudo systemctl enable key2play.service
sudo systemctl start key2play.service
sudo chmod a+rwxX -R /home/key2play/key2play/

echo "installation complete, rebooting"
sleep 5
sudo shutdown -r now
