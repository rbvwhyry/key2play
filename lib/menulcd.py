import time


class MenuLCD:
    def __init__(
        self,
        xml_file_name,
        args,
        usersettings,
        ledsettings,
        ledstrip,
        learning,
        midiports,
        hotspot,
        platform,
    ):
        self.list_count = None
        self.parent_menu = None
        self.current_choice = None
        self.draw = None
        self.t = None
        self.usersettings = usersettings
        self.ledsettings = ledsettings
        self.ledstrip = ledstrip
        self.learning = learning
        self.midiports = midiports
        self.hotspot = hotspot
        self.platform = platform
        self.args = args
        self.scroll_hold = 0
        self.cut_count = 0
        self.pointer_position = 0
        self.background_color = usersettings.get_setting_value("background_color")
        self.text_color = usersettings.get_setting_value("text_color")
        self.update_songs()
        self.update_ports()
        self.update_led_note_offsets()
        self.speed_multiplier = 1

        self.screensaver_settings = dict()
        self.screensaver_settings["time"] = usersettings.get_setting_value("time")
        self.screensaver_settings["date"] = usersettings.get_setting_value("date")
        self.screensaver_settings["cpu_chart"] = usersettings.get_setting_value(
            "cpu_chart"
        )
        self.screensaver_settings["cpu"] = usersettings.get_setting_value("cpu")
        self.screensaver_settings["ram"] = usersettings.get_setting_value("ram")
        self.screensaver_settings["temp"] = usersettings.get_setting_value("temp")
        self.screensaver_settings["network_usage"] = usersettings.get_setting_value(
            "network_usage"
        )
        self.screensaver_settings["sd_card_space"] = usersettings.get_setting_value(
            "sd_card_space"
        )
        self.screensaver_settings["local_ip"] = usersettings.get_setting_value(
            "local_ip"
        )

        self.screensaver_delay = usersettings.get_setting_value("screensaver_delay")
        self.screen_off_delay = usersettings.get_setting_value("screen_off_delay")
        self.led_animation_delay = usersettings.get_setting_value("led_animation_delay")

        self.led_animation = usersettings.get_setting_value("led_animation")

        self.screen_on = int(usersettings.get_setting_value("screen_on"))

        self.screen_status = 1

        self.screensaver_is_running = False
        self.last_activity = time.time()
        self.is_idle_animation_running = False
        self.is_animation_running = False

    def rotate_image(self, image):
        return None

    def toggle_screensaver_settings(self, setting):
        return None

    def update_songs(self):
        return None

    def update_colormap(self):
        return None

    def update_sequence_list(self):
        return None

    def update_ports(self):
        return None

    def update_led_note_offsets(self):
        return None

    def update_multicolor(self, colors_list):
        return None

    def scale(self, size):
        return None

    def disable_screen(self):
        return None

    def enable_screen(self):
        return None

    def show(self, position="default", back_pointer_location=None):
        return None

    def change_pointer(self, direction):
        return None

    def enter_menu(self):
        return None

    def go_back(self):
        return None

    def render_message(self, title, message, delay=500):
        return None

    def render_screensaver(
        self,
        hour,
        date,
        cpu,
        cpu_average,
        ram,
        temp,
        cpu_history=None,
        upload=0,
        download=0,
        card_space=None,
        local_ip="0.0.0.0",
    ):
        return None

    def change_settings(self, choice, location):
        return None

    def change_value(self, value):
        return None

    def speed_change(self):
        return None
