from datetime import datetime as dt
from gpiozero import Button
import logging
import time
from threading import Lock, Thread

from lib.arg_parser import args
from lib.calendar import Calendar


REFRESH_INTERVAL_SEC = 180

if __name__ == "__main__":
    logging.getLogger().setLevel(logging.INFO)

    calendar = Calendar()
    draw_lock = Lock()

    def refresh_loop():
        global last_refreshed_time
        while True:
            with draw_lock:
                print("drawing from refresh_loop")
                calendar.draw()
                last_refreshed_time = dt.now()
            time.sleep(REFRESH_INTERVAL_SEC)  # Sleep for refresh interval

    def button_listener():
        global last_refreshed_time
        while True:
            if refresh_button.is_pressed:
                with draw_lock:
                    print("drawing from button_listener")
                    calendar.draw()
                    last_refreshed_time = dt.now()
            time.sleep(0.1)  # Prevent busy-waiting

    if args.local:
        calendar.build_image()
    else:
        refresh_button = Button(5)
        last_refreshed_time = dt.min

        refresh_thread = Thread(target=refresh_loop, daemon=True)
        button_thread = Thread(target=button_listener, daemon=True)

        refresh_thread.start()
        button_thread.start()

        refresh_thread.join()
        button_thread.join()
