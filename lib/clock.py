import json
from time import time, sleep
from datetime import timedelta, datetime as dt
from PIL import ImageMath

from lib.draw import Draw
from lib.weather import Weather
from lib.spotify_user import SpotifyUser
from lib.misc import Misc
from lib.json_io import LocalJsonIO
from lib.clock_logging import logger

class Clock:
    """
    Clock updates the screen with the current Spotify info, time, date, and weather on a regular loop
    Clock caches the local context of the Spotify user, and will only update the context if the user has changed
    Clock will update the weather every 5 minutes
    """
    def __init__(self):
        # -------- Init --------
        self.local_run = False
        try:
            from waveshare_epd import epd4in2
        except ImportError:
            self.local_run = True

        logger.info("\n\t-- Clock Init --\n-----------------------------------------------------------------------------------------------------")
        self.load_display_settings()

        # Initialize Info/Drawing Libs/Users
        self.image_obj = Draw(self.local_run)
        self.weather = Weather()
        self.misc = Misc()
        self.ctx_io = LocalJsonIO()
        self.spotify_user_1 = SpotifyUser(self.name_1, single_user=self.single_user)
        self.ctx_type_1, self.ctx_title_1 = "", ""
        self.old_album_name1, self.album_name_1 = "", ""
        self.spotify_user_2 = (SpotifyUser(self.name_2, main=False) if not self.single_user else None)
        self.ctx_type_2, self.ctx_title_2 = "", ""

        # EPD vars/settings
        self.epd = epd4in2.EPD() if not self.local_run else None
        self.did_epd_init = False
        self.count_to_5 = 0  # count_to_5 is used to get weather every 5 minutes
        self.time_elapsed = 15.0
        self.old_time = None
        self.flip_to_dark = False
        self.get_new_album_art = False if self.single_user else None

        # Weather/Sunset vars
        self.weather_info = None
        self.sunset_info = None
        self.sunset_time_tuple = None

    def load_display_settings(self):
        """
        Load display settings from config/display_settings.json
        """
        with open("config/display_settings.json", encoding="utf-8") as display_settings:
            display_settings = json.load(display_settings)
            main_settings = display_settings["main_settings"]
            clock_names = display_settings["clock_names"]
            single_user_settings = display_settings["single_user_settings"]
            self.sunset_flip = main_settings["sunset_flip"]
            self.twenty_four_hour_clock = main_settings["twenty_four_hour_clock"]
            self.partial_update = main_settings["partial_update"]
            self.time_on_right = main_settings["time_on_right"]
            self.four_gray_scale = main_settings["four_gray_scale"]  
            self.single_user = single_user_settings["enable_single_user"]
            self.album_art_right_side = single_user_settings["album_art_right_side"]
            self.name_1 = clock_names["name_1"]
            self.name_2 = clock_names["name_2"]

            if self.partial_update and self.four_gray_scale:
                raise ValueError("Partial updates are not supported in 4 Gray Scale, you must choose one or another")

    def set_weather_and_sunset_info(self):
        self.weather_info, self.sunset_info = self.weather.get_weather_and_sunset_info()
        flip_to_dark_before = self.flip_to_dark
        if self.sunset_flip:
            self.flip_to_dark = self.misc.has_sun_set(self.sunset_info, self.sunset_flip)
            if not flip_to_dark_before and self.flip_to_dark:
                self.get_new_album_art = True

    def save_local_file(self):
        # avoid saving this for now; maybe come back for it later with program argument
        # self.image_obj.save_png("{}".format(dt.now().strftime("%H:%M:%S")))
        self.image_obj.save_png("now")

    def tick_tock(self):
        while True:
            self.image_obj.clear_image()
            if self.weather_info is None or self.count_to_5 >= 4:
                self.set_weather_and_sunset_info()
            sec_left, time_str = self.get_time_from_date_time()
            logger.info("Time: %s", time_str)
            start = time() # Used to 'push' our clock timing forward to account for EPD time

            # If we have no context read, grab context our cache/context.txt json file
            ctx_full_1, ctx_full_2 = all([self.ctx_type_1, self.ctx_title_1]), all([self.ctx_type_2, self.ctx_title_2])
            if ctx_full_1 or ctx_full_2:
                try:
                    fh = open("cache/context.txt", encoding="utf-8")
                    self.ctx_type_1, self.ctx_title_1, self.ctx_type_2, self.ctx_title_2 = self.ctx_io.read_json_ctx((self.ctx_type_1, self.ctx_title_1), (self.ctx_type_2, self.ctx_title_2))
                    fh.close()
                except (FileNotFoundError, json.JSONDecodeError) as e:
                    logger.error("error reading cache/context.txt -> %s", e)
            if ctx_full_1 and ctx_full_2:
                try:
                    self.ctx_io.write_json_ctx((self.ctx_type_1, self.ctx_title_1), (self.ctx_type_2, self.ctx_title_2))
                except json.JSONDecodeError as e:
                    logger.error("error writing cache/context.txt -> %s", e)
                
            self.build_image()

            # Get 24H clock c_hour to determine sleep duration before refresh
            date = dt.now() + timedelta(seconds=self.time_elapsed)
            c_hour = int(date.strftime("%-H"))
            # c_minute = int(date.strftime("%-M")) # in case we need it later

            # from 2:01 - 5:59am, don't init the display, return from main, and have .sh script run again in 3 mins
            sleeping_hours = 2 <= c_hour and c_hour <= 5
            if sleeping_hours:
                if self.did_epd_init:
                    # in sleep() from epd4in2.py, epdconfig.module_exit() is never called
                    # I hope this does not create long term damage 🤞
                    logger.info("EPD Sleep(ish) ....")
                else:
                    logger.info("Sleeping... %s", dt.now().strftime('%-I:%M%p'))
                break
            elif not self.did_epd_init:
                if not self.local_run:
                    if self.four_gray_scale:
                        logger.info("Initializing EPD 4Gray...")
                        self.epd.Init_4Gray() 
                    elif self.partial_update:
                        logger.info("Initializing Partial EPD...")
                        self.epd.init_Partial()
                    else:
                        logger.info("Initializing EPD...")
                        self.epd.init()
                    self.epd.Clear()
                else:
                    self.save_local_file()
                self.did_epd_init = True

            if self.did_epd_init:
                if not self.local_run:
                    logger.info("\tDrawing Image to EPD")
                    if self.four_gray_scale: 
                        self.epd.display_4Gray(self.epd.getbuffer_4Gray(self.image_obj.get_image_obj()))
                    else:
                        self.epd.display(self.epd.getbuffer(self.image_obj.get_image_obj()))
                    logger.info("\tSleeping EPD")
                    self.epd.sleep()
                    self.did_epd_init = False
                else:
                    logger.info("\tSaving Image Locally")
                    self.save_local_file()

            # Look @ start variable above. find out how long it takes to compute our image
            stop = time()

            self.time_elapsed = stop - start
            remaining_time = sec_left - self.time_elapsed

            if 5 < c_hour and c_hour < 24:
                # 6:00am - 12:59pm update screen every 3 minutes
                logger.info("\t%.2f\tseconds per loop\tsleeping for %d seconds", round(self.time_elapsed, 2), int(remaining_time/1+120))
                # if we do partial updates and darkmode, you get a worrisome zebra stripe artifact on the EPD
                if self.partial_update and not self.flip_to_dark:
                    # Create new time image, push to display, full update after 2 partials
                    partial_update_count = 0
                    while partial_update_count < 3:
                        date = dt.now()
                        sec_left = 62 - int(date.strftime("%S"))

                        if partial_update_count < 2:
                            logger.info("\t%s sleep, partial_update", round(sec_left, 2))
                            sleep(sec_left)
                        else:
                            logger.info("\t%.2f\tseconds per loop\tsleeping for %d seconds", round(self.time_elapsed, 2), int(remaining_time/1+120))
                            sleep(sec_left-self.time_elapsed)

                        if sec_left > 5 and partial_update_count < 2:
                            date = dt.now()
                            time_str = date.strftime("%-H:%M") if self.twenty_four_hour_clock else date.strftime("%-I:%M") + date.strftime("%p").lower()
                            logger.info("\ttimestr:%s", time_str)
                            time_image, time_width = self.image_obj.create_time_text(time_str, self.weather_info)
                            # flip image polarity
                            time_image = ImageMath.eval('255-(a)', a=time_image)
                            if not self.local_run:
                                if self.time_on_right:
                                    self.epd.EPD_4IN2_PartialDisplay(int(self.image_obj.width-5-time_width), 245, int(self.image_obj.width-5), 288, self.epd.getbuffer(time_image))
                                else:
                                    self.epd.EPD_4IN2_PartialDisplay(5, 245, int(5+time_width), 288, self.epd.getbuffer(time_image))
                            else:
                                self.build_image()
                                self.save_local_file()
                        partial_update_count += 1
                else:
                    sleep(max(2+remaining_time+120, 0))
            elif c_hour < 2:
                # 12:00am - 1:59am update screen every 5ish minutes
                logger.info("\t%.2f\tseconds per loop\tsleeping for %d seconds", round(self.time_elapsed, 2), int(remaining_time+240))
                sleep(max(2+remaining_time+240, 0))

            # Increment counter for Weather requests
            self.count_to_5 = 0 if self.count_to_5 == 4 else self.count_to_5 + 1

    def build_image(self):
        # Draw Spotify info before Weather and Date/Time
        if self.weather_info is None:
            self.set_weather_and_sunset_info()

        # --- Spotify User 1 ---
        self.old_album_name1 = self.album_name_1
        track_1, artist_1, time_since_1, tmp_ctx_type_1, tmp_ctn_name_1, track_image_link, self.album_name_1 = self.spotify_user_1.get_spotipy_info()
        if self.single_user and self.album_art_right_side:
            track_line_count, track_text_size = self.image_obj.draw_track_text(track_1, 5, 26)
            self.image_obj.draw_artist_text(artist_1, track_line_count, track_text_size, 5, 26)

            self.ctx_type_1 = tmp_ctx_type_1 if tmp_ctx_type_1 != "" else self.ctx_type_1
            self.ctx_title_1 = tmp_ctn_name_1 if tmp_ctn_name_1 != "" else self.ctx_title_1
            self.image_obj.draw_spot_context(self.ctx_type_1, self.ctx_title_1, 25, 204)

            name_width_1, name_height_1 = self.image_obj.draw_name(self.spotify_user_1.name, 8, 0)
            self.image_obj.draw_user_time_ago(time_since_1, 18+name_width_1, name_height_1//2)
        else:
            track_line_count, track_text_size = self.image_obj.draw_track_text(track_1, 207, 26)
            self.image_obj.draw_artist_text(artist_1, track_line_count, track_text_size, 207, 26)

            self.ctx_type_1 = tmp_ctx_type_1 if tmp_ctx_type_1 != "" else self.ctx_type_1
            self.ctx_title_1 = tmp_ctn_name_1 if tmp_ctn_name_1 != "" else self.ctx_title_1
            self.image_obj.draw_spot_context(self.ctx_type_1, self.ctx_title_1, 227, 204)

            name_width_1, name_height_1 = self.image_obj.draw_name(self.spotify_user_1.name, 210, 0)
            self.image_obj.draw_user_time_ago(time_since_1, 220+name_width_1, name_height_1//2)

        # --- Spotify User 2 or Album Art Display ---
        if not self.single_user:
            track_2, artist_2, time_since_2, tmp_ctx_type_2, tmp_ctn_name_2, track_image_link, _ = self.spotify_user_2.get_spotipy_info()
            track_line_count, track_text_size = self.image_obj.draw_track_text(track_2, 5, 26)
            self.image_obj.draw_artist_text(artist_2, track_line_count, track_text_size, 5, 26)

            ctx_type_2 = tmp_ctx_type_2 if tmp_ctx_type_2 != "" else ctx_type_2
            ctx_title_2 = tmp_ctn_name_2 if tmp_ctn_name_2 != "" else ctx_title_2
            self.image_obj.draw_spot_context(ctx_type_2, ctx_title_2, 25, 204)

            name_width_2, name_height_2 = self.image_obj.draw_name(self.spotify_user_2.name, 8, 0)
            self.image_obj.draw_user_time_ago(time_since_2, 18+name_width_2, name_height_2 /2)
        else:
            get_new_album_art = self.old_album_name1 != self.album_name_1 or self.get_new_album_art
            if get_new_album_art:
                self.misc.get_album_art(track_image_link)
                self.get_new_album_art = False
            album_pos = (201, 0) if self.album_art_right_side else (0, 0)
            context_pos = (227, 204) if self.album_art_right_side else (25, 204)
            self.image_obj.draw_album_image(self.flip_to_dark, pos=album_pos, convert_image=get_new_album_art)
            self.image_obj.draw_spot_context("album", self.album_name_1, context_pos[0], context_pos[1])
            
        self.image_obj.draw_date_time_temp(self.weather_info)
        self.image_obj.draw_border_lines()

        # -------- Dark Mode --------
        # Dark mode ~25 minutes after the sunsets. Determined by the bool sunset_flip
        if self.flip_to_dark:
            self.image_obj.dark_mode_flip()
        if self.partial_update and not self.local_run:
            # partial updates are inverted on the EPD? I don't know why, but it works
            self.image_obj.dark_mode_flip()

    def get_time_from_date_time(self):
        """Return time information from datetime including seconds, time, date, and the current_minute of update.

        Parameters:
            old_min: used to ensure a proper update interval
        Returns:
            sec_left: used to know how long we should sleep for before next update on the current_minute
            time_str: time text to be displayed
            date_str: date text to be displayed
            new_min: will become the old_min var in next call for proper interval
        """
        date = dt.now() + timedelta(seconds=self.time_elapsed)
        am_pm = date.strftime("%p")
        hour = int(date.strftime("%-H"))
        new_min = int(date.strftime("%M")[-1])

        # Here we make some considerations so the screen isn't updated too frequently
        # We air on the side of caution, and would rather add an additional current_minute than shrink by a current_minute
        if self.old_time is not None and (5 < hour and hour < 24):
            # 6:00am - 11:59pm update screen every 3 mins
            while int(abs(self.old_time-new_min)) < 3:
                date = dt.now() + timedelta(seconds=self.time_elapsed)
                new_min = int(date.strftime("%M")[-1])
                sleep(2)
        # 12:00am - 1:59am update screen every 5 mins at least
        elif self.old_time is not None and hour < 2:
            while int(abs(self.old_time - new_min)) < 5:
                date = dt.now() + timedelta(seconds=self.time_elapsed)
                new_min = int(date.strftime("%M")[-1])
                sleep(2)
        # 2:00am - 5:59am check time every 15ish minutes, granularity here is not paramount
        sec_left = 60 - int(date.strftime("%S"))

        time_str = date.strftime("%-H:%M") if self.twenty_four_hour_clock else date.strftime("%-I:%M") + am_pm.lower()
        return sec_left, time_str
