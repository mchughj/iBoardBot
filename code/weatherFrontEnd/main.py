#!/usr/bin/env python3

# Main program for iBoardBot front end

import kivy
import logging
import datetime

from kivy.app import App
from kivy.clock import Clock
from kivy.config import Config
from kivy.graphics import Color, Line
from kivy.lang import Builder
from kivy.network.urlrequest import UrlRequest
from kivy.properties import NumericProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.widget import Widget

from math import cos, sin, pi

WINDOW_WIDTH = 800
WINDOW_HEIGHT = 480

Config.set('graphics', 'width', WINDOW_WIDTH)
Config.set('graphics', 'height', WINDOW_HEIGHT)
Config.set("kivy", "log_level", "debug")


logging.basicConfig(level=logging.DEBUG, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

kv = '''
#:import math math

<ClockNumber@Label>:
    i: 0
    text: str(self.i)
    pos_hint: {"center_x": 0.5+0.42*math.sin(math.pi/6*(self.i-12)), "center_y": 0.5+0.42*math.cos(math.pi/6*(self.i-12))}
    font_size: self.height/16

<ClockWidget>:
    face: face
    ticks: ticks
    pos_hint: {"center_x":0.25, "center_y":0.5}

    FloatLayout:
        id: face
        size_hint: None, None
        pos_hint: {"center_x":0.5, "center_y":0.5}
        size: 0.7*min(root.size), 0.7*min(root.size)
        canvas:
            Color:
                rgb: 0.1, 0.1, 0.1
            Ellipse:
                size: self.size     
                pos: self.pos
        ClockNumber:
            i: 1
        ClockNumber:
            i: 2
        ClockNumber:
            i: 3
        ClockNumber:
            i: 4
        ClockNumber:
            i: 5
        ClockNumber:
            i: 6
        ClockNumber:
            i: 7
        ClockNumber:
            i: 8
        ClockNumber:
            i: 9
        ClockNumber:
            i: 10
        ClockNumber:
            i: 11
        ClockNumber:
            i: 12
    Ticks:
        id: ticks
        r: min(root.size)*0.9/2
        pos_hint: {"center_x":0.5, "center_y":0.5}

<StatusWidget>:
    lastweathertime: lastweathertime
    nextweathertime: nextweathertime
    pos_hint: {"center_x":0.75, "center_y":0.5}
    size_hint: 0.5, 1

    BoxLayout:
        orientation: 'vertical'
        LastWeatherTime:
            id: lastweathertime
            font_size: 30
            size_hint_x: None
            size: self.texture_size
            pos_hint: {'left': 1}
        Label:
            id: nextweathertime
            font_size: 30
            size_hint_x: None
            size: self.texture_size
            pos_hint: {'left': 1}
            text: "Fetching next weather time"

        Button:
            text: 'Update now'
            size_hint: (1,0.2)
            on_press: app.update_weather_now()


<MainScreenWidget>:
    clock: clock
    statuswidget: statuswidget
    FloatLayout:
        id: main
        size_hint: None, None
        pos_hint: {"center_x":0.5, "center_y":0.5}
        size: root.size

        ClockWidget:
            id: clock

        StatusWidget:
            id: statuswidget


'''
Builder.load_string(kv)

class MainScreenWidget(FloatLayout):
    pass

class ClockWidget(FloatLayout):
    pass

class StatusWidget(BoxLayout):
    def update_status(self, dt):
        logging.info("update_status - going to fetch the information from the weather client")
        self.make_update_request()
        Clock.schedule_once(self.update_status, 10)

    def make_update_request(self):
        self.req = UrlRequest('http://localhost:8080/', self._process_result)

    def _process_result(self, request, result):
        lastFullRefresh = result['lastFullRefresh']
        if lastFullRefresh == 0:
            self.lastweathertime.text = "Last refresh: Never"
        else:
            time = datetime.datetime.fromtimestamp(lastFullRefresh)
            self.lastweathertime.text = "Last refresh: {:02d}:{:02d}".format(time.hour, time.minute)

        nextHour = result['nextHourToWakeUp']
        self.nextweathertime.text = "Next refresh: {:02d}:00".format(nextHour)


class LastWeatherTime(Label):
    def __init__(self, **kwargs):
        super(LastWeatherTime, self).__init__(**kwargs)
        self.text = "Fetching last update..."


class Ticks(Widget):
    def __init__(self, **kwargs):
        super(Ticks, self).__init__(**kwargs)
        self.bind(pos=self.update_clock)
        self.bind(size=self.update_clock)

    def update_clock(self, *args):
        self.canvas.clear()
        with self.canvas:
            time = datetime.datetime.now()
            Color(0.2, 0.5, 0.2)
            Color
            Line(points=[self.center_x, self.center_y, self.center_x+0.6*self.r*sin(pi/30*time.second), self.center_y+0.6*self.r*cos(pi/30*time.second)], width=1, cap="round")
            Color(0.3, 0.6, 0.3)
            Line(points=[self.center_x, self.center_y, self.center_x+0.5*self.r*sin(pi/30*time.minute), self.center_y+0.5*self.r*cos(pi/30*time.minute)], width=2, cap="round")
            Color(0.4, 0.7, 0.4)
            th = time.hour*60 + time.minute
            Line(points=[self.center_x, self.center_y, self.center_x+0.3*self.r*sin(pi/360*th), self.center_y+0.3*self.r*cos(pi/360*th)], width=3, cap="round")

class BoardBotFrontEnd(App):
    def build(self):
        self.screen = MainScreenWidget()
        Clock.schedule_interval(self.screen.clock.ticks.update_clock, 1)
        self.screen.statuswidget.update_status(5)
        return self.screen

    def update_weather_now(self):
        logging.info("Going to request update now")
        self.req = UrlRequest('http://localhost:8080/doFull', self._process_result)

    def _process_result(self, request, result):
        logging.info("Request completed: {}".format(str(result)))
        self.screen.statuswidget.make_update_request()


if __name__ == '__main__':
    logging.info("__main__")
    BoardBotFrontEnd().run()
