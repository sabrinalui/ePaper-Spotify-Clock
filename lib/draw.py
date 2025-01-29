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
        self.DSfnt10, self.DSfnt20, self.DSfnt32 = None, None, None
        self.playlist_icon, self.artist_icon, self.album_icon, self.dj_icon, self.collection_icon, self.failure_icon = None, None, None, None, None, None
        font_sizes = [10, 20, 32]
        font_files = ['NDS12.ttf']
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
    def draw_spot_context(self, context_type: str, context_text: str, x: int, y: int) -> bool:
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
        icon_x = x - 1
        icon_y = y - 2
        self.image_obj.paste(icon, (icon_x, icon_y))

        self.draw_text_wrapped(
            text=context_text,
            font=self.DSfnt10,
            init_x=x,
            init_y=y,
            width=self.width-x,
            textcolor='#000000',
            indent=18,
        )
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
        if convert_image:
            album_image = Image.open(f"{image_file_path}{image_file_name}")
            album_image = album_image.convert(self.image_mode)
            
            if self.ds.four_gray_scale:
                before_dither = time()
                if "NA" in image_file_name:
                    album_image_filepath = self.dither_album_art("NA")
                else:
                    album_image_filepath = self.dither_album_art()
                after_dither = time()
                logger.info("* Dithering took %.2f seconds *", after_dither - before_dither)
                album_image = Image.open(album_image_filepath)

        self.image_obj.paste(album_image, pos)


    def draw_large_text(self, text: str, x: int, y: int) -> None:
        """
        Draws text line at the specified position on the image in font size 32.
        """
        self.image_draw.text((x, y), text, font=self.DSfnt20)


    def draw_small_text(self, text: str, x: int, y: int, width: int, linespacing: int = 0) -> int:
        """
        Draws text line at the specified position on the image in font size 12.
        """
        width = min(self.width, width)
        return self.draw_text_wrapped(
            text, self.DSfnt10, x, y, width, '#000000', linespacing,
        )


    def draw_text_wrapped(
        self, text, font, init_x, init_y, width, textcolor, linespacing=0, indent=0,
    ) -> int:
        """Draw text in an image, wrapping to a second line as needed.
        Max two lines, cutoff with "...". Returns the total text height drawn.

        text:      a long string, without newlines
        font:      a PIL ImageFont object
        width:     width of the area available for text
        init_x
        init_y
        textcolor: a color specifier string
        linespacing: extra space between lines (default 0)
        """
        if not text.strip():
            return init_y

        # Find a first line that fits
        def find_end_of_line(str, w):
            left, top, right, bottom = font.getbbox(str)

            avg_char_width = w / len(str)

            end_index = int(w / avg_char_width)
            if end_index >= len(str):
                end_index = len(str)
            while end_index >= 0:
                if end_index == len(str) or str[end_index-1].isspace():
                    left, top, right, bottom = font.getbbox(str[:end_index])
                    if right - left < w:
                        # It fits
                        break
                # Doesn't fit yet, reduce line size by 1 and try again.
                end_index -= 1

            return end_index, bottom

        first_line_end, bottom = find_end_of_line(text, width - indent)
        if first_line_end < 0:
            # Can't fit one word... just overflow
            self.image_draw.text((init_x + indent, init_y), text,
                font=font, fill=textcolor)
            return init_y + bottom

        # Now end is the index where we'll break
        left, top, right, bottom = font.getbbox(text[:first_line_end])
        self.image_draw.text((init_x + indent, init_y), text[:first_line_end],
            font=font, fill=textcolor)

        if first_line_end == len(text):
            return init_y + bottom
        if text[first_line_end].isspace():
            first_line_end += 1
        
        second_line_init_y = init_y + bottom + linespacing
        remaining_text = text[first_line_end:]
        second_line_end, second_bottom = find_end_of_line(remaining_text, width)
        second_line_text = remaining_text
        if 0 < second_line_end < len(remaining_text):
            # We couldn't fit in two lines so just cut off with '...'
            second_line_text = f"{remaining_text[:second_line_end]}..."
        self.image_draw.text(
            (init_x, second_line_init_y), 
            second_line_text,
            font=font, 
            fill=textcolor,
        )
        return second_line_init_y + second_bottom


    def draw_calendar(self, dt: datetime, x: int, y: int) -> tuple:
        self.image_draw.rectangle([(x,y),(self.width, self.height)],fill = "#808080")    
        date = dt.strftime("%A %b %d")
        self.image_draw.text((x + 10, y + 8), date, font=self.DSfnt20, fill="#ffffff")
        self.image_draw.text((x + 10, y + 35), self.get_greeting(dt), font=self.DSfnt10, fill="#ffffff")

    def get_greeting(self, dt: datetime) -> str:
        if 6 <= dt.hour < 12:
            msg = "gm"
        elif 12 <= dt.hour < 20:
            msg = "hi"
        else:
            msg = "gn"
        msg += " r \u2665"
        return msg

    # ---- DRAW MISC FUNCs ----------------------------------------------------------------------------

    def dither_album_art(self, main_image_name: str = "AlbumImage") -> Optional[str]:
        """
        Dithers the album art image using the Floyd-Steinberg algorithm.

        The image is resized and the colors are remapped using a palette. The dithered image is then saved to a file.

        Returns:
        str: dithered image filepath if the dithering was successful, None otherwise.
        """
        # Define the file paths
        palette_path = os.path.join(self.dir_path, 'palette.PNG')
        resize_path = os.path.join(self.dir_path, f'{main_image_name}_resize.PNG')
        dither_path = os.path.join(self.dir_path, f'{main_image_name}_dither.PNG')

        # Check if the files exist
        if not os.path.exists(resize_path) or not os.path.exists(palette_path):
            logger.error("Error: File %s not found.", resize_path if not os.path.exists(resize_path) else palette_path)
            return None

        # Remap the colors in the image
        start_time = time()
        subprocess.run(['convert', resize_path, '-dither', 'Floyd-Steinberg', '-remap', palette_path, dither_path], check=True)
        end_time = time()
        logger.info("* Dithering %s took %.2f seconds *", os.path.basename(dither_path), end_time - start_time)

        if not os.path.exists(dither_path):
            logger.error("Error: File %s not found.", dither_path)
            return None

        return dither_path


    def get_image_obj(self) -> Image:
        """
        Used in clock.py to be passed into EPD's getBuffer()
        """
        return self.image_obj
