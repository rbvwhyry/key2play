Install [Raspberry Pi OS Lite](https://www.raspberrypi.org/software/) on your SD card.

If you are not able to connect your monitor, mouse and keyboard to RPi you can connect to it using SSH over [Wi-Fi](https://github.com/rbvwhyry/key2play/blob/main/Docs/wifi_setup.md)

Run installation script:

`sudo bash -c "$(curl -fsSL https://raw.githubusercontent.com/rbvwhyry/key2play/main/autoinstall.sh)"`

**or follow those steps:**
 
### 1. **Updating OS** 
After succesfully booting RPi (and connecting to it by SSH if necessary) we need to make sure that everything is up to date.
- `sudo apt-get update`
- `sudo apt-get upgrade` //*it will take a while, go grab a coffee*


### 2. **Creating autoconnect script** ### 
*You can skip this part if you don't plan to connect any MIDI device other than a piano.*
- Create `connectall.py` file

 `sudo nano /usr/local/bin/connectall.py`
- paste the script:
```python
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
            #print("aconnect %s %s" % (source, target))
            subprocess.call("aconnect %s %s" % (source, target), shell=True)
```
Press CTRL + O to save file, confirm with enter and CTRL + X to exit editor.
- Change permissions:

    `sudo chmod +x /usr/local/bin/connectall.py`

- Make the script launch on USB connect:

   ` sudo nano /etc/udev/rules.d/33-midiusb.rules`

- Paste and save:

    `ACTION=="add|remove", SUBSYSTEM=="usb", DRIVER=="usb", RUN+="/usr/local/bin/connectall.py"  `

- Reload services:

   ` sudo udevadm control --reload`

    `sudo service udev restart`
- Open file

    `sudo nano /lib/systemd/system/midi.service`
- Paste and save:
```bash
[Unit]
Description=Initial USB MIDI connect

[Service]
ExecStart=/usr/local/bin/connectall.py

[Install]
WantedBy=multi-user.target
```

- Reload daemon and enable service:

   ` sudo systemctl daemon-reload`
   
   ` sudo systemctl enable midi.service`
    
   `sudo systemctl start midi.service`
    

###  3. **Enabling SPI interface** ### 
 - Here you can find instruction: [Enable SPI Interface on the Raspberry Pi](https://www.raspberrypi-spy.co.uk/2014/08/enabling-the-spi-interface-on-the-raspberry-pi/)


### 4. **Installing packages** //*ready for another cup?* ### 

```bash
sudo apt-get install -y ruby git python3-pip autotools-dev libtool autoconf libasound2-dev libusb-dev libdbus-1-dev libglib2.0-dev libudev-dev libical-dev libreadline-dev python-dev libatlas-base-dev libopenjp2-7 libtiff5 libjack0 libjack-dev libasound2-dev fonts-freefont-ttf gcc make build-essential python-dev git scons swig libavahi-client3 abcmidi dnsmasq hostapd
```


### 5. **Disabling audio output** ### 

    sudo nano /etc/modprobe.d/snd-blacklist.conf
- paste and save:

    `blacklist snd_bcm2835`
- And one more file:

    `sudo nano /boot/config.txt`
- Change `dtparam=audio=on` to `#dtparam=audio=on`

- Reboot RPi

`sudo reboot`


### 6. **Installing RTP-midi server** (optional) ### 
*This part is not needed if you're not going to connect your RPi to PC.*

We are going to use  [RTP MIDI User Space Driver Daemon for Linux](https://github.com/davidmoreno/rtpmidid/releases)
- Navigate to /home folder:

` cd /home/`   
- Download deb package:

`sudo wget https://github.com/davidmoreno/rtpmidid/releases/download/v21.11/rtpmidid_21.11_armhf.deb`
- Install package

`sudo dpkg -i rtpmidid_21.11_armhf.deb`

### 7. **Creating Hot-Spot** ###

*based on https://github.com/schollz/raspberry-pi-turnkey*

`echo -e "auto wlan0\niface wlan0 inet manual\nwpa-conf /etc/wpa_supplicant/wpa_supplicant.conf" | sudo tee -a /etc/network/interfaces > /dev/null`

`sudo systemctl stop dnsmasq && sudo systemctl stop hostapd`

`echo 'interface wlan0
static ip_address=192.168.4.1/24' | sudo tee --append /etc/dhcpcd.conf`

`sudo mv /etc/dnsmasq.conf /etc/dnsmasq.conf.orig`

`sudo systemctl daemon-reload`

`sudo systemctl restart dhcpcd`

`echo 'interface=wlan0
dhcp-range=192.168.4.2,192.168.4.20,255.255.255.0,24h' | sudo tee --append /etc/dnsmasq.conf`

`echo 'interface=wlan0
driver=nl80211
ssid=key2play
hw_mode=g
channel=7
wmm_enabled=0
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=playkey
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP' | sudo tee --append /etc/hostapd/hostapd.conf`

`echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' | sudo tee --append /etc/default/hostapd`

`echo '
auto wlan0
iface wlan0 inet manual
wpa-conf /etc/wpa_supplicant/wpa_supplicant.conf' | sudo tee --append /etc/network/interfaces`

`sudo systemctl start hostapd && sudo systemctl start dnsmasq`


### 8. **Installing key2play** ###
- Navigate to /home folder:

` cd /home/`

- GIT clone repository

`sudo git clone https://github.com/rbvwhyry/key2play`

`cd key2play`
- Install required libraries

`sudo pip3 install -r requirements.txt`
- Enable autologin on boot

`sudo raspi-config`

`Select "System options" then “Boot / Auto Login” then “Console Autologin” `
- Enable autostart script on boot:

`sudo nano /lib/systemd/system/visualizer.service`

Paste and save:

```bash
[Unit]
Description=key2play
After=network-online.target
Wants=network-online.target

[Install]
WantedBy=multi-user.target

[Service]
ExecStart=sudo python3 /home/key2play/visualizer.py
Restart=always
Type=simple
User=pi
Group=pi
```

*If you are using WaveShare 1.3inch 240x240 LED Hat instead of 1.44inch 128x128, edit accordingly:*
`ExecStart=sudo python3 /home/key2play/visualizer.py --display 1in3`

*If you want to use your RPi upside down add `--rotatescreen true` :*

`ExecStart=sudo python3 /home/key2play/visualizer.py --rotatescreen true`

- Reload daemon and enable service:

   ` sudo systemctl daemon-reload`
   
   ` sudo systemctl enable visualizer.service`
    
   `sudo systemctl start visualizer.service`


- Change permissions:

  `sudo chmod a+rwxX -R /home/key2play/`

Now you can type `sudo reboot` to test if everything works. After 1-3 minutes you should see Visualizer menu on RPi screen.
