import os
import requests
import sys
import threading
from time import sleep
from datetime import datetime as dt
from PIL import Image
from typing import NoReturn, Optional, Tuple
from zoneinfo import ZoneInfo

from lib.display_settings import DisplaySettings, display_settings
from lib.draw import Draw
from lib.spotify_user import SpotifyTrackMetadata, SpotifyUser
from lib.clock_logging import logger

class Calendar:
    def __init__(self) -> None:
        logger.info("\n\t-- Calendar Init --\n-----------------------------------------------------------------------------------------------------")
        self.local_run: bool = False
        try:
            from waveshare_epd import epd2in7_V2 # type: ignore
        except ImportError:
            self.local_run = True

        # EPD vars/settings
        self.ds: DisplaySettings = display_settings
        self.epd: Optional[None] = None
        if not self.local_run:
            self.epd = epd2in7_V2.EPD()
        self.did_epd_init: bool = False

        # Initialize Info/Drawing Libs/Users
        self.image_obj: Draw = Draw(self.local_run)
        self.spotify_user: SpotifyUser = SpotifyUser()


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

    def draw(self):
        start = dt.now()

        # If track info has changed from cache or is > 1h stale, draw new image.
        last_drawn_track = self.spotify_user.read_track_from_cache()
        most_recent_track = self.spotify_user.get_most_recent_spotipy_info()
        should_download_album = True
        should_redraw = True
        if most_recent_track is None:
            logger.error("Failed to fetch Spotify info remotely, reading from cache...")
            if last_drawn_track is None:
                logger.error("Failed to fetch Spotify info from cache.")
                most_recent_track = SpotifyTrackMetadata(
                    track_name="N/A",
                    artist_name="N/A",
                    context_type="N/A",
                    context_name="N/A",
                    track_image_link="N/A",
                    album_name="N/A",
                    timestamp=dt.now(),
                )
            else:
                logger.error(f"Successfully fetched last track from cache: {last_drawn_track}")
                most_recent_track = last_drawn_track
                should_redraw = False
        if most_recent_track is not None and last_drawn_track is not None:
            time_elapsed_since_last_draw = dt.now() - dt.fromtimestamp(last_drawn_track.timestamp)
            should_redraw = (
                last_drawn_track != most_recent_track
                or time_elapsed_since_last_draw.total_seconds() > 3600
            )
            should_download_album = (
                last_drawn_track.album_name != most_recent_track.album_name
            )
        if should_redraw:
            self.image_obj.clear_image()
            self.build_image(most_recent_track, should_download_album)
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
                
                self.did_epd_init = True

            if self.did_epd_init and not self.local_run:
                logger.info("Drawing image to EPD")
                if self.ds.four_gray_scale:
                    self.epd.display_4Gray(self.epd.getbuffer_4Gray(self.image_obj.get_image_obj()))
                else:
                    self.epd.display(self.epd.getbuffer(self.image_obj.get_image_obj()))
            self.spotify_user.write_track_to_cache(most_recent_track)

        if self.did_epd_init and self.ds.sleep_epd:
            logger.info("Sleeping EPD")
            self.epd.sleep()
            self.did_epd_init = False
        
        end = dt.now()
        time_elapsed = end - start
        logger.info(f"tick_tock() took {time_elapsed.total_seconds()} seconds")


    def build_image(
            self, 
            track: Optional[SpotifyTrackMetadata] = None,
            should_download_album: bool = True,
        ) -> None:
        """
        Main draw function for the ePaper display.
        """
        # Fetch most recent spotify activity
        if track is None:
            track = self.spotify_user.get_most_recent_spotipy_info()
            logger.info(f"Fetched most recent Spotify track: {track}")
        self.build_album_art(track, should_download_album, (0, 0))
        self.build_calendar(121, 0)
        self.build_track_info(track, 10, 128)
        self.save_local_file()  # save image locally for debugging


    def build_calendar(self, x: int, y: int) -> None:
        pacific_tz = ZoneInfo("America/Los_Angeles")
        pacific_now = dt.now(pacific_tz)
        self.image_obj.draw_calendar(pacific_now, x, y)


    def build_album_art(
        self, 
        track: SpotifyTrackMetadata,
        should_download_album: str,
        pos: Tuple[int, int],
    ) -> None:
        did_refresh_album_art = False
        local_dir = "cache/album_art/"
        image_name = "AlbumImage_resize.PNG"
        if should_download_album or not os.path.exists(f"{local_dir}{image_name}"):
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
        self.image_obj.draw_spot_context(track.context_type, track.context_name, x, y + 30)
