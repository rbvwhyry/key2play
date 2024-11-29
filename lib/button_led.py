import RPi.GPIO as GPIO
import time
from rpi_ws281x import PixelStrip, Color

# LED strip configuration:
LED_COUNT = 30       # Number of LED pixels.
LED_PIN = 18         # GPIO pin connected to the LEDs (PWM pin).
LED_BRIGHTNESS = 255 # Brightness level (0-255).

# Button configuration:
BUTTON_PIN = 17      # GPIO pin connected to the button.

# Initialize the LED strip:
strip = PixelStrip(LED_COUNT, LED_PIN, brightness=LED_BRIGHTNESS)
strip.begin()

# Setup GPIO for the button:
GPIO.setmode(GPIO.BCM)
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)  # Pull-up resistor

# Function to light up an LED:
def light_up_led(led_index, color):
    strip.setPixelColor(led_index, Color(*color))  # Set the color of the LED
    strip.show()                                  # Apply the changes

# Function to turn off an LED:
def turn_off_led(led_index):
    strip.setPixelColor(led_index, Color(0, 0, 0))  # Turn off the LED
    strip.show()                                    # Apply the changes

# Main loop:
try:
    while True:
        button_state = GPIO.input(BUTTON_PIN)
        if button_state == GPIO.LOW:  # Button is pressed
            print("Button pressed!")
            light_up_led(0, (255, 0, 0))  # Light up the first LED in red
            time.sleep(0.2)  # Debounce delay
        else:
            turn_off_led(0)  # Turn off the first LED
        time.sleep(0.1)  # Small delay for button polling

except KeyboardInterrupt:
    print("Exiting program...")
    GPIO.cleanup()  # Clean up GPIO settings
