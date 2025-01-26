import json

from lib.clock_logging import logger

class DisplaySettings:
    def __init__(self):
        with open("config/display_settings.json", encoding="utf-8") as f:
            settings = json.load(f)
            # main settings
            self.load_main_settings(settings["main_settings"])

    def load_main_settings(self, main_settings: dict) -> None:
        """
        Load the main settings from the provided dictionary.

        Parameters:
        main_settings (dict): A dictionary containing the main settings.

        Raises:
        ValueError: If partial updates are enabled in 4 Gray Scale mode.
        """
        # am/pm or 24 hour clock
        self.twenty_four_hour_clock = main_settings["twenty_four_hour_clock"]
        self.partial_update = main_settings["partial_update"]
        # it is not recommended to set sleep_epd to False as it might damage the display
        self.sleep_epd = main_settings["sleep_epd"]
        self.four_gray_scale = main_settings["four_gray_scale"]
        # Use WaveShare's 4in2epd.py or 4in2epdv2.py
        self.use_epd_lib_V2 = main_settings["use_epd_libV2"]

        if self.partial_update and self.four_gray_scale:
            raise ValueError("Partial updates are not supported in 4 Gray Scale, you must choose one or another")

display_settings = DisplaySettings()
