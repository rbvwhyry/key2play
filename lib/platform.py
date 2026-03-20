import filecmp
import json
import os
import re
import socket
import subprocess
import time
from collections import defaultdict
from shutil import copyfile

from lib.log_setup import logger


class PlatformBase:
    def __getattr__(self, name):
        def method(*args, **kwargs):
            return False, f"Method '{name}' is not supported on this platform", ""

        return method


class PlatformNull(PlatformBase):
    def __getattr__(self, name):
        return self.pass_func

    def pass_func(self, *args, **kwargs):
        pass


class PlatformRasp(PlatformBase):
    cached_scan_results = []  #cached WiFi scan from before hotspot started; single-radio Pi can't scan in AP mode

    def __init__(self, appconfig):
        self.appconfig = appconfig

    @staticmethod
    def ensure_hostname(name="ami"):
        """Sets the Pi's hostname so it's reachable at name.local via mDNS."""
        try:
            current = subprocess.check_output(["hostname"], text=True).strip()

            if current == name:
                return

            logger.info(f"Setting hostname to {name} (was {current})")
            subprocess.run(["sudo", "hostnamectl", "set-hostname", name], check=True)

            with open("/etc/hosts", "r") as f:
                lines = f.readlines()

            with open("/etc/hosts", "w") as f:
                for line in lines:
                    if "127.0.1.1" in line:
                        f.write(f"127.0.1.1\t{name}\n")
                    else:
                        f.write(line)

            subprocess.run(["sudo", "systemctl", "restart", "avahi-daemon"], check=True)
            logger.info(f"Hostname set to {name}.local")

        except Exception as e:
            logger.warning(f"Failed to set hostname: {e}")
    
    @staticmethod
    def check_and_enable_spi():
        try:
            # Check if SPI is enabled by looking for spidev in /dev
            if not os.path.exists("/dev/spidev0.0"):
                logger.info("SPI is not enabled. Enabling SPI interface...")
                subprocess.run(
                    ["sudo", "raspi-config", "nonint", "do_spi", "0"], check=True
                )
                logger.info(
                    "SPI has been enabled. A reboot may be required for changes to take effect."
                )
                return False
            return True
        except subprocess.CalledProcessError as e:
            logger.warning(f"Failed to enable SPI: {e}")
            return False
        except Exception as e:
            logger.warning(f"Error checking SPI status: {e}")
            return False

    @staticmethod
    def disable_system_midi_scripts():
        """Disable udev rules and systemd service that run the old connectall script"""
        try:
            # Disable the udev rule
            udev_rule_path = "/etc/udev/rules.d/33-midiusb.rules"
            if os.path.exists(udev_rule_path):
                logger.info("Disabling udev MIDI rule...")
                # Rename the file to disable it
                os.rename(udev_rule_path, udev_rule_path + ".disabled")
                subprocess.call(["sudo", "udevadm", "control", "--reload"], check=False)
                logger.info("udev MIDI rule disabled")

            # Disable the systemd service
            service_name = "midi.service"
            try:
                # Stop the service
                subprocess.call(
                    ["sudo", "systemctl", "stop", service_name], check=False
                )
                # Disable the service
                subprocess.call(
                    ["sudo", "systemctl", "disable", service_name], check=False
                )
                logger.info(f"Systemd service {service_name} disabled")
            except:
                logger.info(f"Could not disable systemd service {service_name}")

        except Exception as e:
            logger.warning(f"Error disabling system MIDI scripts: {e}")

    def install_midi2abc(self):
        if not self.is_package_installed("abcmidi"):
            logger.info("Installing abcmidi")
            subprocess.call(["sudo", "apt-get", "install", "abcmidi", "-y"])

    @staticmethod
    def update_visualizer():
        call("sudo git reset --hard HEAD", shell=True)
        call("sudo git checkout .", shell=True)
        call(
            "sudo git clean -fdx -e Songs_User_Upload/ -e "
            "config/settings.xml -e config/wpa_disable_ap.conf -e visualizer.log",
            shell=True,
        )
        call("sudo git clean -fdx cache", shell=True)
        call("sudo git pull origin master", shell=True)
        call("sudo pip install -r requirements.txt", shell=True)

    @staticmethod
    def shutdown():
        call("sudo /sbin/shutdown -h now", shell=True)

    @staticmethod
    def reboot():
        call("sudo /sbin/reboot now", shell=True)

    @staticmethod
    def restart_visualizer():
        call("sudo systemctl restart visualizer", shell=True)

    @staticmethod
    def restart_rtpmidid():
        call("sudo systemctl restart rtpmidid", shell=True)

    @staticmethod
    def is_package_installed(package_name):
        try:
            # Run the 'dpkg' command to check if the package is installed
            result = subprocess.run(
                ["dpkg", "-s", package_name],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                text=True,
            )
            output = result.stdout
            status_line = [
                line for line in output.split("\n") if line.startswith("Status:")
            ][0]

            if "install ok installed" in status_line:
                logger.info(f"{package_name} package is installed")
                return True
            else:
                logger.info(f"{package_name} package is not installed")
                return False
        except subprocess.CalledProcessError:
            logger.warning(f"Error checking {package_name} package status")
            return False

    @staticmethod
    def create_hotspot_profile():
        check_profile = subprocess.run(
            ["sudo", "nmcli", "connection", "show", "ami-hotspot"],
            capture_output=True,
            text=True,
        )

        if "ami-hotspot" in check_profile.stdout:
            logger.info("ami-hotspot profile already exists. Skipping creation.")
            return

        # clean up old profiles and dnsmasq config from previous versions
        subprocess.run(["sudo", "nmcli", "connection", "delete", "key2play-hotspot"], capture_output=True)
        old_conf = "/etc/dnsmasq.d/captive.conf"
        if os.path.exists(old_conf):
            subprocess.run(["sudo", "rm", "-f", old_conf], capture_output=True)
            subprocess.run(["sudo", "systemctl", "stop", "dnsmasq"], capture_output=True)
            subprocess.run(["sudo", "systemctl", "disable", "dnsmasq"], capture_output=True)
            logger.info("Cleaned up old dnsmasq captive portal config")

        logger.info("Creating new ami-hotspot profile...")

        try:
            subprocess.run(
                [
                    "sudo",
                    "nmcli",
                    "connection",
                    "add",
                    "type",
                    "wifi",
                    "ifname",
                    "wlan0",
                    "con-name",
                    "ami-hotspot",
                    "autoconnect",
                    "no",
                    "ssid",
                    "ami",
                ],
                check=True,
            )

            subprocess.run(
                [
                    "sudo",
                    "nmcli",
                    "connection",
                    "modify",
                    "ami-hotspot",
                    "802-11-wireless.mode",
                    "ap",
                    "802-11-wireless.band",
                    "bg",
                    "ipv4.method",
                    "shared",
                    "ipv4.address",
                    "10.42.0.1/24",
                ],
                check=True,
            )

            logger.info("ami-hotspot profile created successfully")
        except subprocess.CalledProcessError as e:
            logger.warning(
                f"An error occurred while creating the ami-hotspot profile: {e}"
            )

    @staticmethod
    def enable_hotspot():
        logger.info("Enabling ami-hotspot")

        #scan for networks BEFORE starting the hotspot — single-radio Pi can't scan in AP mode
        logger.info("Pre-scanning WiFi networks before hotspot start...")
        PlatformRasp.cached_scan_results = PlatformRasp.scan_wifi_networks()
        logger.info(f"Cached {len(PlatformRasp.cached_scan_results)} networks")

        #write the captive portal DNS config BEFORE starting the hotspot so NM's dnsmasq picks it up on launch
        nm_dnsmasq_dir = "/etc/NetworkManager/dnsmasq-shared.d"
        os.makedirs(nm_dnsmasq_dir, exist_ok=True)

        with open(os.path.join(nm_dnsmasq_dir, "captive.conf"), "w") as f:
            f.write("address=/#/10.42.0.1\n")

        subprocess.run(["sudo", "nmcli", "connection", "down", "preconfigured"])
        subprocess.run(["sudo", "nmcli", "connection", "up", "ami-hotspot"])

        #iptables rules go after the interface is up
        PlatformRasp.enable_captive_portal()

    @staticmethod
    def disable_hotspot():
        logger.info("Disabling ami-hotspot")
        PlatformRasp.disable_captive_portal()
        subprocess.run(["sudo", "nmcli", "connection", "down", "ami-hotspot"])

    @staticmethod
    def enable_captive_portal():
        """Redirects all HTTP traffic to the Pi using iptables so phones auto-open the app."""
        try:
            subprocess.run(["sudo", "iptables", "-t", "nat", "-F", "PREROUTING"], capture_output=True)

            subprocess.run([
                "sudo", "iptables", "-t", "nat", "-A", "PREROUTING",
                "-i", "wlan0", "-p", "udp", "--dport", "53",
                "-j", "DNAT", "--to-destination", "10.42.0.1:53"
            ], check=True)

            subprocess.run([
                "sudo", "iptables", "-t", "nat", "-A", "PREROUTING",
                "-i", "wlan0", "-p", "tcp", "--dport", "80",
                "-j", "DNAT", "--to-destination", "10.42.0.1:80"
            ], check=True)

            subprocess.run([
                "sudo", "iptables", "-t", "nat", "-A", "PREROUTING",
                "-i", "wlan0", "-p", "tcp", "--dport", "443",
                "-j", "DNAT", "--to-destination", "10.42.0.1:80"
            ], check=True)

            logger.info("Captive portal enabled (iptables)")

        except Exception as e:
            logger.warning(f"Failed to enable captive portal: {e}")

    @staticmethod
    def disable_captive_portal():
        """Removes the captive portal iptables rules and DNS redirect."""
        try:
            subprocess.run(["sudo", "iptables", "-t", "nat", "-F", "PREROUTING"], capture_output=True)

            captive_conf = "/etc/NetworkManager/dnsmasq-shared.d/captive.conf"

            if os.path.exists(captive_conf):
                os.remove(captive_conf)

            logger.info("Captive portal disabled")

        except Exception as e:
            logger.warning(f"Failed to disable captive portal: {e}")
    
    @staticmethod
    def get_current_connections():
        try:
            with open(os.devnull, "w") as null_file:
                output = subprocess.check_output(
                    ["iwconfig"], text=True, stderr=null_file
                )

            if "Mode:Master" in output:
                return False, "Running as hotspot", ""

            for line in output.split("\n"):
                if "ESSID:" in line:
                    ssid = line.split("ESSID:")[-1].strip().strip('"')
                    if ssid != "off/any":
                        access_point_line = [
                            line
                            for line in output.split("\n")
                            if "Access Point:" in line
                        ]
                        if access_point_line:
                            access_point = (
                                access_point_line[0].split("Access Point:")[1].strip()
                            )
                            return True, ssid, access_point
                        return False, "Not connected to any Wi-Fi network.", ""
                    return False, "Not connected to any Wi-Fi network.", ""

            return False, "No Wi-Fi interface found.", ""
        except subprocess.CalledProcessError:
            return False, "Error occurred while getting Wi-Fi information.", ""

    def is_hotspot_running(self):
        try:
            result = subprocess.run(
                ["nmcli", "connection", "show", "--active"],
                capture_output=True,
                text=True,
            )
            return "ami-hotspot" in result.stdout
        except Exception as e:
            logger.warning(f"Error checking hotspot status: {str(e)}")
            return False

    def manage_hotspot(self, usersettings, midiports, first_run=False):
        if first_run:
            self.create_hotspot_profile()
            if int(usersettings.get("is_hotspot_active")):
                if not self.is_hotspot_running():
                    logger.info(
                        "ami-hotspot is enabled in settings but not running. Starting hotspot..."
                    )
                    self.enable_hotspot()
                    time.sleep(5)

                    if self.is_hotspot_running():
                        logger.info("ami-hotspot started successfully")
                    else:
                        logger.warning("Failed to start hotspot")
                else:
                    logger.info("ami-hotspot is already running")

        # if we're supposed to be connected to a wifi, but we aren't:
        # eventually turn on hotspot mode
        if (
            not int(usersettings.get("is_hotspot_active"))
            and not self.check_if_connected_to_wifi()
        ):
            time.sleep(10)
            if self.check_if_connected_to_wifi():
                return
            time.sleep(10)
            if self.check_if_connected_to_wifi():
                return
            self.enable_hotspot()

    def check_if_connected_to_wifi(self) -> bool:
        try:
            json_str = subprocess.check_output(
                ["ip", "-j", "addr", "show", "dev", "wlan0"]
            )
            pydict = json.loads(json_str)
            ip = pydict[0]["addr_info"][0]["local"]
            if ip is not None and not ip.startswith("169.254"):
                return True
            else:
                return False
        except Exception as e:
            logger.error(f"error checking wlan0 IP address, {str(e)}")
            return False

    def connect_to_wifi(self, ssid, password, usersettings):
        # Disable the hotspot first
        self.disable_hotspot()

        try:
            result = subprocess.run(
                [
                    "sudo",
                    "nmcli",
                    "device",
                    "wifi",
                    "connect",
                    ssid,
                    "password",
                    password,
                ],
                capture_output=True,
                text=True,
                timeout=30,  # Set a timeout for the connection attempt
            )
            # Check if the connection was successful
            if result.returncode == 0:
                logger.info(f"Successfully connected to {ssid}")
                usersettings.change_setting_value("is_hotspot_active", 0)
                return True
            else:
                logger.warning(f"Failed to connect to {ssid}. Error: {result.stderr}")
                usersettings.change_setting_value("is_hotspot_active", 1)
                self.enable_hotspot()
                return False

        except subprocess.TimeoutExpired:
            logger.warning(f"Connection attempt to {ssid} timed out")
            usersettings.change_setting_value("is_hotspot_active", 1)
            self.enable_hotspot()
            return False
        except Exception as e:
            logger.warning(f"An error occurred while connecting to {ssid}: {str(e)}")
            usersettings.change_setting_value("is_hotspot_active", 1)
            self.enable_hotspot()
            return False

    def disconnect_from_wifi(self, usersettings):
        logger.info("Disconnecting from wifi")
        self.enable_hotspot()
        usersettings.change_setting_value("is_hotspot_active", 1)

    @staticmethod
    def get_wifi_networks():
        try:
            output = subprocess.check_output(
                ["sudo", "iwlist", "wlan0", "scan"], stderr=subprocess.STDOUT
            )
            networks = output.decode().split("Cell ")

            def calculate_signal_strength(level):
                # Map the signal level to a percentage (0% to 100%) linearly.
                # -50 dBm or higher -> 100%
                # -90 dBm or lower -> 0%
                if level >= -50:
                    return 100
                elif level <= -90:
                    return 0
                else:
                    return 100 - (100 / 40) * (level + 90)

            wifi_dict = defaultdict(
                lambda: {"Signal Strength": -float("inf"), "Signal dBm": -float("inf")}
            )

            for network in networks[1:]:
                wifi_data = {}

                address_line = [
                    line for line in network.split("\n") if "Address:" in line
                ]
                if address_line:
                    wifi_data["Address"] = address_line[0].split("Address:")[1].strip()

                ssid_line = [line for line in network.split("\n") if "ESSID:" in line]
                if ssid_line:
                    ssid = ssid_line[0].split("ESSID:")[1].strip('"')
                    wifi_data["ESSID"] = ssid

                freq_line = [
                    line for line in network.split("\n") if "Frequency:" in line
                ]
                if freq_line:
                    wifi_data["Frequency"] = (
                        freq_line[0].split("Frequency:")[1].split(" (")[0]
                    )

                signal_line = [
                    line for line in network.split("\n") if "Signal level=" in line
                ]
                if signal_line:
                    signal_dbm = int(
                        signal_line[0].split("Signal level=")[1].split(" dBm")[0]
                    )
                    signal_strength = calculate_signal_strength(signal_dbm)
                    wifi_data["Signal Strength"] = signal_strength
                    wifi_data["Signal dBm"] = signal_dbm

                # Update the network info if this is the strongest signal for this SSID
                if wifi_data["Signal Strength"] > wifi_dict[ssid]["Signal Strength"]:
                    wifi_dict[ssid].update(wifi_data)

            # Convert the dictionary to a list
            wifi_list = list(wifi_dict.values())

            # Sort descending by "Signal Strength"
            wifi_list.sort(key=lambda x: x["Signal Strength"], reverse=True)

            return wifi_list
        except subprocess.CalledProcessError as e:
            logger.warning(f"Error while scanning Wi-Fi networks: {e.output}")
            return []

    @staticmethod
    def scan_wifi_networks():
        """Scans for nearby WiFi networks using nmcli. Returns a sorted list of dicts."""
        try:
            #check if we're in AP mode — if so, return cached results since single-radio can't scan
            check_ap = subprocess.run(
                ["nmcli", "-t", "-f", "WIFI-PROPERTIES.AP", "dev", "show", "wlan0"],
                capture_output=True, text=True, timeout=5
            )

            #try a rescan; will silently fail in AP mode but that's ok
            subprocess.run(["nmcli", "dev", "wifi", "rescan"], capture_output=True, timeout=10)
            time.sleep(2)

            output = subprocess.check_output(
                ["nmcli", "-t", "-f", "SSID,SIGNAL,SECURITY,BARS", "dev", "wifi", "list"],
                text=True, timeout=15
            )

            networks = {}

            for line in output.strip().split("\n"):
                if not line.strip():
                    continue

                parts = line.split(":")
                if len(parts) < 4:
                    continue

                ssid = parts[0].strip()
                if not ssid or ssid == "--" or ssid == "ami":
                    continue

                signal = int(parts[1]) if parts[1].isdigit() else 0
                security = parts[2].strip()
                bars = parts[3].strip()

                if ssid not in networks or signal > networks[ssid]["signal"]:
                    networks[ssid] = {
                        "ssid": ssid,
                        "signal": signal,
                        "security": security,
                        "bars": bars,
                        "is_open": security == "" or security == "--"
                    }

            result = sorted(networks.values(), key=lambda n: n["signal"], reverse=True)

            if result:
                PlatformRasp.cached_scan_results = result  #update cache with fresh results
                return result

            #no live results (probably in AP mode) — return cached
            if PlatformRasp.cached_scan_results:
                logger.info(f"Returning {len(PlatformRasp.cached_scan_results)} cached scan results (AP mode)")
                return PlatformRasp.cached_scan_results

            return []

        except Exception as e:
            logger.warning(f"Error scanning WiFi networks: {e}")

            #return cached on error too
            if PlatformRasp.cached_scan_results:
                return PlatformRasp.cached_scan_results

            return []

    @staticmethod
    def forget_all_wifi():
        """Deletes all saved WiFi connections from NetworkManager except the hotspot."""
        forgotten = []

        try:
            output = subprocess.check_output(
                ["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"],
                text=True
            )

            for line in output.strip().split("\n"):
                parts = line.split(":")

                if len(parts) >= 2 and parts[1] == "802-11-wireless" and parts[0] != "ami-hotspot":
                    subprocess.run(["sudo", "nmcli", "connection", "delete", parts[0]])
                    forgotten.append(parts[0])
                    logger.info(f"Forgot WiFi network: {parts[0]}")

        except Exception as e:
            logger.warning(f"Error forgetting WiFi networks: {e}")

        return forgotten
    
    @staticmethod
    def get_local_address():
        try:
            # Get the hostname
            hostname = socket.gethostname()

            # Get the IP address
            ip_address = socket.gethostbyname(hostname + ".local")

            # Construct the full local address
            local_address = f"{hostname}.local"

            return {
                "success": True,
                "local_address": local_address,
                "ip_address": ip_address,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def change_local_address(new_name):
        new_name = new_name.rstrip(".local")
        logger.info("Changing local address to " + new_name)
        # Validate the new name
        if not re.match(r"^[a-zA-Z0-9-]+$", new_name):
            raise ValueError("Invalid name. Use only letters, numbers, and hyphens.")

        try:
            # Change the hostname
            subprocess.run(
                ["sudo", "hostnamectl", "set-hostname", new_name], check=True
            )

            # Update /etc/hosts file
            with open("/etc/hosts", "r") as file:
                hosts_content = file.readlines()

            with open("/etc/hosts", "w") as file:
                for line in hosts_content:
                    if "127.0.1.1" in line:
                        file.write(f"127.0.1.1\t{new_name}\n")
                    else:
                        file.write(line)

            # Restart avahi-daemon to apply changes
            subprocess.run(["sudo", "systemctl", "restart", "avahi-daemon"], check=True)

            # Optionally, restart the networking service
            subprocess.run(["sudo", "systemctl", "restart", "networking"], check=True)

            logger.info(f"Local address successfully changed to {new_name}.local")
            return True

        except subprocess.CalledProcessError as e:
            logger.warning(f"An error occurred while changing the local address: {e}")
            return False
        except IOError as e:
            logger.warning(f"An error occurred while updating the hosts file: {e}")
            return False
        except Exception as e:
            logger.warning(f"An unexpected error occurred: {e}")
            return False
