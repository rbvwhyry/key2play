import ast

from lib.functions import clamp, fastColorWipe, find_between
from lib.rpi_drivers import Color
from lib.usersettings import UserSettings


class LedSettings:
    def __init__(self, config, usersettings: UserSettings):
        self.step_number = None
        self.sequence_active_name = None
        self.count_steps = None
        self.control_number = None
        self.next_step = None
        self.sequences_tree = None
        self.ledstrip = None
        self.menu = None
        self.usersettings: UserSettings = usersettings
        self.config = config

        self.red = int(usersettings.get_setting_value("red"))
        self.green = int(usersettings.get_setting_value("green"))
        self.blue = int(usersettings.get_setting_value("blue"))
        self.mode = usersettings.get_setting_value("mode")
        self.fadingspeed = int(usersettings.get_setting_value("fadingspeed"))
        self.fadepedal_notedrop = int(
            usersettings.get_setting_value("fadepedal_notedrop")
        )
        self.color_mode = usersettings.get_setting_value("color_mode")
        self.rainbow_offset = int(usersettings.get_setting_value("rainbow_offset"))
        self.rainbow_scale = int(usersettings.get_setting_value("rainbow_scale"))
        self.rainbow_timeshift = int(
            usersettings.get_setting_value("rainbow_timeshift")
        )
        self.rainbow_colormap = usersettings.get_setting_value("rainbow_colormap")
        self.velocityrainbow_offset = int(
            usersettings.get_setting_value("velocityrainbow_offset")
        )
        self.velocityrainbow_scale = int(
            usersettings.get_setting_value("velocityrainbow_scale")
        )
        self.velocityrainbow_curve = int(
            usersettings.get_setting_value("velocityrainbow_curve")
        )
        self.velocityrainbow_colormap = usersettings.get_setting_value(
            "velocityrainbow_colormap"
        )

        self.multicolor = ast.literal_eval(usersettings.get_setting_value("multicolor"))
        self.multicolor_range = ast.literal_eval(
            usersettings.get_setting_value("multicolor_range")
        )
        self.multicolor_index = 0
        self.multicolor_iteration = ast.literal_eval(
            usersettings.get_setting_value("multicolor_iteration")
        )

        self.sequence_active = usersettings.get_setting_value("sequence_active")

        self.backlight_brightness = int(
            usersettings.get_setting_value("backlight_brightness")
        )
        self.backlight_brightness_percent = int(
            usersettings.get_setting_value("backlight_brightness_percent")
        )
        self.disable_backlight_on_idle = usersettings.get_setting_value(
            "disable_backlight_on_idle"
        )
        self.backlight_stopped = False

        self.led_animation_brightness_percent = int(
            usersettings.get_setting_value("led_animation_brightness_percent")
        )

        self.backlight_red = int(usersettings.get_setting_value("backlight_red"))
        self.backlight_green = int(usersettings.get_setting_value("backlight_green"))
        self.backlight_blue = int(usersettings.get_setting_value("backlight_blue"))

        self.adjacent_mode = usersettings.get_setting_value("adjacent_mode")
        self.adjacent_red = int(usersettings.get_setting_value("adjacent_red"))
        self.adjacent_green = int(usersettings.get_setting_value("adjacent_green"))
        self.adjacent_blue = int(usersettings.get_setting_value("adjacent_blue"))

        self.skipped_notes = usersettings.get_setting_value("skipped_notes")

        self.note_offsets = ast.literal_eval(
            usersettings.get_setting_value("note_offsets")
        )

        self.speed_period_in_seconds = 0.8

        self.speed_slowest = {
            "red": int(usersettings.get_setting_value("speed_slowest_red")),
            "green": int(usersettings.get_setting_value("speed_slowest_green")),
            "blue": int(usersettings.get_setting_value("speed_slowest_blue")),
        }

        self.speed_fastest = {
            "red": int(usersettings.get_setting_value("speed_fastest_red")),
            "green": int(usersettings.get_setting_value("speed_fastest_green")),
            "blue": int(usersettings.get_setting_value("speed_fastest_blue")),
        }

        self.speed_period_in_seconds = float(
            usersettings.get_setting_value("speed_period_in_seconds")
        )
        self.speed_max_notes = int(usersettings.get_setting_value("speed_max_notes"))

        self.gradient_start = {
            "red": int(usersettings.get_setting_value("gradient_start_red")),
            "green": int(usersettings.get_setting_value("gradient_start_green")),
            "blue": int(usersettings.get_setting_value("gradient_start_blue")),
        }

        self.gradient_end = {
            "red": int(usersettings.get_setting_value("gradient_end_red")),
            "green": int(usersettings.get_setting_value("gradient_end_green")),
            "blue": int(usersettings.get_setting_value("gradient_end_blue")),
        }

        self.key_in_scale = {
            "red": int(usersettings.get_setting_value("key_in_scale_red")),
            "green": int(usersettings.get_setting_value("key_in_scale_green")),
            "blue": int(usersettings.get_setting_value("key_in_scale_blue")),
        }

        self.key_not_in_scale = {
            "red": int(usersettings.get_setting_value("key_not_in_scale_red")),
            "green": int(usersettings.get_setting_value("key_not_in_scale_green")),
            "blue": int(usersettings.get_setting_value("key_not_in_scale_blue")),
        }

        self.scales = [
            "C",
            "C#",
            "D",
            "Eb",
            "E",
            "F",
            "F#",
            "G",
            "Ab",
            "A",
            "Bb",
            "B",
            "C m",
            "C# m",
            "D m",
            "Eb m",
            "E m",
            "F m",
            "F# m",
            "G m",
            "G# m",
            "A bm",
            "A m",
            "Bb m",
            "B m",
        ]
        self.scale_key = int(usersettings.get_setting_value("scale_key"))

        self.sequence_number = 0

        self.incoming_setting_change = False

        # if self.mode == "Disabled" and self.color_mode != "disabled":
        #    usersettings.change_setting_value("color_mode", "disabled")

    def add_instance(self, menu, ledstrip):
        self.menu = menu
        self.ledstrip = ledstrip
        menu.update_multicolor(self.multicolor)

    def add_note_offset(self):
        self.note_offsets.insert(0, [100, 1])
        self.usersettings.change_setting_value("note_offsets", self.note_offsets)

    def append_note_offset(self):
        self.note_offsets.append([1, 1])
        self.usersettings.change_setting_value("note_offsets", self.note_offsets)

    def del_note_offset(self, slot):
        del self.note_offsets[int(slot) - 1]
        self.usersettings.change_setting_value("note_offsets", self.note_offsets)

    def update_note_offset(self, slot, data):
        pair = data.split(",")
        self.note_offsets[int(slot) - 1][0] = int(pair[0])
        self.note_offsets[int(slot) - 1][1] = int(pair[1])
        self.usersettings.change_setting_value("note_offsets", self.note_offsets)

    def update_note_offset_lcd(self, current_choice, currentlocation, value):
        slot = int(currentlocation.replace("Offset", "")) - 1
        if current_choice == "LED Number":
            self.note_offsets[slot][0] += value
        else:
            self.note_offsets[slot][1] += value
        self.usersettings.change_setting_value("note_offsets", self.note_offsets)

    def addcolor(self):
        self.multicolor.append([0, 255, 0])
        self.multicolor_range.append([20, 108])

        self.usersettings.change_setting_value("multicolor", self.multicolor)
        self.usersettings.change_setting_value(
            "multicolor_range", self.multicolor_range
        )

        self.menu.update_multicolor(self.multicolor)
        self.menu.show()
        self.incoming_setting_change = True

    def deletecolor(self, key):
        del self.multicolor[int(key) - 1]
        del self.multicolor_range[int(key) - 1]

        self.usersettings.change_setting_value("multicolor", self.multicolor)
        self.usersettings.change_setting_value(
            "multicolor_range", self.multicolor_range
        )

        self.menu.update_multicolor(self.multicolor)
        self.menu.go_back()
        self.menu.show()
        self.incoming_setting_change = True

    def change_multicolor(self, choice, location, value):
        self.sequence_active = False
        location = location.replace("RGB_Color", "")
        location = int(location) - 1
        if choice == "Red":
            choice = 0
        elif choice == "Green":
            choice = 1
        else:
            choice = 2
        self.multicolor[int(location)][choice] += int(value)
        self.multicolor[int(location)][choice] = clamp(
            self.multicolor[int(location)][choice], 0, 255
        )

        self.usersettings.change_setting_value("multicolor", self.multicolor)
        self.incoming_setting_change = True

    def change_multicolor_range(self, choice, location, value):
        location = location.replace("Key_range", "")
        location = int(location) - 1
        if choice == "Start":
            choice = 0
        else:
            choice = 1

        self.multicolor_range[int(location)][choice] += int(value)
        self.usersettings.change_setting_value(
            "multicolor_range", self.multicolor_range
        )
        self.incoming_setting_change = True

    def get_multicolors(self, number):
        number = int(number) - 1
        return (
            str(self.multicolor[int(number)][0])
            + ", "
            + str(self.multicolor[int(number)][1])
            + ", "
            + str(self.multicolor[int(number)][2])
        )

    def light_keys_in_range(self, location):
        fastColorWipe(self.ledstrip.strip, True, self)

        color_counter = 0
        for i in self.multicolor:
            start = self.multicolor_range[int(color_counter)][0]
            end = self.multicolor_range[int(color_counter)][1]

            if start > 92:
                note_offset_start = 2
            elif start > 55:
                note_offset_start = 1
            else:
                note_offset_start = 0

            if end > 92:
                note_offset_end = 2
            elif end > 55:
                note_offset_end = 1
            else:
                note_offset_end = 0

            red = self.multicolor[int(color_counter)][0]
            green = self.multicolor[int(color_counter)][1]
            blue = self.multicolor[int(color_counter)][2]

            self.ledstrip.strip.setPixelColor(
                int(((start - 20) * 2 - note_offset_start)),
                Color(int(red), int(green), int(blue)),
            )
            self.ledstrip.strip.setPixelColor(
                int(((end - 20) * 2 - note_offset_end)),
                Color(int(red), int(green), int(blue)),
            )

            color_counter += 1

    def change_color(self, color, value):
        self.sequence_active = False
        self.usersettings.change_setting_value("sequence_active", self.sequence_active)
        self.color_mode = "Single"
        self.usersettings.change_setting_value("color_mode", self.color_mode)
        if color == "Red":
            if 255 >= self.red >= 0:
                self.red += int(value)
                self.red = clamp(self.red, 0, 255)
                self.usersettings.change_setting_value("red", self.red)
        elif color == "Green":
            if 255 >= self.green >= 0:
                self.green += int(value)
                self.green = clamp(self.green, 0, 255)
                self.usersettings.change_setting_value("green", self.green)
        elif color == "Blue":
            if 255 >= self.blue >= 0:
                self.blue += int(value)
                self.blue = clamp(self.blue, 0, 255)
                self.usersettings.change_setting_value("blue", self.blue)
        self.incoming_setting_change = True

    def change_color_name(self, color):
        self.sequence_active = False
        self.usersettings.change_setting_value("sequence_active", self.sequence_active)
        self.color_mode = "Single"
        self.usersettings.change_setting_value("color_mode", self.color_mode)
        self.red = int(find_between(str(color), "red=", ","))
        self.green = int(find_between(str(color), "green=", ","))
        self.blue = int(find_between(str(color), "blue=", ")"))

        self.usersettings.change_setting_value("red", self.red)
        self.usersettings.change_setting_value("green", self.green)
        self.usersettings.change_setting_value("blue", self.blue)

    def get_color(self, color):
        if color == "Red":
            return self.red
        elif color == "Green":
            return self.green
        elif color == "Blue":
            return self.blue

    def get_colors(self):
        return str(self.red) + ", " + str(self.green) + ", " + str(self.blue)

    def get_backlight_color(self, color):
        if color == "Red":
            return self.backlight_red
        elif color == "Green":
            return self.backlight_green
        elif color == "Blue":
            return self.backlight_blue

    def get_backlight_colors(self):
        return (
            str(self.backlight_red)
            + ", "
            + str(self.backlight_green)
            + ", "
            + str(self.backlight_blue)
        )

    def get_adjacent_color(self, color):
        if color == "Red":
            return self.adjacent_red
        elif color == "Green":
            return self.adjacent_green
        elif color == "Blue":
            return self.adjacent_blue

    def get_adjacent_colors(self):
        return (
            str(self.adjacent_red)
            + ", "
            + str(self.adjacent_green)
            + ", "
            + str(self.adjacent_blue)
        )

    def change_backlight_brightness(self, value):
        self.backlight_brightness_percent += value
        self.backlight_brightness_percent = clamp(
            self.backlight_brightness_percent, 0, 100
        )
        self.backlight_brightness = 255 * self.backlight_brightness_percent / 100
        self.usersettings.change_setting_value(
            "backlight_brightness", int(self.backlight_brightness)
        )
        self.usersettings.change_setting_value(
            "backlight_brightness_percent", self.backlight_brightness_percent
        )
        fastColorWipe(self.ledstrip.strip, True, self)

    def change_backlight_color(self, color, value):
        if color == "Red":
            if 255 >= self.backlight_red >= 0:
                self.backlight_red += int(value)
                self.backlight_red = clamp(self.backlight_red, 0, 255)
        elif color == "Green":
            if 255 >= self.backlight_green >= 0:
                self.backlight_green += int(value)
                self.backlight_green = clamp(self.backlight_green, 0, 255)
        elif color == "Blue":
            if 255 >= self.backlight_blue >= 0:
                self.backlight_blue += int(value)
                self.backlight_blue = clamp(self.backlight_blue, 0, 255)
        self.usersettings.change_setting_value("backlight_red", self.backlight_red)
        self.usersettings.change_setting_value("backlight_green", self.backlight_green)
        self.usersettings.change_setting_value("backlight_blue", self.backlight_blue)

        fastColorWipe(self.ledstrip.strip, True, self)

    def change_adjacent_color(self, color, value):
        self.adjacent_mode = "RGB"
        self.usersettings.change_setting_value("adjacent_mode", self.adjacent_mode)
        if color == "Red":
            if 255 >= self.adjacent_red >= 0:
                self.adjacent_red += int(value)
                self.adjacent_red = clamp(self.adjacent_red, 0, 255)
        elif color == "Green":
            if 255 >= self.adjacent_green >= 0:
                self.adjacent_green += int(value)
                self.adjacent_green = clamp(self.adjacent_green, 0, 255)
        elif color == "Blue":
            if 255 >= self.adjacent_blue >= 0:
                self.adjacent_blue += int(value)
                self.adjacent_blue = clamp(self.adjacent_blue, 0, 255)
        self.usersettings.change_setting_value("adjacent_red", self.adjacent_red)
        self.usersettings.change_setting_value("adjacent_green", self.adjacent_green)
        self.usersettings.change_setting_value("adjacent_blue", self.adjacent_blue)
        fastColorWipe(self.ledstrip.strip, True, self)
