from lib.rpi_drivers import GPIO
import time
import numpy as np
from lib import LCD_Config


class LCD(object):
    """class for ST7789  240*240 1.3inch OLED displays."""

    def __init__(self):
        self.width = 240
        self.height = 240
        self.font_scale = 1.875
        # Initialize DC RST pin
        self._dc = LCD_Config.LCD_DC_PIN
        self._rst = LCD_Config.LCD_RST_PIN
        self._bl = LCD_Config.LCD_BL_PIN
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(self._dc, GPIO.OUT)
        GPIO.setup(self._rst, GPIO.OUT)
        GPIO.setup(self._bl, GPIO.OUT)
        GPIO.output(self._bl, GPIO.HIGH)
        self._spi = LCD_Config.SPI

    """    Write register address and data     """

    def command(self, cmd):
        GPIO.output(self._dc, GPIO.LOW)
        self._spi.writebytes([cmd])

    def data(self, val):
        GPIO.output(self._dc, GPIO.HIGH)
        self._spi.writebytes([val])

    def LCD_Init(self):
        if LCD_Config.GPIO_Init() != 0:
            return -1

        self._spi.max_speed_hz = 40000000

        """Initialize dispaly"""
        self.LCD_Reset()

        self.command(0x36)
        self.data(0x70)  # self.data(0x00)

        self.command(0x3A)
        self.data(0x05)

        self.command(0xB2)
        self.data(0x0C)
        self.data(0x0C)
        self.data(0x00)
        self.data(0x33)
        self.data(0x33)

        self.command(0xB7)
        self.data(0x35)

        self.command(0xBB)
        self.data(0x19)

        self.command(0xC0)
        self.data(0x2C)

        self.command(0xC2)
        self.data(0x01)

        self.command(0xC3)
        self.data(0x12)

        self.command(0xC4)
        self.data(0x20)

        self.command(0xC6)
        self.data(0x0F)

        self.command(0xD0)
        self.data(0xA4)
        self.data(0xA1)

        self.command(0xE0)
        self.data(0xD0)
        self.data(0x04)
        self.data(0x0D)
        self.data(0x11)
        self.data(0x13)
        self.data(0x2B)
        self.data(0x3F)
        self.data(0x54)
        self.data(0x4C)
        self.data(0x18)
        self.data(0x0D)
        self.data(0x0B)
        self.data(0x1F)
        self.data(0x23)

        self.command(0xE1)
        self.data(0xD0)
        self.data(0x04)
        self.data(0x0C)
        self.data(0x11)
        self.data(0x13)
        self.data(0x2C)
        self.data(0x3F)
        self.data(0x44)
        self.data(0x51)
        self.data(0x2F)
        self.data(0x1F)
        self.data(0x1F)
        self.data(0x20)
        self.data(0x23)

        self.command(0x21)

        self.command(0x11)

        self.command(0x29)

    def LCD_Reset(self):
        """Reset the display"""
        GPIO.output(self._rst, GPIO.HIGH)
        time.sleep(0.01)
        GPIO.output(self._rst, GPIO.LOW)
        time.sleep(0.01)
        GPIO.output(self._rst, GPIO.HIGH)
        time.sleep(0.01)

    def LCD_SetWindows(self, Xstart, Ystart, Xend, Yend):
        # set the X coordinates
        self.command(0x2A)
        self.data(0x00)  # Set the horizontal starting point to the high octet
        self.data(Xstart & 0xFF)  # Set the horizontal starting point to the low octet
        self.data(0x00)  # Set the horizontal end to the high octet
        self.data((Xend - 1) & 0xFF)  # Set the horizontal end to the low octet

        # set the Y coordinates
        self.command(0x2B)
        self.data(0x00)
        self.data((Ystart & 0xFF))
        self.data(0x00)
        self.data((Yend - 1) & 0xFF)

        self.command(0x2C)

    def LCD_ShowImage(self, Image, Xstart, Ystart):
        """Set buffer to value of Python Imaging Library image."""
        """Write display buffer to physical display"""
        imwidth, imheight = Image.size
        if imwidth != self.width or imheight != self.height:
            raise ValueError(
                "Image must be same dimensions as display \
                ({0}x{1}).".format(
                    self.width, self.height
                )
            )
        img = np.asarray(Image)
        pix = np.zeros((self.width, self.height, 2), dtype=np.uint8)
        pix[..., [0]] = np.add(
            np.bitwise_and(img[..., [0]], 0xF8), np.right_shift(img[..., [1]], 5)
        )
        pix[..., [1]] = np.add(
            np.bitwise_and(np.left_shift(img[..., [1]], 3), 0xE0),
            np.right_shift(img[..., [2]], 3),
        )
        pix = pix.flatten().tolist()
        self.LCD_SetWindows(0, 0, self.width, self.height)
        GPIO.output(self._dc, GPIO.HIGH)
        for i in range(0, len(pix), 4096):
            self._spi.writebytes(pix[i : i + 4096])

    def LCD_Clear(self):
        """Clear contents of image buffer"""
        _buffer = [0xFF] * (self.width * self.height * 2)
        self.LCD_SetWindows(0, 0, self.width, self.height)
        GPIO.output(self._dc, GPIO.HIGH)
        for i in range(0, len(_buffer), 4096):
            self._spi.writebytes(_buffer[i : i + 4096])
