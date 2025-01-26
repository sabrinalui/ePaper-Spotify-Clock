import os
import subprocess
from time import time
from datetime import datetime
from typing import List, Optional, Tuple

from PIL import Image, ImageFont, ImageDraw, ImageMath

from lib.clock_logging import logger
from lib.display_settings import display_settings

class Draw:
    """ 
    Draw to EPaper - Alex Scott 2024
    Companion functions for Draw() within clock.py for the Spotify EPaper display Clock project

    Functions rely on PIL to draw to a self-stored draw object
    Draw() draws context, date time temp, artist and track info, time since, detailed_weather, and names

    Made in companion with the Waveshare 4.2inch e-Paper Module
    https://www.waveshare.com/wiki/4.2inch_e-Paper_Module
    """
    def __init__(self, local_run: bool = False):
        self.local_run = local_run
        self.width, self.height = 264, 176
        self.ds = display_settings
        self.load_resources()
        self.album_image = None
        self.dt = None
        self.time_str = None

        # Make and get the full path to the 'album_art' directory
        os.makedirs("cache", exist_ok=True)
        os.makedirs("cache/album_art", exist_ok=True)
        self.dir_path = os.path.abspath('cache/album_art')

        self.image_mode = 'L' if self.ds.four_gray_scale else '1'
        if self.ds.four_gray_scale:
            # Create four grayscale color palette
            subprocess.run([
                'convert', '-size', '1x4', 
                'xc:#FFFFFF', 
                'xc:#C0C0C0', 
                'xc:#808080', 
                'xc:#000000', 
                '+append', 
                os.path.join(self.dir_path, 'palette.PNG')
            ], check=True)
        
        self.image_obj = Image.new(self.image_mode, (self.width, self.height), 255)
        self.image_draw = ImageDraw.Draw(self.image_obj)

    def load_resources(self):
        """
        Load local resources. 

        This method loads fonts and icons from the /ePaperFonts and /Icons directories respectively.
        It initializes several instance variables with these resources. The fonts are loaded with 
        different sizes (16, 32, 64) and the icons are loaded as images.

        Fonts:
        - DSfnt16, DSfnt32, DSfnt64: Fonts from the Nintendo-DS-BIOS.ttf file.

        Icons:
            - music_context:
                - playlist_icon: Icon for playlist.
                - artist_icon: Icon for artist.
                - album_icon: Icon for album.
                - dj_icon: Icon for DJ.
                - collection_icon: Icon for collection.
        """
        self.DSfnt16, self.DSfnt24, self.DSfnt32 = None, None, None
        self.playlist_icon, self.artist_icon, self.album_icon, self.dj_icon, self.collection_icon, self.failure_icon = None, None, None, None, None, None
        font_sizes = [16, 24, 32]
        font_files = ['Nintendo-DS-BIOS.ttf']
        for font_file in font_files:
            for size in font_sizes:
                font_attribute = f'DSfnt{size}'
                setattr(self, font_attribute, ImageFont.truetype(f'ePaperFonts/{font_file}', size))

        music_context_icons = ['playlist', 'artist', 'album', 'dj', 'collection', 'failure']
        for icon in music_context_icons:
            setattr(self, f'{icon}_icon', Image.open(f'Icons/music_context/{icon}.png'))


    def clear_image(self) -> None:
        """
        Clears the current image by creating a new blank image filled with the color white (255).
        """
        self.image_obj = Image.new(self.image_mode, (self.width, self.height), 255)
        self.image_draw = ImageDraw.Draw(self.image_obj)

    def save_png(self, file_name: str) -> None:
        """
        Saves the image object as a PNG file.

        Args:
            file_name (str): The name of the file to save the image as.
        """
        output_dir = "test_output"
        os.makedirs(output_dir, exist_ok=True)
        self.image_obj.save(os.path.join(output_dir, f"{file_name}.png"))


    # ---- DRAWING FUNCs ----------------------------------------------------------------------------
    def draw_spot_context(self, context_type: str, context_text: str, context_x: int, context_y: int) -> bool:
        """
        Draws both icon {playlist, album, artist} and context text in the bottom of Spot box.

        Args:
            context_type (str): The type of context (e.g., playlist, album, artist).
            context_text (str): The text to be displayed as the context.
            context_x (int): The x-coordinate of the starting position for drawing the context.
            context_y (int): The y-coordinate of the starting position for drawing the context.

        Returns:
            bool: True if the context was successfully drawn, False otherwise.
        """

        icon_dict = {
            'DJ': self.dj_icon,
            'playlist': self.playlist_icon,
            'album': self.album_icon,
            'artist': self.artist_icon,
            'collection': self.collection_icon
        }

        icon = icon_dict.get(context_type, self.failure_icon)
        icon_x = context_x
        icon_y = context_y - 2
        self.image_obj.paste(icon, (icon_x, icon_y))

        self.image_draw.text((context_x + 20, context_y), context_text, font=self.DSfnt16)
        return True

    def draw_album_image(
        self, 
        image_file_name,
        image_file_path, 
        pos: tuple, 
        convert_image: bool=True,
    ) -> None:
        """
        Draws the album image on the ePaper display.

        Parameters:
        image_file_name (str, optional): The name of the album image file. Defaults to "AlbumImage_resize.PNG".
        pos (tuple, optional): The position (x, y) where the album image should be pasted on the display. Defaults to (0, 0).
        convert_image (bool, optional): Flag indicating whether to convert the image to the specified image mode. Defaults to True.
        """
        if convert_image or self.album_image is None:
            self.album_image = Image.open(f"{image_file_path}{image_file_name}")
            self.album_image = self.album_image.convert(self.image_mode)
            
            if self.ds.four_gray_scale:
                before_dither = time()
                if "NA" in image_file_name:
                    self.dither_album_art("NA")
                else:
                    self.dither_album_art()
                after_dither = time()
                logger.info("* Dithering took %.2f seconds *", after_dither - before_dither)

        chosen_album_image = "cache/album_art/AlbumImage" if "NA" not in image_file_name else "cache/album_art/NA"
        chosen_album_image +=  "_resize"
        chosen_album_image = chosen_album_image.replace("_resize", "_dither") if self.ds.four_gray_scale else chosen_album_image
        self.album_image = Image.open(f"{chosen_album_image}.PNG")

        self.image_obj.paste(self.album_image, pos)


    def draw_large_text(self, text: str, x: int, y: int) -> None:
        """
        Draws text line at the specified position on the image in font size 32.
        """
        self.image_draw.text((x, y), text, font=self.DSfnt32)


    def draw_small_text(self, text: str, x: int, y: int) -> None:
        """
        Draws text line at the specified position on the image in font size 16.
        """
        self.image_draw.text((x, y), text, font=self.DSfnt16)
    
    
    def draw_calendar(self, x: int, y: int) -> tuple:
        self.image_draw.rectangle([(x,y),(270,119)],fill = "#808080")
        now = datetime.now()
        date = now.strftime("%A\n%B %d")
        logger.info(date)
        self.image_draw.text((132, 60), date, font=self.DSfnt32, fill="#ffffff")

    # ---- DRAW MISC FUNCs ----------------------------------------------------------------------------

    def dither_album_art(self, main_image_name: str = "AlbumImage") -> bool:
        """
        Dithers the album art image using the Floyd-Steinberg algorithm.

        The image is resized and the colors are remapped using a palette. The dithered image is then saved to a file.

        Returns:
        bool: True if the dithering was successful, False otherwise.
        """
        # Define the file paths
        palette_path = os.path.join(self.dir_path, 'palette.PNG')
        resize_paths = [os.path.join(self.dir_path, f'{main_image_name}_resize.PNG')]
        dither_paths = [os.path.join(self.dir_path, f'{main_image_name}_dither.PNG')]

        for resize_path, dither_path in zip(resize_paths, dither_paths):
            # Check if the files exist
            if not os.path.exists(resize_path) or not os.path.exists(palette_path):
                logger.error("Error: File %s not found.", resize_path if not os.path.exists(resize_path) else palette_path)
                return False

            # Remap the colors in the image
            start_time = time()
            subprocess.run(['convert', resize_path, '-dither', 'Floyd-Steinberg', '-remap', palette_path, dither_path], check=True)
            end_time = time()
            logger.info("* Dithering %s took %.2f seconds *", os.path.basename(dither_path), end_time - start_time)

            if not os.path.exists(dither_path):
                logger.error("Error: File %s not found.", dither_path)
                return False

            self.album_image = Image.open(dither_path)

        return True


    def get_image_obj(self) -> Image:
        """
        Used in clock.py to be passed into EPD's getBuffer()
        """
        return self.image_obj
