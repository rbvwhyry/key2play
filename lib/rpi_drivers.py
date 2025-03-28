from lib.log_setup import logger

# GPIO
try:
    import RPi.GPIO as GPIO

    RPiException = None
except Exception as e:
    logger.warning("RPi GPIO failed, using null driver.")
    RPiException = e
    from lib.null_drivers import GPIOnull

    GPIO = GPIOnull()

# rpi_ws281x
try:
    from rpi_ws281x import Color, PixelStrip, ws  # noqa: F401 I001
except ModuleNotFoundError:
    logger.warning("Module rpi_ws281x not found, using null driver.")

    PixelStrip = None
    ws = None
    from lib.null_drivers import Color  # noqa: F401 I001
