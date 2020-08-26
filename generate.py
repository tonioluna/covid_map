
# -*- coding: utf-8 -*-
import os
import sys
import configparser
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import collections
import requests
import re
import time
import traceback
import math
import codecs

_my_path = os.path.realpath(os.path.dirname(__file__))

_url_confirmed_cases = "https://covid19.srs.care/boards/people-location/confirmed"
_url_active_cases = "https://covid19.srs.care/boards/people-location/active"

_true_values = ("true", "yes", "1", "sure", "why_not")
_false_values = ("false", "no", "0", "nope", "no_way")

_Layer = collections.namedtuple("Layer", ("url", "color", "id"))
_layers = ( _Layer(_url_confirmed_cases, "b", "Total Cases"),
            _Layer(_url_active_cases,    "r", "Active Cases"),
              )


_maps_cfg_file = os.path.join(_my_path, "maps", "maps.ini")

_Map = collections.namedtuple("Map", ("image", "coord_n", "coord_e", "coord_s", "coord_w", "id", "enabled"))
_City = collections.namedtuple("City", ("name", "latitude", "longitude"))

_re_float_num = re.compile("(\-)?[0-9]+\.[0-9]+")
_re_int_num = re.compile("(\-)?[0-9]+")

_lat_digits = 2
_long_digits = 3

class Maps:
    def __init__(self, cfg_file):
        self.cfg_filename = cfg_file
        self.maps = []
        self.cities = []
        self._read()
        
        
    def _read(self):
        reader = configparser.ConfigParser()
        with codecs.open(self.cfg_filename, "r", "utf8") as fh:
            reader.read_file(fh)
            
        for i in range(0, int(reader.get("global", "map_count"))):
            section = "map_%i"%(i)
            image = os.path.join(os.path.dirname(self.cfg_filename), reader.get(section, "image"))
            assert os.path.isfile(image), "Map image does not exist: %s"%(image,)
            coords = [float(v.strip()) for v in reader.get(section, "coordinates").split(",")]
            assert len(coords) == 4, "Expected 4 coordinates, got %i: %s"%(len(coords), repr(coords))
            id = reader.get(section, "id")
            v = []
            v.append(image)
            v.extend(coords)
            v.append(id)
            enabled = True
            if reader.has_option(section, "enabled"):
                enabled = strToBool(reader.get(section, "enabled"))
            v.append(enabled)
            map = _Map(*v)
            self.maps.append(map)
        
        # Read cities
        v = reader.get("cities", "cities")
        for line in v.split("\n"):
            if line.startswith("#"):
                continue
            city, coords = [i.strip() for i in line.split(":")]
            long, lat = [float(v.strip()) for v in coords.split(",")]
            city = _City(city, lat, long)
            self.cities.append(city)
            print("Read %s"%(city,))
    
    def _get_coord_distance(self, lat1, lon1, lat2, lon2):
        # approximate radius of earth in km
        R = 6373.0

        lat1 = math.radians(lat1)
        lon1 = math.radians(lon1)
        lat2 = math.radians(lat2)
        lon2 = math.radians(lon2)

        dlon = lon2 - lon1
        dlat = lat2 - lat1

        a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        distance = R * c

        return distance
    
    def get_closest_city(self, lat, long):
        dists = {}
        for city in self.cities:
            d = self._get_coord_distance(lat, long, city.latitude, city.longitude)
            dists[d] = city
        keys = list(dists.keys())
        keys.sort()
        city = dists[keys[0]].name
        #print("Closest city to %s, %s: %s (%.2f km)"%(lat, long, city, keys[0]))
        return city, keys[0]

def strToBool(txt):
    txtl = txt.lower()
    if txtl in _true_values: return True
    if txtl in _false_values: return False
    raise Exception("Cannot convert %s to bool. Accepted values: (For True) %s, (For False) %s"
                    ""%(repr(txt), ",".join(_true_values), ",".join(_false_values),))

def _get_coord(point, coord, digits):
    m = _re_float_num.search(point[coord])
    if m == None:
        mi = _re_int_num.search(point[coord])
        if mi != None:
            n = int(mi.group())
            sign = -1 if n <= 0 else 1
            n = abs(n)
            n = "%i"%n
            n = n[0:digits] + "." + n[digits:]
            n = float(n) * sign
            print("Warning: %s converted, %s -> %s"%(coord, point[coord], n))
        else:
            assert m != None, "Invalid %s: %s"%(coord, repr(point[coord]))
    else:
        n = float(m.group())
    
    return n

def main():
    maps = Maps(_maps_cfg_file)
    
    data = []
    for layer in _layers:
        print("getting %s"%(layer.url,))
        json = requests.post(layer.url).json()
        print("parsing data...")
        l = []
        for point in json:
            try:
                long = _get_coord(point, "longitude", _long_digits)
                lat = _get_coord(point, "latitude", _lat_digits)
            except Exception as ex:
                print(repr(ex))
                #print(traceback.format_exc())
                continue
            l.append(dict(latitude = lat, longitude = long))
        data.append(l)
    
    # output directory
    index = 1
    while True:
        dir = time.strftime("%y%m%d") + ("" if index == 1 else ".%i"%index)
        if not os.path.exists(dir):
            os.mkdir(dir)
            break
        index += 1
    
    for map in maps.maps:
        if not map.enabled:
            continue
        print("\n****** Generating %s ******"%(map.id,))
        print("Reading %s"%(map.image,))
        
        fig = plt.figure(frameon=False)
        #fig, ax = plt.subplots()
        
        ax = plt.Axes(fig, [0., 0., 1., 1.])
        ax.set_axis_off()
        fig.add_axes(ax)
        
        ruh_m = plt.imread(map.image)
        
        print("Adding points...")
        
        for set, layer in zip(data, _layers):
            print(">>>> %s"%(layer.id,))
            index = 0
            distances = {}
            for point in set:
                long = point["longitude"]
                lat = point["latitude"]
                #print("Checking %s, %s"%(lat, long,))
                if long < map.coord_w or long > map.coord_e or lat < map.coord_s or lat > map.coord_n: 
                    continue
                #print("    %s %i: New point %s, %s"%(color, index, lat, long,))
                city, distance = maps.get_closest_city(lat, long)
                if city not in distances:
                    distances[city] = [0, 0]
                distances[city][0] += 1
                distances[city][1] = max(distances[city][1], distance)
                
                ax.scatter(long, lat, zorder=1, alpha= 0.4, c=layer.color, s=3)
                index += 1
            cities = list(distances.keys())
            cities.sort()
            for city in cities:
                count, max_distance = distances[city]
                if max_distance > 3.5:
                    print("WARNING\n"*5)
                print("  > %3i %s at max distance %.2f km from %s"%(count, layer.id, max_distance, city))
            
        #ax.set_title(map.id)
        ax.set_xlim(map.coord_w, map.coord_e)
        ax.set_ylim(map.coord_s, map.coord_n)
        
        plt.imshow(ruh_m, zorder=0, extent = (map.coord_w, map.coord_e, map.coord_s, map.coord_n), aspect= 'equal')
        filename = os.path.join(dir, map.id + ".png")
        print("Saving %s"%(filename,))
        plt.savefig(fname = filename, dpi=800, aspect = "equal", bbox_inches='tight', pad_inches=0)
        plt.close()
        
    
    
if __name__ == "__main__":
    main()