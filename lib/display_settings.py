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
        """
        # it is not recommended to set sleep_epd to False as it might damage the display
        self.sleep_epd = main_settings["sleep_epd"]
        self.four_gray_scale = main_settings["four_gray_scale"]


display_settings = DisplaySettings()
