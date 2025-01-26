import os
import requests
import sys
import threading
from time import sleep
from datetime import datetime as dt
from PIL import Image
from typing import NoReturn, Optional, Tuple

from lib.display_settings import DisplaySettings, display_settings
from lib.draw import Draw
from lib.spotify_user import SpotifyTrackMetadata, SpotifyUser
from lib.clock_logging import logger

class Clock:
    """
    Clock updates the screen with the current Spotify info, time, date, and weather on a regular loop.
    Clock caches the local context of the Spotify user, and will only update the context if the user has changed.
    """
    def __init__(self) -> None:
        logger.info("\n\t-- Clock Init --\n-----------------------------------------------------------------------------------------------------")
        self.local_run: bool = False
        try:
            from waveshare_epd import epd2in7_V2, epd2in7 # type: ignore
        except ImportError:
            self.local_run = True

        # EPD vars/settings
        self.ds: DisplaySettings = display_settings
        self.epd: Optional[None] = None
        if not self.local_run:
            self.epd = epd2in7_V2.EPD() if self.ds.use_epd_lib_V2 else epd2in7.EPD()
        self.did_epd_init: bool = False
        self.time_elapsed: float = 15.0

        # Initialize Info/Drawing Libs/Users
        self.image_obj: Draw = Draw(self.local_run)
        self.spotify_user: SpotifyUser = SpotifyUser()
        self.last_drawn_track: SpotifyTrackMetadata = SpotifyTrackMetadata()
        self.last_drawn_time: Optional[dt] = None
        self.last_saved_album_name: str = ""


    def save_local_file(self, file_name="output") -> None:
        """
        Saves image for debugging
        """
        self.image_obj.save_png(file_name)

    def init_epd(self) -> NoReturn:
        """
        Used to initialize the EPD display within a thread to prevent blocking the main loop.
        """
        try:
            self.epd.init()
        except RuntimeError as e:
            logger.error("Failed to init EPD: %s", e)

    def tick_tock(self):
        """
        Main loop for the clock functionality.
        """
        while True:
            start = dt.now()
            c_hour = int(start.strftime("%-H"))

            # from 2:01 - 5:59am, don't init the display, return from main, and have .sh script run again in 3 mins
            if 2 <= c_hour < 6:
                if self.did_epd_init:
                    logger.info("Sleeping EPD")
                    self.epd.sleep()
                    self.did_epd_init = False
                logger.info("Sleeping... %s", dt.now().strftime('%-I:%M%p'))
                sleep(180)
                continue

            # If track info has changed, or is > 1h stale, draw new image.
            most_recent_track = self.spotify_user.get_most_recent_spotipy_info()
            time_elapsed_since_last_draw = dt.now() - self.last_drawn_time
            should_redraw = self.last_drawn_track != most_recent_track and (
                time_elapsed_since_last_draw.total_seconds() > 3600
            )
            if should_redraw(most_recent_track):
                self.image_obj.clear_image()
                self.build_image(most_recent_track)
                if not self.did_epd_init and not self.local_run:
                    # try initing the EPD for a total of 45 seconds
                    thread = threading.Thread(target=self.init_epd)
                    thread.start()
                    thread.join(45)
                    if thread.is_alive():
                        logger.error("Failed to init EPD in 45 seconds, exiting.")
                        sys.exit(1)
                    else:
                        logger.info("EPD initialized.")

                    if self.ds.four_gray_scale:
                        logger.info("Initializing EPD 4Gray...")
                        self.epd.Init_4Gray()
                        logger.info("Done initializing EPD 4Gray.")
                    elif self.ds.partial_update:
                        logger.info("Initializing partial EPD...")
                        self.epd.init_fast(self.epd.Seconds_1_5S)
                        logger.info("Done initializing Partial EPD.")
                    
                    self.did_epd_init = True

                if self.did_epd_init and not self.local_run:
                    logger.info("Drawing image to EPD")
                    if self.ds.four_gray_scale:
                        self.epd.display_4Gray(self.epd.getbuffer_4Gray(self.image_obj.get_image_obj()))
                    else:
                        self.epd.display(self.epd.getbuffer(self.image_obj.get_image_obj()))
                    self.last_drawn_track = most_recent_track
                    self.last_drawn_time = dt.now()
                
            if self.did_epd_init and self.ds.sleep_epd and not self.ds.partial_update:
                logger.info("Sleeping EPD")
                self.epd.sleep()
                self.did_epd_init = False
            
            end = dt.now()
            time_elapsed = end - start
            # Sleep for 3 mins
            logger.info(f"tick_tock() took {time_elapsed.total_seconds()} seconds")
            sleep(180)


    def build_image(self, track: Optional[SpotifyTrackMetadata] = None) -> None:
        """
        Main draw function for the ePaper display.
        """
        # Fetch most recent spotify activity
        if track is None:
            track = self.spotify_user.get_most_recent_spotipy_info()
            logger.info(f"Fetched most recent Spotify track: {track}")
        self.build_album_art(track, (0, 0))
        self.build_calendar(121, 0)
        self.build_track_info(track, 12, 135)
        self.save_local_file()  # save image locally for debugging


    def build_calendar(self, x: int, y: int) -> None:
        self.image_obj.draw_calendar(x, y)
    
    def build_album_art(
        self, 
        track: SpotifyTrackMetadata,
        pos: Tuple[int, int],
    ) -> None:
        did_refresh_album_art = False
        if track.track_image_link is None:
            local_dir = "Icons/album_na/"
            image_name = "NA.png"
            logger.warning("No album art found, drawing NA.png")
        else:
            local_dir = "cache/album_art/"
            image_name = "AlbumImage_resize.PNG"
            # If the last image saved doesn't match, we need to fetch new image
            if self.last_saved_album_name != track.album_name or not os.path.exists(f"{local_dir}{image_name}"):
                newly_saved_image = self.fetch_and_resize_album_art(
                    track_image_link=track.track_image_link, 
                    local_dir=local_dir,
                    image_name="AlbumImage.PNG",
                    dimensions=(120, 120),
                )
                if newly_saved_image is None:
                    logger.warning("Failed to save new album image, drawing NA.png")
                    local_dir = "Icons/album_na/"
                    image_name = "NA.png"
                else:
                    local_dir, image_name = newly_saved_image
                    self.last_saved_album_name = track.album_name
                    did_refresh_album_art = True

        self.image_obj.draw_album_image(
            image_file_name=image_name,
            image_file_path=local_dir,
            pos=pos, 
            convert_image=did_refresh_album_art,
        )


    def fetch_and_resize_album_art(
        self,
        track_image_link: str, 
        local_dir: str,
        image_name: str,
        dimensions: Tuple[int, int],
    ) -> Optional[Tuple[int, int]]:
        """
        Downloads the album art from the given track image link and saves it with the specified album image name.
        The downloaded image is then resized.
        
        Args:
            track_image_link (str): The URL of the track image.
            album_image_name (str): The name of the album image file (default is "AlbumImage.PNG").

        Returns:
            (filename, filepath) if the album art was successfully downloaded and resized, else None.
        """
        os.makedirs(local_dir, exist_ok=True)
        try:
            image_data = requests.get(track_image_link, timeout=25).content
        except requests.exceptions.RequestException as e:
            logger.error("Failed to download %s: %s", track_image_link, e)
            return None
        image_path = f"{local_dir}{image_name}"
        with open(image_path, 'wb') as handler:
            handler.write(image_data)

        outfile = os.path.splitext(image_name)[0] + f"_resize.PNG"
        try:
            im = Image.open(image_path)
            im.thumbnail(dimensions)
            im = im.convert("L")
            im.save(f"{local_dir}{outfile}", "PNG")
            return (local_dir, outfile)
        except IOError as e:
            logger.error(f"Failed to resize {image_name}: {e}")
            return None


    def build_track_info(self, track: SpotifyTrackMetadata, x: int, y: int) -> None:
        self.image_obj.draw_small_text(track.track_name, x, y)
        self.image_obj.draw_small_text(track.artist_name, x, y + 15)
        # self.image_obj.draw_spot_context(track.context_type, track.context_name, x, y + 30)
