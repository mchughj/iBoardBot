#!/bin/bash
# Uncomment line below -- with the '--immediate' if you want to see results
# right away.  
# export IMMEDIATE_SETTING="--immediate"
source /home/mchughj/iBoardBot/code/server/env/bin/activate && source /home/mchughj/iBoardBot/code/weatherClient/keys && python3.7 /home/mchughj/iBoardBot/code/weatherClient/client.py --doIncrementalDaily --weatherAPIKey $WEATHER_API_KEY --hours 7 9 12 15 18 $IMMEDIATE_SETTING
