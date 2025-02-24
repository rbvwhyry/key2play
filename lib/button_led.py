from rpi_ws281x import PixelStrip, Color
import time

# LED strip configuration:
LED_COUNT = 150  # Number of LED pixels
LED_PIN = 18  # GPIO pin connected to the LEDs
LED_BRIGHTNESS = 255  # Brightness level (0-255)

# Initialize the LED strip
strip = PixelStrip(LED_COUNT, LED_PIN, brightness=LED_BRIGHTNESS)
strip.begin()


# Function to light up a specific LED
def light_up_led(index, color, duration):
    strip.setPixelColor(index, Color(*color))  # Set LED color
    strip.show()  # Update the strip
    time.sleep(duration)  # Wait for the duration
    strip.setPixelColor(index, Color(0, 0, 0))  # Turn off the LED
    strip.show()
