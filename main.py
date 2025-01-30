from datetime import datetime as dt, timedelta
from gpiozero import Button
import logging
import time
from threading import Event, Lock, Thread
from zoneinfo import ZoneInfo

from lib.arg_parser import args
from lib.calendar import Calendar


REFRESH_INTERVAL_SEC = 180

if __name__ == "__main__":
    logging.getLogger().setLevel(logging.INFO)

    calendar = Calendar()
    draw_lock = Lock()
    stop_event = Event()
    button_cooldown = timedelta(seconds=1)
    last_button_press = dt.min

    def refresh_loop():
        while not stop_event.is_set():
            pacific_tz = ZoneInfo("America/Los_Angeles")
            now = dt.now(pacific_tz)
            if 2 <= now.hour < 6:
                # Don't draw between 2AM and 6AM
                time.sleep(REFRESH_INTERVAL_SEC)
            else:
                with draw_lock:
                    print("Drawing from refresh_loop")
                    calendar.draw()
                time.sleep(REFRESH_INTERVAL_SEC)  # Sleep for refresh interval

    def button_listener():
        while not stop_event.is_set():
            if refresh_button.is_pressed:
                now = dt.now()
                if now - last_button_press > button_cooldown:  
                    last_button_press = now
                    with draw_lock:
                        print("Drawing from button_listener")
                        calendar.draw()
            time.sleep(0.1)  # Prevent busy-waiting

    def thread_supervisor():
        """ Restarts threads if they crash. """
        global refresh_thread, button_thread
        while not stop_event.is_set():
            if not refresh_thread.is_alive():
                print("[WARNING] Refresh thread restarted")
                refresh_thread = Thread(target=refresh_loop, daemon=True)
                refresh_thread.start()

            if not button_thread.is_alive():
                print("[WARNING] Button listener restarted")
                button_thread = Thread(target=button_listener, daemon=True)
                button_thread.start()

            time.sleep(5)  # Check every 5 seconds

    if args.local:
        calendar.build_image()
    else:
        refresh_button = Button(5)

        refresh_thread = Thread(target=refresh_loop, daemon=True)
        button_thread = Thread(target=button_listener, daemon=True)
        supervisor_thread = Thread(target=thread_supervisor, daemon=True)

        refresh_thread.start()
        button_thread.start()
        supervisor_thread.start()

        # Keep main thread alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Shutting down...")
            stop_event.set()
            refresh_thread.join()
            button_thread.join()
            supervisor_thread.join()