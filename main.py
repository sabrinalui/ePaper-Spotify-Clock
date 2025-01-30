from datetime import datetime as dt
from gpiozero import Button
import logging
from threading import Lock

from lib.arg_parser import args
from lib.calendar import Calendar


REFRESH_INTERVAL_SEC = 180

if __name__ == "__main__":
    logging.getLogger().setLevel(logging.INFO)

    calendar = Calendar()
    draw_lock = Lock()

    if args.local:
        calendar.build_image()
    else:
        refresh_button = Button(5)
        last_refreshed_time = dt.min
        while True:
            # Check if refresh button was pressed
            if refresh_button.is_pressed:
                with draw_lock:
                    calendar.draw()
                    last_refreshed_time = dt.now()
            # Check if it's time to schedule a refresh (every 3 min)
            if dt.now() - last_refreshed_time >= REFRESH_INTERVAL_SEC:
                with draw_lock:
                    calendar.draw()
                    last_refreshed_time = dt.now()