
import logging
from dataclasses import dataclass

# Information taken from here https://openweathermap.org/weather-conditions
@dataclass
class WeatherType:
    numericId: int
    description: str
    shorter_description: str
    icon_filename: str

allWeatherTypes = [
    WeatherType( 200, "THUNDERSTORM WITH LIGHT RAIN", "STORM, LT RAIN", "w/storm-light-rain.png"),
    WeatherType( 201, "THUNDERSTORM WITH RAIN", "STORM & RAIN", "w/storm-rain.png"),
    WeatherType( 202, "THUNDERSTORM WITH HEAVY RAIN", "STORM HEAVY RAIN", "w/storm-rain.png"),
    WeatherType( 210, "LIGHT THUNDERSTORM", "LIGHT STORM", "w/storm.png"),
    WeatherType( 211, "THUNDERSTORM", "STORM", "w/storm.png"),
    WeatherType( 212, "HEAVY THUNDERSTORM", "HEAVY STORM", "w/storm-heavy.png"),
    WeatherType( 221, "RAGGED THUNDERSTORM", "RAGGED STORM", "w/storm-heavy.png"),
    WeatherType( 230, "THUNDERSTORM WITH LIGHT DRIZZLE", "STORM & LT DRIZZLE", "w/storm-light-rain.png"),
    WeatherType( 231, "THUNDERSTORM WITH DRIZZLE", "STORM & DRIZZLE", "w/storm-light-rain.png"),
    WeatherType( 232, "THUNDERSTORM WITH HEAVY DRIZZLE", "STORM & H DRIZZLE", "w/storm-rain.png"),
    WeatherType( 300, "LIGHT INTENSITY DRIZZLE", "LIGHT DRIZZLE", "w/rain-light.png"),
    WeatherType( 301, "DRIZZLE", "DRIZZLE", "w/rain-light.png"),
    WeatherType( 302, "HEAVY INTENSITY DRIZZLE", "HEAVY DRIZZLE", "w/rain.png"),
    WeatherType( 310, "LIGHT INTENSITY DRIZZLE RAIN", "LT DRIZZLE RAIN", "w/rain-light.png"),
    WeatherType( 311, "DRIZZLE RAIN", "DRIZZLE RAIN", "w/rain-light.png"),
    WeatherType( 312, "HEAVY INTENSITY DRIZZLE RAIN", "H DRIZZLE RAIN", "w/rain.png"),
    WeatherType( 313, "SHOWER RAIN AND DRIZZLE", "RAIN & DRIZZLE", "w/rain.png"),
    WeatherType( 314, "HEAVY SHOWER RAIN AND DRIZZLE", "RAIN & DRIZZLE", "w/rain.png"),
    WeatherType( 321, "SHOWER DRIZZLE", "SHOWER DRIZZLE", "w/rain.png"),
    WeatherType( 500, "LIGHT RAIN", "LIGHT RAIN", "w/rain-light.png"),
    WeatherType( 501, "MODERATE RAIN", "MODERATE RAIN", "w/rain.png"),
    WeatherType( 502, "HEAVY INTENSITY RAIN", "HEAVY RAIN", "w/rain.png"),
    WeatherType( 503, "VERY HEAVY RAIN", "VERY HEAVY RAIN", "w/rain.png"),
    WeatherType( 504, "EXTREME RAIN", "EXTREME RAIN", "w/rain.png"),
    WeatherType( 511, "FREEZING RAIN", "FREEZING RAIN", "w/rain.png"),
    WeatherType( 520, "LIGHT INTENSITY SHOWER RAIN", "LIGHT RAIN", "w/rain-light.png"),
    WeatherType( 521, "SHOWER RAIN", "RAIN", "w/rain.png"),
    WeatherType( 522, "HEAVY INTENSITY SHOWER RAIN", "HEAVY RAIN", "w/rain.png"),
    WeatherType( 531, "RAGGED SHOWER RAIN", "RAGGED RAIN", "w/rain.png"),
    WeatherType( 600, "LIGHT SNOW", "LIGHT SNOW", "w/snow-light.png"),
    WeatherType( 601, "SNOW", "SNOW", "w/snow.png"),
    WeatherType( 602, "HEAVY SNOW", "HEAVY SNOW", "w/snow.png"),
    WeatherType( 611, "SLEET", "SLEET", "w/snow-rain.png"),
    WeatherType( 612, "LIGHT SHOWER SLEET", "LIGHT SLEET", "w/snow-rain.png"),
    WeatherType( 613, "SHOWER SLEET", "SLEET", "w/snow-rain.png"),
    WeatherType( 615, "LIGHT RAIN AND SNOW", "LIGHT SLEET", "w/snow-rain.png"),
    WeatherType( 616, "RAIN AND SNOW", "RAIN AND SNOW", "w/snow-rain.png"),
    WeatherType( 620, "LIGHT SHOWER SNOW", "LIGHT SLEET", "w/snow-rain.png"),
    WeatherType( 621, "SHOWER SNOW", "SLEET", "w/snow-rain.png"),
    WeatherType( 622, "HEAVY SHOWER SNOW", "HEAVY SLEET", "w/snow-rain.png"),
    WeatherType( 701, "MIST", "MIST", "w/mist.png"),
    WeatherType( 711, "SMOKE", "SMOKE", "w/mist.png"),
    WeatherType( 721, "HAZE", "HAZE", "w/mist.png"),
    WeatherType( 731, "SAND/ DUST WHIRLS", "SAND/DUST", "w/mist.png"),
    WeatherType( 741, "FOG", "FOG", "w/mist.png"),
    WeatherType( 751, "SAND", "SAND", "w/mist.png"),
    WeatherType( 761, "DUST", "DUST", "w/mist.png"),
    WeatherType( 762, "VOLCANIC ASH", "VOLCANIC ASH", "w/mist.png"),
    WeatherType( 771, "SQUALLS", "SQUALLS", "w/Question.png"),
    WeatherType( 781, "TORNADO", "TORNADO", "w/Question.png"),
    WeatherType( 800, "CLEAR SKY", "CLEAR SKY", "w/sunny.png"),
    WeatherType( 801, "FEW CLOUDS", "FEW CLOUDS", "w/clouds-light.png"),
    WeatherType( 802, "SCATTERED CLOUDS", "SCATTERED CLOUDS", "w/clouds-light.png"),
    WeatherType( 803, "BROKEN CLOUDS", "BROKEN CLOUDS", "w/clouds.png"),
    WeatherType( 804, "OVERCAST CLOUDS", "OVERCAST", "w/clouds.png"),
]

def getWeatherTypeByNumericID(id):
    for x in allWeatherTypes:
        if x.id == id:
         return x
    
    logging.warn("getWeatherTypeByNumericID - cannot find requested; id: {}".format(id))
    return None
