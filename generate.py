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

_my_path = os.path.realpath(os.path.dirname(__file__))

_url_confirmed_cases = "https://covid19.srs.care/boards/people-location/confirmed"
_url_active_cases = "https://covid19.srs.care/boards/people-location/active"

_layers = ( (_url_confirmed_cases, "b",),
            (_url_active_cases, "r",),
              )


_maps_cfg_file = os.path.join(_my_path, "maps", "maps.ini")

_Map = collections.namedtuple("Map", ("image", "coord_n", "coord_e", "coord_s", "coord_w", "id"))

_re_float_num = re.compile("(\-)?[0-9]+\.[0-9]+")
_re_int_num = re.compile("(\-)?[0-9]+")

_lat_digits = 2
_long_digits = 3

class Maps:
    def __init__(self, cfg_file):
        self.cfg_filename = cfg_file
        self.maps = []
        self._read()
        
        
    def _read(self):
        reader = configparser.ConfigParser()
        reader.read(self.cfg_filename)
        
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
            map = _Map(*v)
            self.maps.append(map)

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
    colors = []
    for url, color in _layers:
        print("getting %s"%(url,))
        json = requests.post(url).json()
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
        colors.append(color)
    
    # output directory
    index = 1
    while True:
        dir = time.strftime("%y%m%d") + ("" if index == 1 else ".%i"%index)
        if not os.path.exists(dir):
            os.mkdir(dir)
            break
        index += 1
    
    for map in maps.maps:
        print("Generating %s"%(map.id,))
        print("Reading %s"%(map.image,))
        
        fig = plt.figure(frameon=False)
        #fig, ax = plt.subplots()
        
        ax = plt.Axes(fig, [0., 0., 1., 1.])
        ax.set_axis_off()
        fig.add_axes(ax)
        
        ruh_m = plt.imread(map.image)
        
        print("Adding points...")
        
        for set, color in zip(data, colors):
            for point in set:
                long = point["longitude"]
                lat = point["latitude"]
                #print("Checking %s, %s"%(lat, long,))
                if long < map.coord_w or long > map.coord_e or lat < map.coord_s or lat > map.coord_n: 
                    continue
                #print("Adding %s, %s"%(lat, long,))
                ax.scatter(long, lat, zorder=1, alpha= 0.4, c=color, s=3)
                
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