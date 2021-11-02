#!/bin/bash
# Uncomment line below -- with the '--immediate' if you want to see results
# right away.  
# export IMMEDIATE_SETTING="--immediate"
source /home/pi/.virtualenvs/cv/bin/activate && source /home/pi/iBoardBot/code/weatherClient/keys && python /home/pi/iBoardBot/code/weatherClient/client.py --doIncrementalDaily --weatherAPIKey $WEATHER_API_KEY --hours 7 9 12 13 15 18 $IMMEDIATE_SETTING
