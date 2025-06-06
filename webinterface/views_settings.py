import datetime
import json
import os
import threading
from subprocess import call
from xml.dom import minidom
from zipfile import ZipFile

import webcolors as wc
from flask import jsonify, request, send_file
from werkzeug.security import safe_join

import lib.colormaps as cmap
from lib.functions import clamp, fastColorWipe, play_midi
from lib.log_setup import logger
from webinterface import webinterface


def pretty_print(dom):
    return "\n".join(
        [line for line in dom.toprettyxml(indent=" " * 4).split("\n") if line.strip()]
    )


def pretty_save(file_path, sequences_tree):
    with open(file_path, "w", encoding="utf8") as outfile:
        outfile.write(pretty_print(sequences_tree))


@webinterface.route("/api/change_setting", methods=["GET"])
def change_setting():
    setting_name = request.args.get("setting_name")
    value = request.args.get("value")
    second_value = request.args.get("second_value")
    disable_sequence = request.args.get("disable_sequence")

    reload_sequence = True
    if second_value == "no_reload":
        reload_sequence = False

    if disable_sequence == "true":
        # menu = webinterface.ledsettings.menu
        # ledstrip = webinterface.ledsettings.ledstrip
        # webinterface.ledsettings.__init__(webinterface.usersettings)
        # webinterface.ledsettings.menu = menu
        # webinterface.ledsettings.add_instance(menu, ledstrip)
        # webinterface.ledsettings.ledstrip = ledstrip
        webinterface.ledsettings.sequence_active = False

    if setting_name == "clean_ledstrip":
        fastColorWipe(webinterface.ledstrip.strip, True, webinterface.ledsettings)

    if setting_name == "led_color":
        rgb = wc.hex_to_rgb("#" + value)

        webinterface.ledsettings.color_mode = "Single"

        webinterface.ledsettings.red = rgb[0]
        webinterface.ledsettings.green = rgb[1]
        webinterface.ledsettings.blue = rgb[2]

        webinterface.usersettings.change_setting_value(
            "color_mode", webinterface.ledsettings.color_mode
        )
        webinterface.usersettings.change_setting_value("red", rgb[0])
        webinterface.usersettings.change_setting_value("green", rgb[1])
        webinterface.usersettings.change_setting_value("blue", rgb[2])
        webinterface.ledsettings.incoming_setting_change = True
        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "light_mode":
        webinterface.ledsettings.mode = value
        webinterface.usersettings.change_setting_value("mode", value)

    if setting_name == "fading_speed" or setting_name == "velocity_speed":
        if not int(value):
            value = 1000
        webinterface.ledsettings.fadingspeed = int(value)
        webinterface.usersettings.change_setting_value(
            "fadingspeed", webinterface.ledsettings.fadingspeed
        )

    if setting_name == "brightness":
        webinterface.usersettings.change_setting_value("brightness_percent", int(value))
        webinterface.ledstrip.change_brightness(int(value), True)

    if setting_name == "led_animation_brightness_percent":
        webinterface.usersettings.change_setting_value(
            "led_animation_brightness_percent", int(value)
        )
        webinterface.ledsettings.led_animation_brightness_percent = int(value)

    if setting_name == "backlight_brightness":
        webinterface.ledsettings.backlight_brightness_percent = int(value)
        webinterface.ledsettings.backlight_brightness = (
            255 * webinterface.ledsettings.backlight_brightness_percent / 100
        )
        webinterface.usersettings.change_setting_value(
            "backlight_brightness", int(webinterface.ledsettings.backlight_brightness)
        )
        webinterface.usersettings.change_setting_value(
            "backlight_brightness_percent",
            webinterface.ledsettings.backlight_brightness_percent,
        )
        fastColorWipe(webinterface.ledstrip.strip, True, webinterface.ledsettings)

    if setting_name == "disable_backlight_on_idle":
        value = int(value == "true")
        webinterface.ledsettings.disable_backlight_on_idle = int(value)
        webinterface.usersettings.change_setting_value(
            "disable_backlight_on_idle",
            webinterface.ledsettings.disable_backlight_on_idle,
        )

    if setting_name == "backlight_color":
        rgb = wc.hex_to_rgb("#" + value)

        webinterface.ledsettings.backlight_red = rgb[0]
        webinterface.ledsettings.backlight_green = rgb[1]
        webinterface.ledsettings.backlight_blue = rgb[2]

        webinterface.usersettings.change_setting_value("backlight_red", rgb[0])
        webinterface.usersettings.change_setting_value("backlight_green", rgb[1])
        webinterface.usersettings.change_setting_value("backlight_blue", rgb[2])

        fastColorWipe(webinterface.ledstrip.strip, True, webinterface.ledsettings)

    if setting_name == "sides_color":
        rgb = wc.hex_to_rgb("#" + value)

        webinterface.ledsettings.adjacent_red = rgb[0]
        webinterface.ledsettings.adjacent_green = rgb[1]
        webinterface.ledsettings.adjacent_blue = rgb[2]

        webinterface.usersettings.change_setting_value("adjacent_red", rgb[0])
        webinterface.usersettings.change_setting_value("adjacent_green", rgb[1])
        webinterface.usersettings.change_setting_value("adjacent_blue", rgb[2])

    if setting_name == "sides_color_mode":
        webinterface.ledsettings.adjacent_mode = value
        webinterface.usersettings.change_setting_value("adjacent_mode", value)

    if setting_name == "input_port":
        webinterface.usersettings.change_setting_value("input_port", value)
        webinterface.midiports.change_port("inport", value)

    if setting_name == "secondary_input_port":
        webinterface.usersettings.change_setting_value("secondary_input_port", value)

    if setting_name == "play_port":
        webinterface.usersettings.change_setting_value("play_port", value)
        webinterface.midiports.change_port("playport", value)

    if setting_name == "skipped_notes":
        webinterface.usersettings.change_setting_value("skipped_notes", value)
        webinterface.ledsettings.skipped_notes = value

    if setting_name == "add_note_offset":
        webinterface.ledsettings.add_note_offset()
        return jsonify(success=True, reload=True)

    if setting_name == "append_note_offset":
        webinterface.ledsettings.append_note_offset()
        return jsonify(success=True, reload=True)

    if setting_name == "remove_note_offset":
        webinterface.ledsettings.del_note_offset(int(value) + 1)
        return jsonify(success=True, reload=True)

    if setting_name == "note_offsets":
        webinterface.usersettings.change_setting_value("note_offsets", value)

    if setting_name == "update_note_offset":
        webinterface.ledsettings.update_note_offset(int(value) + 1, second_value)
        return jsonify(success=True, reload=True)

    if setting_name == "shift":
        webinterface.usersettings.change_setting_value("shift", int(value))
        webinterface.ledstrip.change_shift(int(value), True)

    if setting_name == "reverse":
        webinterface.usersettings.change_setting_value("reverse", int(value))
        webinterface.ledstrip.change_reverse(int(value), True)

    if setting_name == "color_mode":
        reload_sequence = True
        if second_value == "no_reload":
            reload_sequence = False

        webinterface.ledsettings.color_mode = value
        webinterface.usersettings.change_setting_value(
            "color_mode", webinterface.ledsettings.color_mode
        )
        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "add_multicolor":
        webinterface.ledsettings.addcolor()
        return jsonify(success=True, reload=True)

    if setting_name == "add_multicolor_and_set_value":
        settings = json.loads(value)

        webinterface.ledsettings.multicolor.clear()
        webinterface.ledsettings.multicolor_range.clear()

        for key, value in settings.items():
            rgb = wc.hex_to_rgb("#" + value["color"])

            webinterface.ledsettings.multicolor.append(
                [int(rgb[0]), int(rgb[1]), int(rgb[2])]
            )
            webinterface.ledsettings.multicolor_range.append(
                [int(value["range"][0]), int(value["range"][1])]
            )

        webinterface.usersettings.change_setting_value(
            "multicolor", webinterface.ledsettings.multicolor
        )
        webinterface.usersettings.change_setting_value(
            "multicolor_range", webinterface.ledsettings.multicolor_range
        )

        cmap.update_multicolor(
            webinterface.ledsettings.multicolor_range,
            webinterface.ledsettings.multicolor,
        )

        return jsonify(success=True)

    if setting_name == "remove_multicolor":
        webinterface.ledsettings.deletecolor(int(value) + 1)
        cmap.update_multicolor(
            webinterface.ledsettings.multicolor_range,
            webinterface.ledsettings.multicolor,
        )
        return jsonify(success=True, reload=True)

    if setting_name == "multicolor":
        rgb = wc.hex_to_rgb("#" + value)
        webinterface.ledsettings.multicolor[int(second_value)][0] = rgb[0]
        webinterface.ledsettings.multicolor[int(second_value)][1] = rgb[1]
        webinterface.ledsettings.multicolor[int(second_value)][2] = rgb[2]

        webinterface.usersettings.change_setting_value(
            "multicolor", webinterface.ledsettings.multicolor
        )

        cmap.update_multicolor(
            webinterface.ledsettings.multicolor_range,
            webinterface.ledsettings.multicolor,
        )

        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "multicolor_range_left":
        webinterface.ledsettings.multicolor_range[int(second_value)][0] = int(value)
        webinterface.usersettings.change_setting_value(
            "multicolor_range", webinterface.ledsettings.multicolor_range
        )

        cmap.update_multicolor(
            webinterface.ledsettings.multicolor_range,
            webinterface.ledsettings.multicolor,
        )

        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "multicolor_range_right":
        webinterface.ledsettings.multicolor_range[int(second_value)][1] = int(value)
        webinterface.usersettings.change_setting_value(
            "multicolor_range", webinterface.ledsettings.multicolor_range
        )

        cmap.update_multicolor(
            webinterface.ledsettings.multicolor_range,
            webinterface.ledsettings.multicolor,
        )

        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "remove_all_multicolors":
        webinterface.ledsettings.multicolor.clear()
        webinterface.ledsettings.multicolor_range.clear()

        webinterface.usersettings.change_setting_value(
            "multicolor", webinterface.ledsettings.multicolor
        )
        webinterface.usersettings.change_setting_value(
            "multicolor_range", webinterface.ledsettings.multicolor_range
        )
        return jsonify(success=True)

    if setting_name == "rainbow_offset":
        webinterface.ledsettings.rainbow_offset = int(value)
        webinterface.usersettings.change_setting_value(
            "rainbow_offset", int(webinterface.ledsettings.rainbow_offset)
        )
        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "rainbow_scale":
        webinterface.ledsettings.rainbow_scale = int(value)
        webinterface.usersettings.change_setting_value(
            "rainbow_scale", int(webinterface.ledsettings.rainbow_scale)
        )
        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "rainbow_timeshift":
        webinterface.ledsettings.rainbow_timeshift = int(value)
        webinterface.usersettings.change_setting_value(
            "rainbow_timeshift", int(webinterface.ledsettings.rainbow_timeshift)
        )
        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "rainbow_colormap":
        webinterface.ledsettings.rainbow_colormap = value
        webinterface.usersettings.change_setting_value(
            "rainbow_colormap", webinterface.ledsettings.rainbow_colormap
        )
        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "velocityrainbow_offset":
        webinterface.ledsettings.velocityrainbow_offset = int(value)
        webinterface.usersettings.change_setting_value(
            "velocityrainbow_offset",
            int(webinterface.ledsettings.velocityrainbow_offset),
        )
        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "velocityrainbow_scale":
        webinterface.ledsettings.velocityrainbow_scale = int(value)
        webinterface.usersettings.change_setting_value(
            "velocityrainbow_scale", int(webinterface.ledsettings.velocityrainbow_scale)
        )
        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "velocityrainbow_curve":
        webinterface.ledsettings.velocityrainbow_curve = int(value)
        webinterface.usersettings.change_setting_value(
            "velocityrainbow_curve", int(webinterface.ledsettings.velocityrainbow_curve)
        )
        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "velocityrainbow_colormap":
        webinterface.ledsettings.velocityrainbow_colormap = value
        webinterface.usersettings.change_setting_value(
            "velocityrainbow_colormap",
            webinterface.ledsettings.velocityrainbow_colormap,
        )
        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "speed_slowest_color":
        rgb = wc.hex_to_rgb("#" + value)
        webinterface.ledsettings.speed_slowest["red"] = rgb[0]
        webinterface.ledsettings.speed_slowest["green"] = rgb[1]
        webinterface.ledsettings.speed_slowest["blue"] = rgb[2]

        webinterface.usersettings.change_setting_value("speed_slowest_red", rgb[0])
        webinterface.usersettings.change_setting_value("speed_slowest_green", rgb[1])
        webinterface.usersettings.change_setting_value("speed_slowest_blue", rgb[2])

        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "speed_fastest_color":
        rgb = wc.hex_to_rgb("#" + value)
        webinterface.ledsettings.speed_fastest["red"] = rgb[0]
        webinterface.ledsettings.speed_fastest["green"] = rgb[1]
        webinterface.ledsettings.speed_fastest["blue"] = rgb[2]

        webinterface.usersettings.change_setting_value("speed_fastest_red", rgb[0])
        webinterface.usersettings.change_setting_value("speed_fastest_green", rgb[1])
        webinterface.usersettings.change_setting_value("speed_fastest_blue", rgb[2])

        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "gradient_start_color":
        rgb = wc.hex_to_rgb("#" + value)
        webinterface.ledsettings.gradient_start["red"] = rgb[0]
        webinterface.ledsettings.gradient_start["green"] = rgb[1]
        webinterface.ledsettings.gradient_start["blue"] = rgb[2]

        webinterface.usersettings.change_setting_value("gradient_start_red", rgb[0])
        webinterface.usersettings.change_setting_value("gradient_start_green", rgb[1])
        webinterface.usersettings.change_setting_value("gradient_start_blue", rgb[2])

        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "gradient_end_color":
        rgb = wc.hex_to_rgb("#" + value)
        webinterface.ledsettings.gradient_end["red"] = rgb[0]
        webinterface.ledsettings.gradient_end["green"] = rgb[1]
        webinterface.ledsettings.gradient_end["blue"] = rgb[2]

        webinterface.usersettings.change_setting_value("gradient_end_red", rgb[0])
        webinterface.usersettings.change_setting_value("gradient_end_green", rgb[1])
        webinterface.usersettings.change_setting_value("gradient_end_blue", rgb[2])

        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "speed_max_notes":
        webinterface.ledsettings.speed_max_notes = int(value)
        webinterface.usersettings.change_setting_value("speed_max_notes", int(value))

        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "speed_period_in_seconds":
        webinterface.ledsettings.speed_period_in_seconds = float(value)
        webinterface.usersettings.change_setting_value(
            "speed_period_in_seconds", float(value)
        )

        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "key_in_scale_color":
        rgb = wc.hex_to_rgb("#" + value)
        webinterface.ledsettings.key_in_scale["red"] = rgb[0]
        webinterface.ledsettings.key_in_scale["green"] = rgb[1]
        webinterface.ledsettings.key_in_scale["blue"] = rgb[2]

        webinterface.usersettings.change_setting_value("key_in_scale_red", rgb[0])
        webinterface.usersettings.change_setting_value("key_in_scale_green", rgb[1])
        webinterface.usersettings.change_setting_value("key_in_scale_blue", rgb[2])

        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "key_not_in_scale_color":
        rgb = wc.hex_to_rgb("#" + value)
        webinterface.ledsettings.key_not_in_scale["red"] = rgb[0]
        webinterface.ledsettings.key_not_in_scale["green"] = rgb[1]
        webinterface.ledsettings.key_not_in_scale["blue"] = rgb[2]

        webinterface.usersettings.change_setting_value("key_not_in_scale_red", rgb[0])
        webinterface.usersettings.change_setting_value("key_not_in_scale_green", rgb[1])
        webinterface.usersettings.change_setting_value("key_not_in_scale_blue", rgb[2])

        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "scale_key":
        webinterface.ledsettings.scale_key = int(value)
        webinterface.usersettings.change_setting_value("scale_key", int(value))

        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "next_step":
        webinterface.ledsettings.set_sequence(0, 1, False)
        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "set_sequence":
        if int(value) == 0:
            menu = webinterface.ledsettings.menu
            ledstrip = webinterface.ledsettings.ledstrip
            webinterface.ledsettings.__init__(webinterface.usersettings)
            webinterface.ledsettings.menu = menu
            webinterface.ledsettings.ledstrip = ledstrip
            webinterface.ledsettings.sequence_active = False
        else:
            webinterface.ledsettings.set_sequence(int(value) - 1, 0)
        webinterface.ledsettings.incoming_setting_change = True
        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "change_sequence_name":
        sequences_tree = minidom.parse("config/sequences.xml")
        sequence_to_edit = "sequence_" + str(value)

        sequences_tree.getElementsByTagName(sequence_to_edit)[0].getElementsByTagName(
            "settings"
        )[0].getElementsByTagName("sequence_name")[0].firstChild.nodeValue = str(
            second_value
        )

        pretty_save("config/sequences.xml", sequences_tree)

        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "change_step_value":
        sequences_tree = minidom.parse("config/sequences.xml")
        sequence_to_edit = "sequence_" + str(value)

        sequences_tree.getElementsByTagName(sequence_to_edit)[0].getElementsByTagName(
            "settings"
        )[0].getElementsByTagName("next_step")[0].firstChild.nodeValue = str(
            second_value
        )

        pretty_save("config/sequences.xml", sequences_tree)

        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "change_step_activation_method":
        sequences_tree = minidom.parse("config/sequences.xml")
        sequence_to_edit = "sequence_" + str(value)

        sequences_tree.getElementsByTagName(sequence_to_edit)[0].getElementsByTagName(
            "settings"
        )[0].getElementsByTagName("control_number")[0].firstChild.nodeValue = str(
            second_value
        )

        pretty_save("config/sequences.xml", sequences_tree)

        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "add_sequence":
        sequences_tree = minidom.parse("config/sequences.xml")

        sequences_amount = 1
        while True:
            if (
                len(
                    sequences_tree.getElementsByTagName(
                        "sequence_" + str(sequences_amount)
                    )
                )
                == 0
            ):
                break
            sequences_amount += 1

        settings = sequences_tree.createElement("settings")

        control_number = sequences_tree.createElement("control_number")
        control_number.appendChild(sequences_tree.createTextNode("0"))
        settings.appendChild(control_number)

        next_step = sequences_tree.createElement("next_step")
        next_step.appendChild(sequences_tree.createTextNode("1"))
        settings.appendChild(next_step)

        sequence_name = sequences_tree.createElement("sequence_name")
        sequence_name.appendChild(
            sequences_tree.createTextNode("Sequence " + str(sequences_amount))
        )
        settings.appendChild(sequence_name)

        step = sequences_tree.createElement("step_1")

        color = sequences_tree.createElement("color")
        color.appendChild(sequences_tree.createTextNode("RGB"))
        step.appendChild(color)

        red = sequences_tree.createElement("Red")
        red.appendChild(sequences_tree.createTextNode("255"))
        step.appendChild(red)

        green = sequences_tree.createElement("Green")
        green.appendChild(sequences_tree.createTextNode("255"))
        step.appendChild(green)

        blue = sequences_tree.createElement("Blue")
        blue.appendChild(sequences_tree.createTextNode("255"))
        step.appendChild(blue)

        light_mode = sequences_tree.createElement("light_mode")
        light_mode.appendChild(sequences_tree.createTextNode("Normal"))
        step.appendChild(light_mode)

        element = sequences_tree.createElement("sequence_" + str(sequences_amount))
        element.appendChild(settings)
        element.appendChild(step)

        sequences_tree.getElementsByTagName("list")[0].appendChild(element)

        pretty_save("config/sequences.xml", sequences_tree)
        webinterface.ledsettings.incoming_setting_change = True
        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "remove_sequence":
        sequences_tree = minidom.parse("config/sequences.xml")

        # removing sequence node
        nodes = sequences_tree.getElementsByTagName("sequence_" + str(value))
        for node in nodes:
            parent = node.parentNode
            parent.removeChild(node)

        # changing nodes tag names
        i = 1
        for sequence in sequences_tree.getElementsByTagName("list")[0].childNodes:
            if sequence.nodeType == 1:
                sequences_tree.getElementsByTagName(sequence.nodeName)[0].tagName = (
                    "sequence_" + str(i)
                )
                i += 1

        pretty_save("config/sequences.xml", sequences_tree)
        webinterface.ledsettings.incoming_setting_change = True
        return jsonify(success=True, reload_sequence=reload_sequence)

    if setting_name == "add_step":
        sequences_tree = minidom.parse("config/sequences.xml")

        step_amount = 1
        while True:
            if (
                len(
                    sequences_tree.getElementsByTagName("sequence_" + str(value))[
                        0
                    ].getElementsByTagName("step_" + str(step_amount))
                )
                == 0
            ):
                break
            step_amount += 1

        step = sequences_tree.createElement("step_" + str(step_amount))

        color = sequences_tree.createElement("color")

        color.appendChild(sequences_tree.createTextNode("RGB"))
        step.appendChild(color)

        red = sequences_tree.createElement("Red")
        red.appendChild(sequences_tree.createTextNode("255"))
        step.appendChild(red)

        green = sequences_tree.createElement("Green")
        green.appendChild(sequences_tree.createTextNode("255"))
        step.appendChild(green)

        blue = sequences_tree.createElement("Blue")
        blue.appendChild(sequences_tree.createTextNode("255"))
        step.appendChild(blue)

        light_mode = sequences_tree.createElement("light_mode")
        light_mode.appendChild(sequences_tree.createTextNode("Normal"))
        step.appendChild(light_mode)

        sequences_tree.getElementsByTagName("sequence_" + str(value))[0].appendChild(
            step
        )

        pretty_save("config/sequences.xml", sequences_tree)
        webinterface.ledsettings.incoming_setting_change = True
        return jsonify(
            success=True,
            reload_sequence=reload_sequence,
            reload_steps_list=True,
            set_sequence_step_number=step_amount,
        )

    # remove node list with a tag name "step_" + str(value), and change tag names to maintain order
    if setting_name == "remove_step":
        second_value = int(second_value)
        second_value += 1

        sequences_tree = minidom.parse("config/sequences.xml")

        # removing step node
        nodes = sequences_tree.getElementsByTagName("sequence_" + str(value))[
            0
        ].getElementsByTagName("step_" + str(second_value))
        for node in nodes:
            parent = node.parentNode
            parent.removeChild(node)

        # changing nodes tag names
        i = 1
        for step in sequences_tree.getElementsByTagName("sequence_" + str(value))[
            0
        ].childNodes:
            if step.nodeType == 1 and step.tagName != "settings":
                sequences_tree.getElementsByTagName("sequence_" + str(value))[
                    0
                ].getElementsByTagName(step.nodeName)[0].tagName = "step_" + str(i)
                i += 1

        pretty_save("config/sequences.xml", sequences_tree)
        webinterface.ledsettings.incoming_setting_change = True
        return jsonify(
            success=True, reload_sequence=reload_sequence, reload_steps_list=True
        )

    # saving current led settings as sequence step
    if setting_name == "save_led_settings_to_step" and second_value != "":
        # remove node and child under "sequence_" + str(value) and "step_" + str(second_value)
        sequences_tree = minidom.parse("config/sequences.xml")

        second_value = int(second_value)
        second_value += 1

        nodes = sequences_tree.getElementsByTagName("sequence_" + str(value))[
            0
        ].getElementsByTagName("step_" + str(second_value))
        for node in nodes:
            parent = node.parentNode
            parent.removeChild(node)

        # create new step node
        step = sequences_tree.createElement("step_" + str(second_value))

        # load color mode from webinterface.ledsettings and put it into step node
        color_mode = sequences_tree.createElement("color")
        color_mode.appendChild(
            sequences_tree.createTextNode(str(webinterface.ledsettings.color_mode))
        )
        step.appendChild(color_mode)

        # load mode from webinterface.ledsettings and put it into step node
        mode = sequences_tree.createElement("light_mode")
        mode.appendChild(
            sequences_tree.createTextNode(str(webinterface.ledsettings.mode))
        )
        step.appendChild(mode)

        # if mode is equal "Fading" or "Velocity", load fadingspeed from ledsettings and put it into step node
        if webinterface.ledsettings.mode in ["Fading", "Velocity"]:
            fadingspeed = sequences_tree.createElement("fadingspeed")
            fadingspeed.appendChild(
                sequences_tree.createTextNode(str(webinterface.ledsettings.fadingspeed))
            )
            step.appendChild(fadingspeed)

        # if color_mode is equal to "Single" load color from webinterface.ledsettings and put it into step node
        if webinterface.ledsettings.color_mode == "Single":
            red = sequences_tree.createElement("Red")
            red.appendChild(
                sequences_tree.createTextNode(str(webinterface.ledsettings.red))
            )
            step.appendChild(red)

            green = sequences_tree.createElement("Green")
            green.appendChild(
                sequences_tree.createTextNode(str(webinterface.ledsettings.green))
            )
            step.appendChild(green)

            blue = sequences_tree.createElement("Blue")
            blue.appendChild(
                sequences_tree.createTextNode(str(webinterface.ledsettings.blue))
            )
            step.appendChild(blue)

        # if color_mode is equal to "Multicolor" load colors from webinterface.ledsettings and put it into step node
        if webinterface.ledsettings.color_mode == "Multicolor":
            # load value from webinterface.ledsettings.multicolor
            multicolor = webinterface.ledsettings.multicolor

            # loop through multicolor object and add each color to step node
            # under "sequence_"+str(value) with tag name "color_"+str(i)
            for i in range(len(multicolor)):
                color = sequences_tree.createElement("color_" + str(i + 1))
                new_multicolor = str(multicolor[i])
                new_multicolor = new_multicolor.replace("[", "")
                new_multicolor = new_multicolor.replace("]", "")

                color.appendChild(sequences_tree.createTextNode(new_multicolor))
                step.appendChild(color)

            # same as above but with multicolor_range and "color_range_"+str(i)
            multicolor_range = webinterface.ledsettings.multicolor_range
            for i in range(len(multicolor_range)):
                color_range = sequences_tree.createElement("color_range_" + str(i + 1))
                new_multicolor_range = str(multicolor_range[i])

                new_multicolor_range = new_multicolor_range.replace("[", "")
                new_multicolor_range = new_multicolor_range.replace("]", "")
                color_range.appendChild(
                    sequences_tree.createTextNode(new_multicolor_range)
                )
                step.appendChild(color_range)

        # if color_mode is equal to "Rainbow" load colors from webinterface.ledsettings and put it into step node
        if webinterface.ledsettings.color_mode == "Rainbow":
            # load values rainbow_offset, rainbow_scale and rainbow_timeshift from webinterface.ledsettings and put them into step node under Offset, Scale and Timeshift
            rainbow_offset = sequences_tree.createElement("Offset")
            rainbow_offset.appendChild(
                sequences_tree.createTextNode(
                    str(webinterface.ledsettings.rainbow_offset)
                )
            )
            step.appendChild(rainbow_offset)

            rainbow_scale = sequences_tree.createElement("Scale")
            rainbow_scale.appendChild(
                sequences_tree.createTextNode(
                    str(webinterface.ledsettings.rainbow_scale)
                )
            )
            step.appendChild(rainbow_scale)

            rainbow_timeshift = sequences_tree.createElement("Timeshift")
            rainbow_timeshift.appendChild(
                sequences_tree.createTextNode(
                    str(webinterface.ledsettings.rainbow_timeshift)
                )
            )
            step.appendChild(rainbow_timeshift)

            rainbow_colormap = sequences_tree.createElement("Colormap")
            rainbow_colormap.appendChild(
                sequences_tree.createTextNode(
                    str(webinterface.ledsettings.rainbow_colormap)
                )
            )
            step.appendChild(rainbow_colormap)

        # if color_mode is equal to "VelocityRainbow" load colors from webinterface.ledsettings and put it into step node
        if webinterface.ledsettings.color_mode == "VelocityRainbow":
            velocityrainbow_offset = sequences_tree.createElement("Offset")
            velocityrainbow_offset.appendChild(
                sequences_tree.createTextNode(
                    str(webinterface.ledsettings.velocityrainbow_offset)
                )
            )
            step.appendChild(velocityrainbow_offset)

            velocityrainbow_scale = sequences_tree.createElement("Scale")
            velocityrainbow_scale.appendChild(
                sequences_tree.createTextNode(
                    str(webinterface.ledsettings.velocityrainbow_scale)
                )
            )
            step.appendChild(velocityrainbow_scale)

            velocityrainbow_curve = sequences_tree.createElement("Curve")
            velocityrainbow_curve.appendChild(
                sequences_tree.createTextNode(
                    str(webinterface.ledsettings.velocityrainbow_curve)
                )
            )
            step.appendChild(velocityrainbow_curve)

            velocityrainbow_colormap = sequences_tree.createElement("Colormap")
            velocityrainbow_colormap.appendChild(
                sequences_tree.createTextNode(
                    str(webinterface.ledsettings.velocityrainbow_colormap)
                )
            )
            step.appendChild(velocityrainbow_colormap)

        # if color_mode is equal to "Speed" load colors from webinterface.ledsettings and put it into step node
        if webinterface.ledsettings.color_mode == "Speed":
            # load values speed_slowest["red"] etc. from webinterface.ledsettings and put them under speed_slowest_red etc
            speed_slowest_red = sequences_tree.createElement("speed_slowest_red")
            speed_slowest_red.appendChild(
                sequences_tree.createTextNode(
                    str(webinterface.ledsettings.speed_slowest["red"])
                )
            )
            step.appendChild(speed_slowest_red)

            speed_slowest_green = sequences_tree.createElement("speed_slowest_green")
            speed_slowest_green.appendChild(
                sequences_tree.createTextNode(
                    str(webinterface.ledsettings.speed_slowest["green"])
                )
            )
            step.appendChild(speed_slowest_green)

            speed_slowest_blue = sequences_tree.createElement("speed_slowest_blue")
            speed_slowest_blue.appendChild(
                sequences_tree.createTextNode(
                    str(webinterface.ledsettings.speed_slowest["blue"])
                )
            )
            step.appendChild(speed_slowest_blue)

            # same as above but with "fastest"
            speed_fastest_red = sequences_tree.createElement("speed_fastest_red")
            speed_fastest_red.appendChild(
                sequences_tree.createTextNode(
                    str(webinterface.ledsettings.speed_fastest["red"])
                )
            )
            step.appendChild(speed_fastest_red)

            speed_fastest_green = sequences_tree.createElement("speed_fastest_green")
            speed_fastest_green.appendChild(
                sequences_tree.createTextNode(
                    str(webinterface.ledsettings.speed_fastest["green"])
                )
            )
            step.appendChild(speed_fastest_green)

            speed_fastest_blue = sequences_tree.createElement("speed_fastest_blue")
            speed_fastest_blue.appendChild(
                sequences_tree.createTextNode(
                    str(webinterface.ledsettings.speed_fastest["blue"])
                )
            )
            step.appendChild(speed_fastest_blue)

            # load "speed_max_notes" and "speed_period_in_seconds" values from webinterface.ledsettings
            # and put them under speed_max_notes and speed_period_in_seconds

            speed_max_notes = sequences_tree.createElement("speed_max_notes")
            speed_max_notes.appendChild(
                sequences_tree.createTextNode(
                    str(webinterface.ledsettings.speed_max_notes)
                )
            )
            step.appendChild(speed_max_notes)

            speed_period_in_seconds = sequences_tree.createElement(
                "speed_period_in_seconds"
            )
            speed_period_in_seconds.appendChild(
                sequences_tree.createTextNode(
                    str(webinterface.ledsettings.speed_period_in_seconds)
                )
            )
            step.appendChild(speed_period_in_seconds)

        # if color_mode is equal to "Gradient" load colors from webinterface.ledsettings and put it into step node
        if webinterface.ledsettings.color_mode == "Gradient":
            # load values gradient_start_red etc from webinterface.ledsettings and put them under gradient_start_red etc
            gradient_start_red = sequences_tree.createElement("gradient_start_red")
            gradient_start_red.appendChild(
                sequences_tree.createTextNode(
                    str(webinterface.ledsettings.gradient_start["red"])
                )
            )
            step.appendChild(gradient_start_red)

            gradient_start_green = sequences_tree.createElement("gradient_start_green")
            gradient_start_green.appendChild(
                sequences_tree.createTextNode(
                    str(webinterface.ledsettings.gradient_start["green"])
                )
            )
            step.appendChild(gradient_start_green)

            gradient_start_blue = sequences_tree.createElement("gradient_start_blue")
            gradient_start_blue.appendChild(
                sequences_tree.createTextNode(
                    str(webinterface.ledsettings.gradient_start["blue"])
                )
            )
            step.appendChild(gradient_start_blue)

            # same as above but with gradient_end
            gradient_end_red = sequences_tree.createElement("gradient_end_red")
            gradient_end_red.appendChild(
                sequences_tree.createTextNode(
                    str(webinterface.ledsettings.gradient_end["red"])
                )
            )
            step.appendChild(gradient_end_red)

            gradient_end_green = sequences_tree.createElement("gradient_end_green")
            gradient_end_green.appendChild(
                sequences_tree.createTextNode(
                    str(webinterface.ledsettings.gradient_end["green"])
                )
            )
            step.appendChild(gradient_end_green)

            gradient_end_blue = sequences_tree.createElement("gradient_end_blue")
            gradient_end_blue.appendChild(
                sequences_tree.createTextNode(
                    str(webinterface.ledsettings.gradient_end["blue"])
                )
            )
            step.appendChild(gradient_end_blue)

        # if color_mode is equal to "Scale" load colors from webinterface.ledsettings and put it into step node
        if webinterface.ledsettings.color_mode == "Scale":
            # load values key_in_scale_red etc from webinterface.ledsettings and put them under key_in_scale_red etc
            key_in_scale_red = sequences_tree.createElement("key_in_scale_red")
            key_in_scale_red.appendChild(
                sequences_tree.createTextNode(
                    str(webinterface.ledsettings.key_in_scale["red"])
                )
            )
            step.appendChild(key_in_scale_red)

            key_in_scale_green = sequences_tree.createElement("key_in_scale_green")
            key_in_scale_green.appendChild(
                sequences_tree.createTextNode(
                    str(webinterface.ledsettings.key_in_scale["green"])
                )
            )
            step.appendChild(key_in_scale_green)

            key_in_scale_blue = sequences_tree.createElement("key_in_scale_blue")
            key_in_scale_blue.appendChild(
                sequences_tree.createTextNode(
                    str(webinterface.ledsettings.key_in_scale["blue"])
                )
            )
            step.appendChild(key_in_scale_blue)

            # same as above but with key_not_in_scale
            key_not_in_scale_red = sequences_tree.createElement("key_not_in_scale_red")
            key_not_in_scale_red.appendChild(
                sequences_tree.createTextNode(
                    str(webinterface.ledsettings.key_not_in_scale["red"])
                )
            )
            step.appendChild(key_not_in_scale_red)

            key_not_in_scale_green = sequences_tree.createElement(
                "key_not_in_scale_green"
            )
            key_not_in_scale_green.appendChild(
                sequences_tree.createTextNode(
                    str(webinterface.ledsettings.key_not_in_scale["green"])
                )
            )
            step.appendChild(key_not_in_scale_green)

            key_not_in_scale_blue = sequences_tree.createElement(
                "key_not_in_scale_blue"
            )
            key_not_in_scale_blue.appendChild(
                sequences_tree.createTextNode(
                    str(webinterface.ledsettings.key_not_in_scale["blue"])
                )
            )
            step.appendChild(key_not_in_scale_blue)

            scale_key = sequences_tree.createElement("scale_key")
            scale_key.appendChild(
                sequences_tree.createTextNode(str(webinterface.ledsettings.scale_key))
            )
            step.appendChild(scale_key)

        try:
            sequences_tree.getElementsByTagName("sequence_" + str(value))[
                0
            ].insertBefore(
                step,
                sequences_tree.getElementsByTagName("sequence_" + str(value))[
                    0
                ].getElementsByTagName("step_" + str(second_value + 1))[0],
            )
        except Exception:
            sequences_tree.getElementsByTagName("sequence_" + str(value))[
                0
            ].appendChild(step)

        pretty_save("config/sequences.xml", sequences_tree)

        webinterface.ledsettings.incoming_setting_change = True

        return jsonify(
            success=True, reload_sequence=reload_sequence, reload_steps_list=True
        )

    if setting_name == "screen_on":
        if int(value) == 0:
            webinterface.menu.disable_screen()
        else:
            webinterface.menu.enable_screen()

    if setting_name == "reinitialize_network_on_boot":
        if int(value) == 0:
            webinterface.usersettings.change_setting_value(
                "reinitialize_network_on_boot", 0
            )
        else:
            webinterface.usersettings.change_setting_value(
                "reinitialize_network_on_boot", 1
            )

    if setting_name == "reset_to_default":
        webinterface.usersettings.reset_to_default()

    if setting_name == "restart_rpi":
        webinterface.platform.reboot()

    if setting_name == "restart_visualizer":
        webinterface.platform.restart_visualizer()

    if setting_name == "turnoff_rpi":
        webinterface.platform.shutdown()

    if setting_name == "update_rpi":
        webinterface.platform.update_visualizer()

    if setting_name == "connect_ports":
        webinterface.midiports.connectall()
        return jsonify(success=True, reload_ports=True)

    if setting_name == "disconnect_ports":
        call("sudo aconnect -x", shell=True)
        return jsonify(success=True, reload_ports=True)

    if setting_name == "restart_rtp":
        webinterface.platform.restart_rtpmidid()

    if setting_name == "show_midi_events":
        value = int(value == "true")
        webinterface.usersettings.change_setting_value("midi_logging", value)

    if setting_name == "multicolor_iteration":
        value = int(value == "true")
        webinterface.usersettings.change_setting_value("multicolor_iteration", value)
        webinterface.ledsettings.multicolor_iteration = value

    if setting_name == "start_recording":
        webinterface.saving.start_recording()
        return jsonify(success=True, reload_songs=True)

    if setting_name == "cancel_recording":
        webinterface.saving.cancel_recording()
        return jsonify(success=True, reload_songs=True)

    if setting_name == "save_recording":
        now = datetime.datetime.now()
        current_date = now.strftime("%Y-%m-%d %H:%M")
        webinterface.saving.save(current_date)
        return jsonify(success=True, reload_songs=True)

    if setting_name == "change_song_name":
        if os.path.exists("Songs/" + second_value):
            return jsonify(
                success=False, reload_songs=True, error=second_value + " already exists"
            )

        if "_main" in value:
            search_name = value.replace("_main.mid", "")
            for fname in os.listdir("Songs"):
                if search_name in fname:
                    new_name = second_value.replace(".mid", "") + fname.replace(
                        search_name, ""
                    )
                    os.rename("Songs/" + fname, "Songs/" + new_name)
        else:
            os.rename("Songs/" + value, "Songs/" + second_value)
            os.rename(
                "Songs/cache/" + value + ".p", "Songs/cache/" + second_value + ".p"
            )

        return jsonify(success=True, reload_songs=True)

    if setting_name == "remove_song":
        if "_main" in value:
            name_no_suffix = value.replace("_main.mid", "")
            for fname in os.listdir("Songs"):
                if name_no_suffix in fname:
                    os.remove("Songs/" + fname)
        else:
            os.remove("Songs/" + value)

            file_types = [".musicxml", ".xml", ".mxl", ".abc"]
            for file_type in file_types:
                try:
                    os.remove("Songs/" + value.replace(".mid", file_type))
                except Exception:
                    pass

            try:
                os.remove("Songs/cache/" + value + ".p")
            except Exception:
                logger.info("No cache file for " + value)

        return jsonify(success=True, reload_songs=True)

    if setting_name == "download_song":
        if "_main" in value:
            zipObj = ZipFile("Songs/" + value.replace(".mid", "") + ".zip", "w")
            name_no_suffix = value.replace("_main.mid", "")
            songs_count = 0
            for fname in os.listdir("Songs"):
                if name_no_suffix in fname and ".zip" not in fname:
                    songs_count += 1
                    zipObj.write("Songs/" + fname)
            zipObj.close()
            if songs_count == 1:
                os.remove("Songs/" + value.replace(".mid", "") + ".zip")
                return send_file(
                    safe_join("../Songs/" + value),
                    mimetype="application/x-csv",
                    download_name=value,
                    as_attachment=True,
                )
            else:
                return send_file(
                    safe_join("../Songs/" + value.replace(".mid", "")) + ".zip",
                    mimetype="application/x-csv",
                    download_name=value.replace(".mid", "") + ".zip",
                    as_attachment=True,
                )
        else:
            return send_file(
                safe_join("../Songs/" + value),
                mimetype="application/x-csv",
                download_name=value,
                as_attachment=True,
            )

    if setting_name == "download_sheet_music":
        file_types = [".musicxml", ".xml", ".mxl", ".abc"]
        i = 0
        while i < len(file_types):
            try:
                new_name = value.replace(".mid", file_types[i])
                return send_file(
                    safe_join("../Songs/" + new_name),
                    mimetype="application/x-csv",
                    download_name=new_name,
                    as_attachment=True,
                )
            except Exception:
                i += 1
        webinterface.learning.convert_midi_to_abc(value)
        try:
            return send_file(
                safe_join("../Songs/", value.replace(".mid", ".abc")),
                mimetype="application/x-csv",
                download_name=value.replace(".mid", ".abc"),
                as_attachment=True,
            )
        except Exception:
            logger.warning("Converting failed")

    if setting_name == "start_midi_play":
        webinterface.saving.t = threading.Thread(
            target=play_midi,
            args=(
                value,
                webinterface.midiports,
                webinterface.saving,
                webinterface.menu,
                webinterface.ledsettings,
                webinterface.ledstrip,
            ),
        )
        webinterface.saving.t.start()

        return jsonify(success=True, reload_songs=True)

    if setting_name == "stop_midi_play":
        webinterface.saving.is_playing_midi.clear()
        fastColorWipe(webinterface.ledstrip.strip, True, webinterface.ledsettings)

        return jsonify(success=True, reload_songs=True)

    if setting_name == "learning_load_song":
        webinterface.learning.t = threading.Thread(
            target=webinterface.learning.load_midi, args=(value,)
        )
        webinterface.learning.t.start()

        return jsonify(success=True, reload_learning_settings=True)

    if setting_name == "start_learning_song":
        webinterface.learning.t = threading.Thread(
            target=webinterface.learning.learn_midi
        )
        webinterface.learning.t.start()

        return jsonify(success=True)

    if setting_name == "stop_learning_song":
        webinterface.learning.is_started_midi = False
        fastColorWipe(webinterface.ledstrip.strip, True, webinterface.ledsettings)

        return jsonify(success=True)

    if setting_name == "change_practice":
        value = int(value)
        webinterface.learning.practice = value
        webinterface.learning.practice = clamp(
            webinterface.learning.practice,
            0,
            len(webinterface.learning.practiceList) - 1,
        )
        webinterface.usersettings.change_setting_value(
            "practice", webinterface.learning.practice
        )

        return jsonify(success=True)

    if setting_name == "change_tempo":
        value = int(value)
        webinterface.learning.set_tempo = value
        webinterface.learning.set_tempo = clamp(
            webinterface.learning.set_tempo, 10, 200
        )
        webinterface.usersettings.change_setting_value(
            "set_tempo", webinterface.learning.set_tempo
        )

        return jsonify(success=True)

    if setting_name == "change_hands":
        value = int(value)
        webinterface.learning.hands = value
        webinterface.learning.hands = clamp(
            webinterface.learning.hands, 0, len(webinterface.learning.handsList) - 1
        )
        webinterface.usersettings.change_setting_value(
            "hands", webinterface.learning.hands
        )

        return jsonify(success=True)

    if setting_name == "change_mute_hand":
        value = int(value)
        webinterface.learning.mute_hand = value
        webinterface.learning.mute_hand = clamp(
            webinterface.learning.mute_hand,
            0,
            len(webinterface.learning.mute_handList) - 1,
        )
        webinterface.usersettings.change_setting_value(
            "mute_hand", webinterface.learning.mute_hand
        )

        return jsonify(success=True)

    if setting_name == "learning_start_point":
        value = int(value)
        webinterface.learning.start_point = value
        webinterface.learning.start_point = clamp(
            webinterface.learning.start_point, 0, webinterface.learning.end_point - 1
        )
        webinterface.usersettings.change_setting_value(
            "start_point", webinterface.learning.start_point
        )
        webinterface.learning.restart_learning()

        return jsonify(success=True)

    if setting_name == "learning_end_point":
        value = int(value)
        webinterface.learning.end_point = value
        webinterface.learning.end_point = clamp(
            webinterface.learning.end_point, webinterface.learning.start_point + 1, 100
        )
        webinterface.usersettings.change_setting_value(
            "end_point", webinterface.learning.end_point
        )
        webinterface.learning.restart_learning()

        return jsonify(success=True)

    if setting_name == "set_current_time_as_start_point":
        webinterface.learning.start_point = round(
            float(
                webinterface.learning.current_idx
                * 100
                / float(len(webinterface.learning.song_tracks))
            ),
            3,
        )
        webinterface.learning.start_point = clamp(
            webinterface.learning.start_point, 0, webinterface.learning.end_point - 1
        )
        webinterface.usersettings.change_setting_value(
            "start_point", webinterface.learning.start_point
        )
        webinterface.learning.restart_learning()

        return jsonify(success=True, reload_learning_settings=True)

    if setting_name == "set_current_time_as_end_point":
        webinterface.learning.end_point = round(
            float(
                webinterface.learning.current_idx
                * 100
                / float(len(webinterface.learning.song_tracks))
            ),
            3,
        )
        webinterface.learning.end_point = clamp(
            webinterface.learning.end_point, webinterface.learning.start_point + 1, 100
        )
        webinterface.usersettings.change_setting_value(
            "end_point", webinterface.learning.end_point
        )
        webinterface.learning.restart_learning()

        return jsonify(success=True, reload_learning_settings=True)

    if setting_name == "change_handL_color":
        value = int(value)
        webinterface.learning.hand_colorL += value
        webinterface.learning.hand_colorL = clamp(
            webinterface.learning.hand_colorL,
            0,
            len(webinterface.learning.hand_colorList) - 1,
        )
        webinterface.usersettings.change_setting_value(
            "hand_colorL", webinterface.learning.hand_colorL
        )

        return jsonify(success=True, reload_learning_settings=True)

    if setting_name == "change_handR_color":
        value = int(value)
        webinterface.learning.hand_colorR += value
        webinterface.learning.hand_colorR = clamp(
            webinterface.learning.hand_colorR,
            0,
            len(webinterface.learning.hand_colorList) - 1,
        )
        webinterface.usersettings.change_setting_value(
            "hand_colorR", webinterface.learning.hand_colorR
        )

        return jsonify(success=True, reload_learning_settings=True)

    if setting_name == "change_wrong_notes":
        value = int(value)
        webinterface.learning.show_wrong_notes = value
        webinterface.usersettings.change_setting_value(
            "show_wrong_notes", webinterface.learning.show_wrong_notes
        )

    if setting_name == "change_future_notes":
        value = int(value)
        webinterface.learning.show_future_notes = value
        webinterface.usersettings.change_setting_value(
            "show_future_notes", webinterface.learning.show_future_notes
        )

    if setting_name == "change_learning_loop":
        value = int(value == "true")
        webinterface.learning.is_loop_active = value
        webinterface.usersettings.change_setting_value(
            "is_loop_active", webinterface.learning.is_loop_active
        )

        return jsonify(success=True)

    if setting_name == "number_of_mistakes":
        value = int(value)
        webinterface.learning.number_of_mistakes = value
        webinterface.usersettings.change_setting_value(
            "number_of_mistakes", webinterface.learning.number_of_mistakes
        )

        return jsonify(success=True)

    if setting_name == "connect_to_wifi":
        logger.info("Controller: connecting to wifi")
        try:
            response = webinterface.platform.connect_to_wifi(
                value, second_value, webinterface.hotspot, webinterface.usersettings
            )
        except Exception:
            response = False

        return jsonify(success=response)

    if setting_name == "disconnect_wifi":
        try:
            webinterface.platform.disconnect_from_wifi(
                webinterface.hotspot, webinterface.usersettings
            )
        except Exception:
            return jsonify(success=False)

    if setting_name == "animation_delay":
        value = max(int(value), 0)
        webinterface.menu.led_animation_delay = value
        if webinterface.menu.led_animation_delay < 0:
            webinterface.menu.led_animation_delay = 0
        webinterface.usersettings.change_setting_value(
            "led_animation_delay", webinterface.menu.led_animation_delay
        )

        return jsonify(success=True)

    if setting_name == "led_animation":
        webinterface.menu.led_animation = value
        webinterface.usersettings.change_setting_value("led_animation", value)

        return jsonify(success=True)

    if setting_name == "led_gamma":
        webinterface.usersettings.change_setting_value("led_gamma", value)
        webinterface.ledstrip.change_gamma(float(value))

        return jsonify(success=True)

    return jsonify(success=True)


@webinterface.route("/api/get_settings", methods=["GET"])
def get_settings():
    response = {}

    red = webinterface.usersettings.get_setting_value("red")
    green = webinterface.usersettings.get_setting_value("green")
    blue = webinterface.usersettings.get_setting_value("blue")
    led_color = wc.rgb_to_hex((int(red), int(green), int(blue)))

    backlight_red = webinterface.usersettings.get_setting_value("backlight_red")
    backlight_green = webinterface.usersettings.get_setting_value("backlight_green")
    backlight_blue = webinterface.usersettings.get_setting_value("backlight_blue")
    backlight_color = wc.rgb_to_hex(
        (int(backlight_red), int(backlight_green), int(backlight_blue))
    )

    sides_red = webinterface.usersettings.get_setting_value("adjacent_red")
    sides_green = webinterface.usersettings.get_setting_value("adjacent_green")
    sides_blue = webinterface.usersettings.get_setting_value("adjacent_blue")
    sides_color = wc.rgb_to_hex((int(sides_red), int(sides_green), int(sides_blue)))

    light_mode = webinterface.usersettings.get_setting_value("mode")
    fading_speed = webinterface.usersettings.get_setting_value("fadingspeed")

    brightness = webinterface.usersettings.get_setting_value("brightness_percent")
    backlight_brightness = webinterface.usersettings.get_setting_value(
        "backlight_brightness_percent"
    )
    disable_backlight_on_idle = webinterface.usersettings.get_setting_value(
        "disable_backlight_on_idle"
    )

    response["led_color"] = led_color
    response["light_mode"] = light_mode
    response["fading_speed"] = fading_speed

    response["brightness"] = brightness
    response["backlight_brightness"] = backlight_brightness
    response["backlight_color"] = backlight_color
    response["disable_backlight_on_idle"] = disable_backlight_on_idle
    response["led_gamma"] = webinterface.usersettings.get_setting_value("led_gamma")

    response["sides_color_mode"] = webinterface.usersettings.get_setting_value(
        "adjacent_mode"
    )
    response["sides_color"] = sides_color

    response["input_port"] = webinterface.usersettings.get_setting_value("input_port")
    response["play_port"] = webinterface.usersettings.get_setting_value("play_port")

    response["skipped_notes"] = webinterface.usersettings.get_setting_value(
        "skipped_notes"
    )
    response["note_offsets"] = webinterface.usersettings.get_setting_value(
        "note_offsets"
    )
    response["led_shift"] = webinterface.usersettings.get_setting_value("shift")
    response["led_reverse"] = webinterface.usersettings.get_setting_value("reverse")

    response["color_mode"] = webinterface.usersettings.get_setting_value("color_mode")

    response["multicolor"] = webinterface.usersettings.get_setting_value("multicolor")
    response["multicolor_range"] = webinterface.usersettings.get_setting_value(
        "multicolor_range"
    )
    response["multicolor_iteration"] = webinterface.usersettings.get_setting_value(
        "multicolor_iteration"
    )

    response["rainbow_offset"] = webinterface.usersettings.get_setting_value(
        "rainbow_offset"
    )
    response["rainbow_scale"] = webinterface.usersettings.get_setting_value(
        "rainbow_scale"
    )
    response["rainbow_timeshift"] = webinterface.usersettings.get_setting_value(
        "rainbow_timeshift"
    )
    response["rainbow_colormap"] = webinterface.usersettings.get_setting_value(
        "rainbow_colormap"
    )

    response["velocityrainbow_offset"] = webinterface.usersettings.get_setting_value(
        "velocityrainbow_offset"
    )
    response["velocityrainbow_scale"] = webinterface.usersettings.get_setting_value(
        "velocityrainbow_scale"
    )
    response["velocityrainbow_curve"] = webinterface.usersettings.get_setting_value(
        "velocityrainbow_curve"
    )
    response["velocityrainbow_colormap"] = webinterface.usersettings.get_setting_value(
        "velocityrainbow_colormap"
    )

    speed_slowest_red = webinterface.usersettings.get_setting_value("speed_slowest_red")
    speed_slowest_green = webinterface.usersettings.get_setting_value(
        "speed_slowest_green"
    )
    speed_slowest_blue = webinterface.usersettings.get_setting_value(
        "speed_slowest_blue"
    )
    speed_slowest_color = wc.rgb_to_hex(
        (int(speed_slowest_red), int(speed_slowest_green), int(speed_slowest_blue))
    )
    response["speed_slowest_color"] = speed_slowest_color

    speed_fastest_red = webinterface.usersettings.get_setting_value("speed_fastest_red")
    speed_fastest_green = webinterface.usersettings.get_setting_value(
        "speed_fastest_green"
    )
    speed_fastest_blue = webinterface.usersettings.get_setting_value(
        "speed_fastest_blue"
    )
    speed_fastest_color = wc.rgb_to_hex(
        (int(speed_fastest_red), int(speed_fastest_green), int(speed_fastest_blue))
    )
    response["speed_fastest_color"] = speed_fastest_color

    gradient_start_red = webinterface.usersettings.get_setting_value(
        "gradient_start_red"
    )
    gradient_start_green = webinterface.usersettings.get_setting_value(
        "gradient_start_green"
    )
    gradient_start_blue = webinterface.usersettings.get_setting_value(
        "gradient_start_blue"
    )
    gradient_start_color = wc.rgb_to_hex(
        (int(gradient_start_red), int(gradient_start_green), int(gradient_start_blue))
    )
    response["gradient_start_color"] = gradient_start_color

    gradient_end_red = webinterface.usersettings.get_setting_value("gradient_end_red")
    gradient_end_green = webinterface.usersettings.get_setting_value(
        "gradient_end_green"
    )
    gradient_end_blue = webinterface.usersettings.get_setting_value("gradient_end_blue")
    gradient_end_color = wc.rgb_to_hex(
        (int(gradient_end_red), int(gradient_end_green), int(gradient_end_blue))
    )
    response["gradient_end_color"] = gradient_end_color

    key_in_scale_red = webinterface.usersettings.get_setting_value("key_in_scale_red")
    key_in_scale_green = webinterface.usersettings.get_setting_value(
        "key_in_scale_green"
    )
    key_in_scale_blue = webinterface.usersettings.get_setting_value("key_in_scale_blue")
    key_in_scale_color = wc.rgb_to_hex(
        (int(key_in_scale_red), int(key_in_scale_green), int(key_in_scale_blue))
    )
    response["key_in_scale_color"] = key_in_scale_color

    key_not_in_scale_red = webinterface.usersettings.get_setting_value(
        "key_not_in_scale_red"
    )
    key_not_in_scale_green = webinterface.usersettings.get_setting_value(
        "key_not_in_scale_green"
    )
    key_not_in_scale_blue = webinterface.usersettings.get_setting_value(
        "key_not_in_scale_blue"
    )
    key_not_in_scale_color = wc.rgb_to_hex(
        (
            int(key_not_in_scale_red),
            int(key_not_in_scale_green),
            int(key_not_in_scale_blue),
        )
    )
    response["key_not_in_scale_color"] = key_not_in_scale_color

    response["scale_key"] = webinterface.usersettings.get_setting_value("scale_key")

    response["speed_max_notes"] = webinterface.usersettings.get_setting_value(
        "speed_max_notes"
    )
    response["speed_period_in_seconds"] = webinterface.usersettings.get_setting_value(
        "speed_period_in_seconds"
    )

    return jsonify(response)
