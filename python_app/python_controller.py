import hid
import time


class L5PKeyboard:
    VENDOR_ID = 0x048D
    PRODUCT_IDS = [
        0xC995,
        0xC994,
        0xC993,  # 2024
        0xC985,
        0xC984,
        0xC983,  # 2023
        0xC975,
        0xC973,  # 2022
        0xC965,
        0xC963,  # 2021
        0xC955,  # 2020
    ]
    USAGE_PAGE = 0xFF89
    USAGE = 0x00CC

    EFFECTS = {"static": 0x01, "breath": 0x03, "wave": 0x04, "smooth": 0x06}

    def __init__(self):
        self.device = hid.device()
        self.device_path = self._find_device()

        if not self.device_path:
            raise ValueError(
                "Lenovo Legion Keyboard not found. "
                "Ensure you run as administrator if required, and that your model is supported."
            )

        self.device.open_path(self.device_path)

        self.effect = "static"
        self.speed = 1
        self.brightness = 1
        self.colors = [0] * 12  # 4 zones * 3 (R, G, B)
        self.wave_direction = "left"  # 'left' or 'right'
        self._payload_buffer = bytearray(33)
        self._payload_buffer[0] = 0xCC

    def _find_device(self):
        # We search through the connected HID devices
        for dev_info in hid.enumerate(self.VENDOR_ID):
            if dev_info["product_id"] in self.PRODUCT_IDS:
                # Windows uses Usage Pages to distinguish between the various endpoints of the device
                if (
                    dev_info["usage_page"] == self.USAGE_PAGE
                    and dev_info["usage"] == self.USAGE
                ):
                    return dev_info["path"]
        return None

    def _build_payload(self):
        # The payload structure must be exactly 33 bytes for the RGB controller
        for i in range(1, 33):
            self._payload_buffer[i] = 0

        self._payload_buffer[1] = 0x16

        # Effect Type
        self._payload_buffer[2] = self.EFFECTS.get(self.effect, 0x01)

        # Speed and Brightness
        self._payload_buffer[3] = self.speed
        self._payload_buffer[4] = self.brightness

        # RGB applies to Static and Breath effects
        if self.effect in ["static", "breath"]:
            for i in range(12):
                self._payload_buffer[5 + i] = self.colors[i]

        # Wave direction handling
        elif self.effect == "wave":
            if self.wave_direction == "right":
                self._payload_buffer[18] = 0x01
            else:  # left
                self._payload_buffer[19] = 0x01

        return self._payload_buffer

    def refresh(self):
        # Send the feature report using the pre-allocated buffer
        payload = self._build_payload()
        self.device.send_feature_report(payload)

    def set_effect(self, effect):
        if effect not in self.EFFECTS:
            raise ValueError(
                f"Invalid effect. Choose from: {list(self.EFFECTS.keys())}"
            )
        self.effect = effect
        self.refresh()

    def set_speed(self, speed):
        """Speed from 1 (slow) to 4 (fast)"""
        self.speed = max(1, min(4, speed))
        self.refresh()

    def set_brightness(self, brightness):
        """Brightness is typically 1 (Low) or 2 (High)"""
        self.brightness = max(1, min(2, brightness))
        self.refresh()

    def set_colors(self, colors):
        """
        Colors is a list of exactly 12 integers representing the RGB of 4 zones.
        [R1, G1, B1, R2, G2, B2, R3, G3, B3, R4, G4, B4]
        """
        if len(colors) != 12:
            raise ValueError("Colors array must be exactly 12 elements [R,G,B * 4]")
        self.colors = [max(0, min(255, c)) for c in colors]
        self.refresh()

    def set_solid_color(self, r, g, b):
        """Sets the entire keyboard to a single solid RGB color"""
        self.set_colors([r, g, b] * 4)

    def close(self):
        """Closes the connection to the HID device"""
        self.device.close()


if __name__ == "__main__":
    try:
        # Initialize the keyboard
        kb = L5PKeyboard()
        print("Keyboard disconnected and initialized!")

        # 1. Solid Red Example
        print("Setting to solid Red...")
        kb.set_effect("static")
        kb.set_brightness(2)
        kb.set_solid_color(255, 0, 0)
        time.sleep(3)

        # 2. Multi-Zone Colors Example
        print("Setting 4 different zone colors...")
        # Zone 1 (Cyan), Zone 2 (Magenta), Zone 3 (Yellow), Zone 4 (White)
        kb.set_colors([0, 255, 255, 255, 0, 255, 255, 255, 0, 255, 255, 255])
        time.sleep(3)

        # 3. Wave Effect Example
        print("Setting to Right Wave effect...")
        kb.wave_direction = "right"
        kb.set_effect("wave")
        kb.set_speed(3)
        time.sleep(4)

        # 4. Return to solid color before shutting script down
        print("Returning to solid blue.")
        kb.set_effect("static")
        kb.set_solid_color(0, 50, 255)

        kb.close()
        print("Done!")

    except Exception as e:
        print(f"Error: {e}")
