import logging
from lib.arg_parser import args
from lib.calendar import Calendar

if __name__ == "__main__":
    logging.getLogger().setLevel(logging.INFO)

    calendar = Calendar()
    if args.local or (calendar.local_run and not args.calendar):
        calendar.build_image()
    else:
        calendar.draw()