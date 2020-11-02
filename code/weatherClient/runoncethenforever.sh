#!/bin/bash
source /home/pi/.virtualenvs/cv/bin/activate && source /home/pi/iBoardBot/code/weatherClient/keys 
python /home/pi/iBoardBot/code/weatherClient/client.py --weatherAPIKey $WEATHER_API_KEY --onceFull
python /home/pi/iBoardBot/code/weatherClient/client.py --weatherAPIKey $WEATHER_API_KEY --hours 5 8 11 13 15
