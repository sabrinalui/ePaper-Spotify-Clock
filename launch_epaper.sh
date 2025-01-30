#!/bin/bash
# launch_epaper.sh
# navigate to directory then execute python script
ePaperClockLocation="/home/$USER/ePaper-Spotify-Clock/"

# Initialize our own variables
verbose=0
clock=0
local_run=0

# Parse command-line arguments
while (( "$#" )); do
  case "$1" in
  -v | --verbose)
    verbose=1
    shift
    ;;
  --clock)
    clock=1
    shift
    ;;
  --local_run)
    local_run=1
    shift
    ;;
  *)
    echo "Error: Invalid option"
    exit 1
    ;;
  esac
done

runscript() {
  while true; do
    echo "Starting main.py..."
    
    python_cmd="python3 main.py"
    [ "$verbose" = 1 ] && python_cmd="$python_cmd -v"
    [ "$clock" = 1 ] && python_cmd="$python_cmd --clock"
    [ "$local_run" = 1 ] && python_cmd="$python_cmd --local"

    if [ "$verbose" = 1 ]; then
      $python_cmd
    else
      $python_cmd 2>>failures.txt
    fi

    echo "main.py crashed at: $(date '+%Y-%m-%d %H:%M:%S')" >>failures.txt
    echo "Restarting in 5 seconds..."
    sleep 5
  done
}

cd "$ePaperClockLocation" || { echo "Failed to change directory"; exit 1; }

runscript