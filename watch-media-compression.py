#!/usr/bin/python3
"""Media compression monitor script"""
import datetime
import os
import fnmatch
import re
import time
import pprint
import subprocess
import textwrap
import urllib.request
import requests
import json
import objectpath
from pathlib import Path
import psutil
from colorama import Fore
from colorama import Style

import colorama
from pymediainfo import MediaInfo
            
class Utils:
    """Static methods for use by other classes"""

    @staticmethod
    def convert_millis(millis):
        """ Converts milliseconds to HH:MM:SS format."""

        millis = int(millis)
        seconds = (millis/1000)%60
        seconds = int(seconds)
        minutes = (millis/(1000*60))%60
        minutes = int(minutes)
        hours = (millis/(1000*60*60))%24
        if hours < 1:
            hours = 0
            
        return "{:02d}:{:02d}:{:02d}".format(int(hours), int(minutes), int(seconds))

    @staticmethod
    def clear():
        """Clears the screen"""

        _ = subprocess.call('clear' if os.name == 'posix' else 'cls')


class Form:
    """ Handles the 'forms' used on the console."""

    self = ""
    content = ""
    x = 1
    y = 1
    width = 0
    height = 0
    rows, columns = os.popen('stty size', 'r').read().split()

    #pylint: disable-msg=too-many-arguments
    def __init__(self, name, x=1, y=1, width=0, height=0):
        """ Initializes the Form Object."""
        
        self.name = name
        self.x = x
        self.y = y
        self.width = width
        self.height = height
    #pylint: enable-msg=too-many-arguments


    def set_cursor_position(self, y, x):
        """ Used to move the cursor around the console."""

        return '\x1b[%d;%dH' % (y, x)

    def get_content(self):
        """Returns the content of the form."""

        return self.content

    def add_content(self, line):
        """ Adds content to the form."""
        self.content += line

    def render(self):
        """Renders the form on the console."""

        if int(self.width) == 0:
            self.width = len(max(self.content.split("\n"), key=len))
        if int(self.width) > int(self.columns):
            self.width = int(self.columns)
            
        if int(self.width) < len(self.name) + 10:
            self.width = len(self.name) + 10
        
        if self.height == 0:
            self.height = len(self.content.split("\n"))
            
        render_y = self.y
        row_count = 0
        output = ""
        
        output += self.set_cursor_position(self.y, self.x)
        output += (
            (
                Style.BRIGHT +
                Fore.BLUE +
                chr(213) + 4*chr(205) + " {} {}" + chr(184) +
                Style.RESET_ALL
            ).format(
                str(self.name),
                (self.width  - len(self.name) - 7)*chr(205)
            )
        )

        render_y += 1
        row_count += 1
        for line in self.content.split("\n"):
            if row_count <= self.height:
                output += self.set_cursor_position(render_y, self.x)
                output += " "*(self.width+1)
                
                output += self.set_cursor_position(render_y, self.x)
                if line.strip() == '_':
                    output += (
                        (
                            Style.BRIGHT + Fore.BLUE + chr(179) +
                            Style.RESET_ALL + "{:<{width}}" +
                            # Style.BRIGHT + Fore.BLUE + chr(179) +
                            Style.RESET_ALL + "\n"
                        ).format(
                            " ",
                            width=self.width
                        )
                    )
                    render_y += 1
                    row_count += 1
                    
                elif line.strip() != '':
                    output += (
                        (
                            Style.BRIGHT + Fore.BLUE + chr(179) +
                            Style.RESET_ALL + "{:<{width}}" +
                            # Style.BRIGHT + Fore.BLUE + chr(179) +
                            Style.RESET_ALL + "\n"
                        ).format(
                            line,
                            width=self.width
                        )
                    )

                    render_y += 1
                    row_count += 1

        while row_count <= self.height:
            output += self.set_cursor_position(render_y, self.x)
            output += (
                (
                    Style.BRIGHT + Fore.BLUE + chr(179) + "{}" + Style.RESET_ALL
                ).format((self.width)*" ")
            )
            render_y += 1
            row_count += 1

        output += self.set_cursor_position(render_y, self.x)
        output += (Style.BRIGHT + Fore.BLUE + chr(192) + "{}" + chr(217) + Style.RESET_ALL).format((self.width-1)*chr(196))
        render_y += 1
        row_count += 1

        print(output)
        return render_y


class Media:
    """ Object that handles media file information."""

    @staticmethod
    def get_x264_count(path):
        """ Gets the count of x264 media files on the specified path."""

        file_list = []
        for d_name, sd_name, f_list in os.walk(path):
            for file_name in f_list:
                if(
                        not fnmatch.fnmatch(file_name, '*265*') and
                        not fnmatch.fnmatch(file_name, '*HEVC*')
                ):
                    if os.path.exists( os.path.join(d_name, file_name) ):
                        size = os.stat(os.path.join(d_name, file_name)).st_size
                    else:
                        size = 0
                        
                    if size > 200000000:
                        file_list.append(
                            {
                                "path" : os.path.join(d_name, file_name),
                                "size" : size
                            }
                        )
        return file_list

    @staticmethod
    def get_x265_count(path):
        """ Gets the count of x265 media files on the specified path."""

        file_list = []
        for d_name, sd_name, f_list in os.walk(path):
            for file_name in f_list:
                if fnmatch.fnmatch(file_name, '*265*') or fnmatch.fnmatch(file_name, '*HEVC*'):
                    if os.path.exists( os.path.join(d_name, file_name) ):
                        size = os.stat(os.path.join(d_name, file_name)).st_size
                    else:
                        size = 0
                        
                    if size > 200000000:
                        file_list.append(
                            {
                                "path" : os.path.join(d_name, file_name),
                                "size" : size
                            }
                        )
        return file_list

    @staticmethod
    def get_last_line():
        """ Gets the last line of the nohup compression log."""

        with open("/home/plex/h265/mediaCompression.nohup.out") as nohup_file:
            lines = nohup_file.readlines()
            if len(lines) > 0:
                last = lines[-1]
            else:
                last = ""

        return last

    @staticmethod
    def get_conversion_speeds():
        """ Gets the speeds tracked in the nohup compression log."""
        speeds = []
        with open("/home/plex/h265/mediaCompression.nohup.out") as nohup_file:
            for line in nohup_file:
                line = re.findall(r'speed=([0-9\.]+)', line)
                if line:
                    speeds.append(float(line[0]))

        return speeds
        
        

class CompressionWatcher:
    """ Main Compression Watcher applet object."""

    pp = pprint.PrettyPrinter(indent=4)
    rows, columns = os.popen('stty size', 'r').read().split()
    pct_disk_usage = 0
    current_row = 1
    current_partition = ""
    current_file = ""
    current_dest = ""
    conversion_speeds = []

    def __init__(self):
        """ Initializes the CompressionWatcher Object."""

        pass

    def render_summary(self, start_row):
        """ Renders the summary form."""

        x264_episodes = Media.get_x264_count('/Storage/Television/')
        x264_movies = Media.get_x264_count('/Storage/Movies/')
        x265_episodes = Media.get_x265_count('/Storage/Television/')
        x265_movies = Media.get_x265_count('/Storage/Movies/')
        self.conversion_speeds = Media.get_conversion_speeds()
        total_speed = sum(map(float, self.conversion_speeds))

        summary_form = Form('Summary')
        summary_form.x = 1
        summary_form.y = start_row
        summary_form.width = 36

        cpu_temp = float( psutil.sensors_temperatures()['k10temp'][0].current)
        if cpu_temp > 75 :
            cpu_temp = Style.BRIGHT + Fore.RED + str(cpu_temp) + Style.RESET_ALL
        elif cpu_temp > 70:
            cpu_temp = Style.BRIGHT + Fore.YELLOW + str(cpu_temp) + Style.RESET_ALL
        elif cpu_temp > 60:
            cpu_temp = Style.BRIGHT + Fore.GREEN + str(cpu_temp) + Style.RESET_ALL
        elif cpu_temp > 50:
            cpu_temp = Style.BRIGHT + Fore.CYAN + str(cpu_temp) + Style.RESET_ALL
        else:
            cpu_temp = Style.NORMAL + Fore.WHITE + str(cpu_temp) + Style.RESET_ALL
                    
        summary_form.add_content(
            ("""CPU Temp              : {cpu_temp:<15}
_            
x264 Episodes         : {x264ep:<15}
x264 Movies           : {x264mv:<15}
x264 Total Videos     : {x264tot:<15}
_
x265 Episodes         : {x265ep:<15}
x265 Movies           : {x265mv:<15}
x265 Total Videos     : {x265tot:<15}
_
Avg Tel AVC Size      : {avc_tel_avg:<15}
Avg Tel HEVC Size     : {hevc_tel_avg:<15}
Est Tel Utilization   : {tel_util:<15}
_
Avg Movie AVC Size    : {avc_mov_avg:<15}
Avg Movie HEVC Size   : {hevc_mov_avg:<15}
Est Movie Utilization : {mov_util:<15}
_
{white}Avg Conversion Speed  : {avg_spd:<.2f}
{white}Days Until Completion : {eta:<4.4f}"""
            ).format(
                
                cpu_temp = cpu_temp,
                x264ep= Fore.YELLOW + str(len(x264_episodes)) + Style.RESET_ALL,
                x264mv=Fore.YELLOW + str(len(x264_movies)) + Style.RESET_ALL,
                x264tot=Style.BRIGHT + Fore.YELLOW + str(len(x264_episodes) + len(x264_movies)) + Style.RESET_ALL,

                x265ep= Fore.GREEN + str(len(x265_episodes)) + Style.RESET_ALL,
                x265mv=Fore.GREEN + str(len(x265_movies)) + Style.RESET_ALL,
                x265tot=Style.BRIGHT + Fore.GREEN + str(len(x265_episodes) + len(x265_movies)) + Style.RESET_ALL,

                avc_tel_avg= Fore.YELLOW + str( (
                    int(
                        (sum(item['size'] for item in x264_episodes)) 
                        / 
                        len(x264_episodes)
                    
                    )
                ) ) + Style.RESET_ALL,
                
                hevc_tel_avg=Fore.GREEN + str( (
                    int((sum(item['size'] for item in x265_episodes)) / len(x265_episodes))
                ) ) + Style.RESET_ALL,
                tel_util=Style.BRIGHT + Fore.GREEN + str(
                    str(
                        int(
                            (
                                (sum(item['size'] for item in x265_episodes))
                                /
                                len(x265_episodes)
                                *
                                (len(x264_episodes) + len(x265_episodes))
                                /
                                len(self.get_devices('/Storage/Television/'))
                            ) / 38446405000
                        )
                    ) + " %"
                ) + Style.RESET_ALL,

                avc_mov_avg= Fore.YELLOW + str( (int((sum(item['size'] for item in x264_movies)) / (len(x264_movies) + 1) )) ) + Style.RESET_ALL,
                hevc_mov_avg=Fore.GREEN + str(int((sum(item['size'] for item in x265_movies)) / (len(x265_movies) + 1) )) + Style.RESET_ALL,
                mov_util=Style.BRIGHT + Fore.GREEN + str(
                    str(
                        int(
                            (
                                (sum(item['size'] for item in x265_movies))
                                /
                                len(x265_movies)
                                *
                                (len(x264_movies) + len(x265_movies))
                                /
                                len(self.get_devices('/Storage/Movies/'))
                            ) / 38446405000
                        )
                    ) + " %"
                ) + Style.RESET_ALL,

                white = Style.BRIGHT + Fore.WHITE,
                avg_spd=total_speed/(len(self.conversion_speeds)+1),
                eta=(
                    (
                        len(x264_episodes)
                        +
                        len(x264_movies)
                    )
                    /
                    ( 1 + (24 * (total_speed/ (1 + len(self.conversion_speeds)))) )
                )
            )
        )

        return summary_form.render()

    def render_file_data(self, start_row):
        """ Renders the conversion file form. """
        file_data_form = Form('File Data', x=1, y=start_row, width=36, height=16)
        new_file = False
        
        try:
            procs = [
                p.info for p in psutil.process_iter(
                    attrs=['pid', 'name', 'cmdline']
                ) if 'ffmpeg' in p.info['name']
            ]
            
            if len(list(procs)) == 0:
                self.current_file = ""
                file_data_form.add_content("Please wait...")
                file_data_form.render()
                return -1
                
            for proc in procs:
                if "-probesize" in proc['cmdline']:
                
                    try:
                        processes = subprocess.check_output(
                            [
                                'lsof', 
                                '-e', '/run/user/1000/doc', 
                                '-e', '/run/user/1000/gvfs', 
                                '-Fn', 
                                '-p', 
                                str(proc['pid']), 
                                '-n'
                            ],
                            stderr=None
                        ).decode('ascii').split("\n")

                        
                            
                        for thread in processes:
                            if "Storage" in thread and "." in thread:
                                if re.findall(r'Television|Movies', thread):
                                    if os.path.isfile( str( thread[1:]).strip() ):
                                        if str(self.current_file).strip() != str(thread[1:]).strip():
                                            self.current_file = str(thread[1:]).strip()
                                            new_file = True
                                            
                                        media_info = MediaInfo.parse(str(thread)[1:])
                                        for track in media_info.tracks:
                                            if track.track_type == 'Video':
                                                self.src_millis = track.duration

                                                file_data_form.add_content(
                                                    ("""Source
FileSize           : {src_file_size:<15,}
Duration           : {src_duration:<15}
Height             : {src_height:<15}
Width              : {src_width:<15}
Framerate          : {src_frame_rate:<15}
Bitrate            : {src_bit_rate:<15}
_
"""                                                 ).format(
                                                        src_file_size=os.path.getsize(str(thread)[1:]),
                                                        src_duration=(Utils.convert_millis(int(float((0 if track.duration is None else track.duration))))),
                                                        src_height=(0 if track.height is None else track.height),
                                                        src_width=(0 if track.width is None else track.width),
                                                        src_frame_rate=(0 if track.frame_rate is None else track.frame_rate),
                                                        src_bit_rate=(0 if track.bit_rate is None else track.bit_rate)
                                                    )
                                                )
                                        
                                    else:
                                        self.current_file = ""
                    except Exception as e:
                        file_data_form.add_content( str(e) )
        except Exception as e:
            file_data_form.add_content( str(e) )
            
        root_directory = Path("/Storage/Misc/tmp/transcoder/")
        for f in root_directory.glob('**/*'):
            if f.is_file():
                try:
                    self.current_dest = str(f)
                    media_info = MediaInfo.parse(f)
                    for track in media_info.tracks:
                        if track.track_type == 'Video':
                            file_data_form.add_content(
                                ("""Destination
FileSize           : {dest_file_size:<15,}
Duration           : {dest_duration:<15}
Height             : {dest_height:<15}
Width              : {dest_width:<15}
Framerate          : {dest_frame_rate:<15}
Bitrate            : {dest_bit_rate:<15}"""
                                ).format(
                                    dest_file_size=os.path.getsize(f),
                                    dest_duration=(
                                        0 if track.duration is None else Utils.convert_millis(int(float(track.duration)))
                                    ),
                                    dest_height=(0 if track.height is None else track.height),
                                    dest_width=(0 if track.width is None else track.width),
                                    dest_frame_rate=(0 if track.frame_rate is None else track.frame_rate),
                                    dest_bit_rate=(0 if track.bit_rate is None else track.bit_rate)
                                )
                            )
                except Exception as e:
                    file_data_form.add_content( str(e) )
            else:
                self.current_dest = ""
        if new_file == True:
            return -1 
        else:
            return file_data_form.render()

    def render_progress(self, start_row, step, clear=False):
        """Renders the progress bar."""
        
        progress_form = Form('Full Refresh Meter', y=start_row, x=1, width=(int(self.columns) - 1))
        if clear:
            progress_form.add_content( " "*((int(self.columns) )))
        else:
            bar = ( chr(219) * ( int((int(self.columns))/60*step) ) ).ljust( (int(self.columns) ) )[0: (int(self.columns) )]
            if step / 60 < .25:
                progress_form.add_content( Fore.CYAN   + bar + Style.RESET_ALL )
            elif step / 60 < .50:
                progress_form.add_content( Fore.GREEN  + bar + Style.RESET_ALL )
            elif step / 60 < .75:
                progress_form.add_content( Fore.YELLOW + bar + Style.RESET_ALL )
            else:
                progress_form.add_content( Fore.RED    + bar + Style.RESET_ALL )

        render = progress_form.render()
        
        print( progress_form.set_cursor_position(progress_form.y + 1, ( int(float(self.columns) / 2 ) ) - 2 ) + str(int(float(step/60*100))) + "%" )
        return render

    def render_poster(self, start_row):
        """Renders an ascii art poster of the currently converting file"""
        poster_form = Form('Poster', y=start_row, x=186, width=43, height=38)
        
        try:
            if "/Television/" in self.current_file:
                req_url = "{}/api/parse/?apikey={}&path=/{}".format(
                    "http://192.168.1.20:8989",
                    "153e4bef80f6465fa20711a0b8469f55",
                    os.path.basename(self.current_file)
                )
                r = urllib.request.urlopen(req_url).read()
                data = r.decode('utf-8')
                tree_obj = objectpath.Tree(json.loads(data))
                json_details = tree_obj.execute("$..*[@.coverType is 'poster'].url")
                 
                if json_details:
                    for entry in json_details:
                        urllib.request.urlretrieve( entry, "/home/plex/h265/poster.jpg")
                        
                        a = 0.4
                        while True:
                            ansi = subprocess.check_output([
                                '/home/plex/.local/bin/img2txt.py',
                                '--ansi',
                                '--antialias',
                                '--maxLen=42',
                                '--targetAspect=' + str(a),
                                '/home/plex/h265/poster.jpg'
                            ]).decode('ascii')
                            a += 0.05
                            if len(ansi.split("\n")) > 40:
                                break
                            
                        poster_form.add_content(
                            ansi
                        )
                    
                else:
                    poster_form.add_content('Please Wait...')
            elif "/Movies/" in self.current_file:
                # there is no parse for radarr, gotta load them all
                req = urllib.request.Request("{}/api/movie/?apikey={}".format("http://192.168.1.20:7878", "d104c6f578054520841c3e6616aba771" ))
                r = urllib.request.urlopen(req).read()
                data = r.decode('utf-8')
                
                radarrObj = objectpath.Tree(json.loads(data))
                json_details = radarrObj.execute(
                    "$.*[@.movieFile.relativePath is \"{}\"].images".format( 
                        os.path.basename(self.current_file)
                    )
                )
                
                if json_details:
                    for entry in json_details:
                        for img in entry:
                            if img['coverType'] == 'poster':
                                urllib.request.urlretrieve( "http://192.168.1.20:7878" + img['url'], "/home/plex/h265/poster.jpg")
                                
                                a = 0.4
                                while True:
                                    ansi = subprocess.check_output([
                                        '/home/plex/.local/bin/img2txt.py',
                                        '--ansi',
                                        '--antialias',
                                        '--maxLen=42',
                                        '--targetAspect=' + str(a),
                                        '/home/plex/h265/poster.jpg'
                                    ]).decode('ascii')
                                    a += 0.05
                                    if len(ansi.split("\n")) > 40:
                                        break
                                    
                                poster_form.add_content(
                                    ansi
                                )
                else:
                    poster_form.add_content('Please Wait...')
            else:
                poster_form.add_content('Please Wait...')
        except Exception as e:
            poster_form.add_content(str(e))
        
        return poster_form.render()
    
    def render_conversions(self, start_row):
        """Renders the file conversion form."""
        
        last_line = Media.get_last_line()
        conversion_form = Form('Conversion Data', y=start_row, x=38, width=(int(self.columns) - 82))
        conversion_form.add_content(Style.BRIGHT + Fore.WHITE + "Source File      " + Style.RESET_ALL + ": " + os.path.basename(self.current_file).ljust(int(self.columns) - 110)[:int(self.columns) - 110] + "\n")
        conversion_form.add_content(Style.BRIGHT + Fore.WHITE + "Encoding Process " + Style.RESET_ALL + ": " + last_line)
        
        
        time_match = re.search(r'([0-9]+:[0-9]+:[0-9.]+)', last_line)
        speed_match = re.search(r'([0-9]+[.]*[0-9]*)x', last_line)
        if time_match is not None and speed_match is not None:
            hour, minute, second = time_match.group(0).split(':')
            dest_millis = ( (int(hour) * 60 * 60 * 1000) + (int(minute) * 60 * 1000) + (int(float(second)) * 1000) )
            
            pct_comp = float(round( (100* float(dest_millis) / float(self.src_millis)),2))
            pct_comp_style = ""
            if pct_comp < 25:
                pct_comp_style = Style.NORMAL + Fore.RED 
            elif pct_comp < 50:
                pct_comp_style = Style.NORMAL + Fore.YELLOW
            elif pct_comp < 90:
                pct_comp_style = Style.BRIGHT + Fore.GREEN
            else:
                pct_comp_style = Style.BRIGHT + Fore.CYAN
            
            time_left = int((float( self.src_millis) - float(dest_millis)) / float( speed_match.group(1) ) )
            time_left_style = ""
            if time_left > 1000 * 60 * 15:
                time_left_style = Style.NORMAL + Fore.RED
            elif time_left > 1000 * 60 * 5:
                time_left_style = Style.NORMAL + Fore.YELLOW 
            elif time_left > 1000 * 60 * 2:
                time_left_style = Style.BRIGHT + Fore.GREEN 
            else:
                time_left_style = Style.BRIGHT + Fore.CYAN
                
            conversion_form.add_content( 
                "{white}Percent Complete : {p}% , {white} ETA: {t}".format(
                    white = Style.BRIGHT + Fore.WHITE,
                    clear = Style.RESET_ALL,
                    p = pct_comp_style + str(round(pct_comp,2)) + Style.RESET_ALL,
                    t = time_left_style + str( Utils.convert_millis( time_left ) ) + Style.RESET_ALL
                )
            )
            
            
        else:
            conversion_form.add_content(Style.BRIGHT + "Percent Complete :" + Style.RESET_ALL + " {}".format( "0" ))

        return conversion_form.render()

    def render_media_info(self, start_row):
        media_form = Form('Media Info', y=start_row, x=38, height=14, width=(int(self.columns) - 82))
        output = ""
        if "/Television/" in self.current_file:
            req_url = "{}/api/parse/?apikey={}&path=/{}".format(
                "http://192.168.1.20:8989",
                "153e4bef80f6465fa20711a0b8469f55",
                os.path.basename(self.current_file)
            )
            req = urllib.request.Request(req_url)
            r = urllib.request.urlopen(req).read()
            data = json.loads( r.decode('utf-8') )
            if 'series' in data and 'episodes' in data and len(data['episodes']) > 0:
                output = ("""        
{seriesTitle} - ({seriesYear}) - Genres: {seriesGenre} - IMDB: {seriesImdb}
{seriesOverview}
_
Network: {seriesNetwork} - Seasons: {seasonCount} - Status: {seriesStatus}
Path: {seriesPath}
_
{episodeTitle} - {s00e00} - Air Date: {episodeAirDate} - Runtime: {episodeRuntime} min {clear}
{episodeOverview}
"""             ).format(
                    white = Style.BRIGHT + Fore.WHITE,
                    clear = Style.RESET_ALL,
                    seriesTitle = Style.BRIGHT + Fore.WHITE + str(data['series']['title']) + Style.RESET_ALL,
                    seriesImdb = Style.BRIGHT + Fore.BLUE + str( "https://www.imdb.com/title/" + data['series']['imdbId'] if 'imdbId' in data['series'] else ''),
                    seriesYear = Style.BRIGHT + Fore.GREEN + str( data['series']['year'] ) + Style.RESET_ALL,
                    seriesOverview = textwrap.fill( data['series']['overview'], media_form.width - 1 ) ,
                    seriesNetwork = Fore.RED + str( data['series']['network'] ) + Style.RESET_ALL,
                    seasonCount = Fore.CYAN + str( data['series']['seasonCount'] ) + Style.RESET_ALL,
                    seriesStatus = Style.BRIGHT + Fore.WHITE + str( data['series']['status']) + Style.RESET_ALL,
                    seriesPath = Style.BRIGHT + Fore.CYAN + str(data['series']['path']) + Style.RESET_ALL,
                    seriesGenre = Style.BRIGHT + Fore.YELLOW + str( ", ".join( data['series']['genres'] ) if len( data['series']['genres'] ) > 0 else 'Unknown' ) + Style.RESET_ALL,
                    episodeTitle = Style.BRIGHT + Fore.WHITE + str( data['episodes'][0]['title'] ) + Style.RESET_ALL,
                    episodeAirDate = Style.BRIGHT + Fore.BLUE + str(data['episodes'][0]['airDate']) + Style.RESET_ALL,
                    episodeRuntime = Style.BRIGHT + Fore.BLUE + str(data['series']['runtime']),
                    episodeOverview = textwrap.fill( data['episodes'][0]['overview'], media_form.width - 1),
                    s00e00 = Style.BRIGHT + Fore.GREEN + str( "S" + str(data['episodes'][0]['seasonNumber']).rjust(2,'0') + "E" + str(data['episodes'][0]['episodeNumber']).rjust(2,'0') ) + Style.RESET_ALL
                )
            else:
                media_form.add_content('Please Wait...')
        elif "/Movies/" in self.current_file:
            # there is no parse for radarr, gotta load them all
            req = urllib.request.Request("{}/api/movie/?apikey={}".format("http://192.168.1.20:7878", "d104c6f578054520841c3e6616aba771" ))
            r = urllib.request.urlopen(req).read()
            data = r.decode('utf-8')
            radarrObj = objectpath.Tree(json.loads(data))
            json_details = radarrObj.execute("$..*[@.movieFile.relativePath is \"{}\"]".format( os.path.basename(self.current_file) ))
         
            if json_details:
                for data in json_details:
                    try: 
                        output = ("""        
{movieTitle} - ({movieYear}) - Genres: {movieGenre} - Runtime: {movieRuntime} - IMDB: {movieIMDB}
{movieOverview}
_
Studio: {movieStudio} - Status: {movieStatus}
In Cinemas: {movieInCinemas} - Physical Release: {moviePhysicalRelease}
_
Website: {movieWebsite}
Path: {moviePath}
"""                     ).format(
                            movieStatus = Style.BRIGHT + Fore.WHITE + str(data['status']) + Style.RESET_ALL,
                            movieInCinemas = Style.BRIGHT + Fore.GREEN + str(data['inCinemas'][:10]) + Style.RESET_ALL,
                            moviePhysicalRelease = Style.BRIGHT + Fore.BLUE + (str(data['physicalRelease'] if 'physicalRelease' in data else '')[:10]) + Style.RESET_ALL,
                            movieIMDB = Style.BRIGHT + Fore.WHITE + str("https://www.imdb.com/title/" + data['imdbId']) + Style.RESET_ALL,
                            movieRuntime = Style.BRIGHT + Fore.GREEN + str('{:02d}:{:02d}'.format(*divmod(data['runtime'], 60))) + Style.RESET_ALL ,
                            movieWebsite = Style.BRIGHT + Fore.WHITE + str( data['website'] if 'website' in data else '') + Style.RESET_ALL,
                            movieTitle = Style.BRIGHT + Fore.GREEN + str(data['title']) + Style.RESET_ALL,
                            movieYear = Style.BRIGHT + Fore.GREEN + str(data['year']) + Style.RESET_ALL,
                            movieOverview = textwrap.fill( data['overview'], media_form.width - 1) ,
                            movieStudio = Style.BRIGHT + Fore.RED + str(data['studio']) + Style.RESET_ALL,
                            moviePath = Style.BRIGHT + Fore.CYAN + str(data['path']) + Style.RESET_ALL,
                            movieGenre = Style.BRIGHT + Fore.YELLOW + str(", ".join( data['genres'] ) if len(data['genres']) > 0 else 'Unknown') + Style.RESET_ALL
                        )
                    except Exception as e:
                        output += str(e)
            else:
                media_form.add_content('Please Wait...')
        else:
            media_form.add_content('Please Wait...')
        
        media_form.add_content(output)
        return media_form.render()
        
    def render_procs(self, start_row):
        """Renders the running processes form."""

        procs_form = Form('Processes', y=start_row, x=38, height=17, width=(int(self.columns) - 82))

        procs = []
        for proc in psutil.process_iter():
            if proc:
                try:
                    pinfo = proc.as_dict(attrs=['pid', 'name', 'memory_percent', 'cpu_percent', 'cmdline'])
                    if pinfo['cpu_percent'] > .1 or pinfo['memory_percent'] > .1:
                        cmd = " ".join(pinfo['cmdline'])
                        cmd = cmd.ljust(int(self.columns) - 110)[:int(self.columns) - 110]
                        if cmd.strip() != '':
                            procs.append({
                                'pid' : pinfo['pid'],
                                'mem' : pinfo['memory_percent'],
                                'cpu' : pinfo['cpu_percent'],
                                'cmd' : cmd
                            })
                except:
                    procs.append({'pid' : 0, 'mem': 0, 'cpu': 0, 'cmd' : ''})
        procs_form.add_content((Style.BRIGHT + Fore.BLUE + "{:>7}" + chr(179) + " {:>7}" + chr(179) +" {:>7}" + chr(179) + " {}" + Style.RESET_ALL + "\n").format('PID','CPU','MEM','Command Line' + (' '*(int(self.columns) - 121)  )))
        
                
        procs.sort(key=lambda x: float(x['cpu']), reverse=True)
        count = 0
        for proc in procs:
            count += 1
            if count < 17:
                cmd_style = Style.NORMAL + Fore.WHITE
                mem_style = Style.NORMAL + Fore.WHITE
                if proc['mem'] > 50:
                    mem_style = Style.BRIGHT + Fore.RED
                    cmd_style = Style.NORMAL + Fore.RED
                elif proc['mem'] > 25:
                    mem_style = Style.BRIGHT + Fore.YELLOW
                    cmd_style = Style.NORMAL + Fore.YELLOW
                elif proc['mem'] > 5:
                    mem_style = Style.BRIGHT + Fore.GREEN
                    cmd_style = Style.NORMAL + Fore.GREEN
                elif proc['mem'] > 1:
                    mem_style = Style.BRIGHT + Fore.CYAN
                    cmd_style = Style.NORMAL + Fore.CYAN
                    
                cpu_style = Style.NORMAL + Fore.WHITE
                if proc['cpu'] > 800:
                    cpu_style = Style.BRIGHT + Fore.RED
                    cmd_style = Style.BRIGHT + Fore.RED
                elif proc['cpu'] > 100:
                    cpu_style = Style.BRIGHT + Fore.YELLOW
                    cmd_style = Style.BRIGHT + Fore.YELLOW
                elif proc['cpu'] > 15:
                    cpu_style = Style.BRIGHT + Fore.GREEN
                    cmd_style = Style.BRIGHT + Fore.GREEN
                elif proc['cpu'] > 1:
                    cpu_style = Style.BRIGHT + Fore.CYAN
                    cmd_style = Style.BRIGHT + Fore.CYAN
            
                
            
                procs_form.add_content(
                    (
                        "{pid:>7}" + chr(179) + cpu_style + " {cpu:>7.2f}" + Style.RESET_ALL + chr(179) + mem_style + " {mem:>7.2f}" + Style.RESET_ALL + chr(179) + cmd_style + " {cmd}" + Style.RESET_ALL + "\n"
                    ).format(
                        pid=proc['pid'], cpu=proc['cpu'], mem=proc['mem'], cmd=proc['cmd']
                    )
                )        
                
        return procs_form.render()



    def render_disk_usage(self, paths):
        """ Renders the disk usage form."""
        disk_usage_form = Form('Disk Usage', x=1, y=1, width=228, height=16)
        self.pct_disk_usage = int(self.columns) - 135
        line = [
                Style.DIM    + Fore.MAGENTA + "{:>11}" + Style.RESET_ALL,
                Style.BRIGHT + Fore.BLUE    + "{:22}" + Style.RESET_ALL,
                Style.NORMAL + Fore.WHITE   + "{:>18}" + Style.RESET_ALL,
                Style.BRIGHT + Fore.YELLOW  + "{:>18}" + Style.RESET_ALL,
                Style.BRIGHT + Fore.GREEN   + "{:>18}" + Style.RESET_ALL,
                Style.BRIGHT + Fore.CYAN    + "{:>18}" + Style.RESET_ALL,
                (
                    Style.BRIGHT +
                    Fore.GREEN   +
                    "{:" +
                    str( self.pct_disk_usage - 1) +
                    "}" +
                    Style.RESET_ALL
                ),
                Style.BRIGHT + Fore.WHITE   + "{:>5}"  + Style.RESET_ALL,
                Style.BRIGHT + Fore.WHITE   + "{:>4}" + Style.RESET_ALL,
                Style.BRIGHT + Fore.WHITE   + "{:>5}"   + Style.RESET_ALL,
                Style.BRIGHT + Fore.WHITE   + "{:>5}"   + Style.RESET_ALL
            ]
        headers = (
                (chr(179).join(line)).format(
                    "DEVICE",
                    "MOUNTPOINT",
                    "TARGETSIZE",
                    "USED",
                    "FREE",
                    "AVAILABLE",
                    "USAGE",
                    "PCT",
                    "TEMP",
                    "X264",
                    "X265"
                )
            ) + "\n"
            
        disk_usage_form.add_content(headers)
        for path in paths:
            disk_usage_form.add_content( self.get_disk_usage(path) + "\n" )

        return disk_usage_form.render()

    def get_disk_usage(self, path):
        """ Generates the disk usage specifics on a specified path."""

        results = ""
        self.pct_disk_usage = int(self.columns) - 135

        root_directory = Path(path)
        total_usage = sum(f.stat().st_size for f in root_directory.glob('**/*') if f.is_file())
        devices = self.get_devices(path)
        device_count = len(devices)
        targetsize = int(total_usage/device_count)

        devices.sort(key=lambda x: x.mountpoint)

        for p in devices:
            usage = self.get_partition_info(p)

            line = [
                Style.DIM    + Fore.MAGENTA + "{:>11}" + Style.RESET_ALL,
                Style.BRIGHT + Fore.BLUE    + "{:<22}" + Style.RESET_ALL,
                Style.NORMAL + Fore.WHITE   + "{:18,}" + Style.RESET_ALL,
                Style.BRIGHT + Fore.YELLOW  + "{:18,}" + Style.RESET_ALL,
                Style.BRIGHT + Fore.GREEN   + "{:18,}" + Style.RESET_ALL,
                Style.BRIGHT + Fore.CYAN    + "{:18,}" + Style.RESET_ALL,
                (
                    Style.BRIGHT +
                    Fore.WHITE   +
                    "{:" +
                    str(self.pct_disk_usage) +
                    "}" +
                    Style.RESET_ALL
                ),
                Style.BRIGHT + Fore.WHITE   + "{:4}%"  + Style.RESET_ALL,
                Style.BRIGHT + Fore.WHITE   + "{:>3}C" + Style.RESET_ALL,
                Style.BRIGHT + Fore.WHITE   + "{:5}"   + Style.RESET_ALL,
                Style.BRIGHT + Fore.WHITE   + "{:5}"   + Style.RESET_ALL
            ]

            percent_usage = (
                chr(254) * (int(.01 * self.pct_disk_usage * usage['percent'])) +
                " " * (int(.01 * self.pct_disk_usage * (100 - usage['percent'])))
            )

            percent_usage = (
                Fore.GREEN +
                percent_usage[0:int(targetsize/usage['total']*self.pct_disk_usage)] +
                Fore.WHITE + chr(179) +  Fore.RED +
                percent_usage[int(targetsize/usage['total']*self.pct_disk_usage)+1:]
            )

            results += (
                (chr(179).join(line)).format(
                    p.device,
                    p.mountpoint,
                    targetsize,
                    usage['used'],
                    usage['free'],
                    targetsize - usage['used'],
                    percent_usage,
                    usage['percent'],
                    usage['temp'],
                    usage['x264'],
                    usage['x265']
                )
            ) + "\n"
        return results

    def get_partition_info(self, part):
        """ Gets information about the partitions used for a specified path."""

        usage = psutil.disk_usage(part.mountpoint)

        diskval = {}
        diskval['device'] = part.device
        diskval['mountpoint'] = part.mountpoint
        diskval['total'] = usage.total
        diskval['used'] = usage.used
        diskval['free'] = usage.free
        diskval['percent'] = usage.percent
        diskval['temp'] = (
            subprocess.check_output(['hddtemp', '--numeric', part.device]).decode('ascii').strip()
        )

        file_list = []
        for d_name, sd_name, f_list in os.walk(part.mountpoint):
            for file_name in f_list:
                if(
                        not fnmatch.fnmatch(file_name, '*265*') and
                        not fnmatch.fnmatch(file_name, '*HEVC*')
                ):
                    if os.path.exists( os.path.join(d_name, file_name) ):
                        size = os.stat(os.path.join(d_name, file_name)).st_size
                    else:
                        size = 0
                    
                    if size > 200000000:
                        file_list.append(os.path.join(d_name, file_name))
        diskval['x264'] = len(file_list)

        file_list = []
        for d_name, sd_name, f_list in os.walk(part.mountpoint):
            for file_name in f_list:
                if fnmatch.fnmatch(file_name, '*265*') or fnmatch.fnmatch(file_name, '*HEVC*'):
                    if os.path.exists( os.path.join(d_name, file_name) ):
                        size = os.stat(os.path.join(d_name, file_name)).st_size
                    else:
                        size = 0
                        
                    if size > 200000000:
                        file_list.append(os.path.join(d_name, file_name))
        diskval['x265'] = len(file_list)
        return diskval

    def get_devices(self, path):
        """ Gets all block devices."""
        return list(filter(lambda x: (path in x.mountpoint), psutil.disk_partitions()))
        
    def render_cpu_percent(self, start_row):
        cpus = psutil.cpu_percent(interval=0.1, percpu=True)
        
        cpu_percent_form = Form('CPU Percentage', y=start_row, x=( int(self.columns) - ( 2*len(cpus) + 5) ), width=( 2*len(cpus) + 5), height=22)
        output = ""
        
        for r in range(0,20):
            if r % 5 == 0:
                output += "-" + chr(179) + " "
            else:
                output += " " + chr(179) + " "
            
            for c in cpus:
                if ((20-r)/20*100) > 75:
                    output += Fore.RED
                elif ((20-r)/20*100) > 50:
                    output += Fore.YELLOW
                elif ((20-r)/20*100) > 25:
                    output += Fore.GREEN
                else:
                    output += Fore.CYAN
                
                if c > ((20-r)/20*100):
                    output += chr(219) + " "
                else:
                    output += "  "
                    
                output += Style.RESET_ALL
            output += " \n"
        output += chr(196) + chr(193)
        for r in range(0, ( 2*len(cpus) + 2) ):
            output += chr(196)
        output += "\n"
        n1, n5, n15 = [x / psutil.cpu_count() * 100 for x in psutil.getloadavg()]
        output += "Load: 1M:{:6} 5M:{:6} 15M:{:6}".format( str(round(n1,2)),str(round(n5,2)),str(round(n15,2)))
        
        cpu_percent_form.add_content(output)
        return cpu_percent_form.render()
    
    def render_disk_visualization(self, start_row):
        cpus = psutil.cpu_percent(percpu=True)
        disk_vis_form = Form('Disk Visualization', y=start_row, x=(int(self.columns)-( 2*len(cpus) + 7) - 75), width=76, height=22)
        mountpoint = str( '/'.join( self.current_file.split('/')[0:4] ) )
        devices = list(filter(lambda x: (mountpoint in x.mountpoint), psutil.disk_partitions()))
        
        if mountpoint.strip() != '' and self.current_partition != devices[0].device:        
            self.current_partition = devices[0].device
            outputmap = list()
            for i in range(1500):
                outputmap.append( 0 )
        
            root_directory = Path(mountpoint)
            for f in root_directory.glob('**/*'):
                if f.is_file() and all(ord(c) < 128 for c in str(f)):
                    fileinfo = subprocess.check_output(
                        [
                            'filefrag', 
                            '-b512',
                            '-e',
                            str(f)
                        ],
                        stderr=None
                    ).decode('ascii').split("\n")
                    
                    
                    for i in fileinfo[3:-1]:
                        fields = i.split(':')
                        if len(fields) >= 3 and "Storage" not in fields[0] and fields[2] is not None:                        
                            data = fields[2].split('.')[0]
                            try:
                                maploc = int( int( data ) / 7814035087 *  ( ( int(disk_vis_form.width) - 1 ) * ( int(disk_vis_form.height) - 2 ) ) )
                                outputmap[ maploc ] =  int(outputmap[ maploc ]) + 1 

                            except Exception as e:
                                print(str(e))
                                print(str(f))
            
            index = 0
            results = ""
            line = ""
            # Utils.clear()
            # print(max(outputmap))
            # print(outputmap)
            # time.sleep(10)
            
            
            fileinfo = subprocess.check_output(
                [
                    'filefrag', 
                    '-b512',
                    '-e',
                    str(self.current_file)
                ],
                stderr=None
            ).decode('ascii').split("\n")
            
            
            for i in fileinfo[3:-1]:
                fields = i.split(':')
                if len(fields) >= 3 and "Storage" not in fields[0] and fields[2] is not None:                        
                    data = fields[2].split('.')[0]
                    try:
                        maploc = int( int( data ) / 7814035087 *  ( ( int(disk_vis_form.width) - 1 ) * ( int(disk_vis_form.height) - 2 ) ) )
                        outputmap[ maploc ] =  -1

                    except Exception as e:
                        print(str(e))
                        print(str(f))
                        
            for c in outputmap:
                index += 1
                
                if( (max(outputmap)) < 10):
                    if int(c) == -1:
                        line += Style.BRIGHT + Fore.MAGENTA + '#' + Style.RESET_ALL
                    elif int(c) == 0:
                        line += " "
                    elif int(c) < int((max(outputmap)) * ( 1 / 6 ) ) :
                        line += chr(249)
                    elif int(c) < int((max(outputmap)) * ( 2 / 6 ) ):
                        line += ( Style.BRIGHT + Fore.BLUE + chr(176) + Style.RESET_ALL)
                    elif int(c) < int((max(outputmap)) * ( 3 / 6 ) ):
                        line += ( Style.BRIGHT + Fore.CYAN + chr(176) + Style.RESET_ALL)
                    elif int(c) < int((max(outputmap)) * ( 4 / 6 ) ):
                        line += ( Style.BRIGHT + Fore.GREEN + chr(177) + Style.RESET_ALL)
                    elif int(c) < int((max(outputmap)) * ( 5 / 6 ) ):
                        line += ( Style.BRIGHT + Fore.YELLOW + chr(178) + Style.RESET_ALL)
                    else:
                        line += ( Style.BRIGHT + Fore.RED + chr(219) + Style.RESET_ALL)
                else:
                    if int(c) == -1:
                        line += Style.BRIGHT + Fore.MAGENTA + '#' + Style.RESET_ALL
                    elif int(c) == 0:
                        line += " "
                    elif int(c) < int((max(outputmap)) * ( 1 / 11 ) ) :
                        line += chr(249)
                    elif int(c) < int((max(outputmap)) * ( 2 / 11 ) ):
                        line += ( Style.DIM + Fore.BLUE + chr(176) + Style.RESET_ALL)
                    elif int(c) < int((max(outputmap)) * ( 3 / 11 ) ):
                        line += ( Style.BRIGHT + Fore.BLUE + chr(176) + Style.RESET_ALL)
                    elif int(c) < int((max(outputmap)) * ( 4 / 11 ) ):
                        line += ( Style.DIM + Fore.CYAN + chr(176) + Style.RESET_ALL)
                    elif int(c) < int((max(outputmap)) * ( 5 / 11 ) ):
                        line += ( Style.BRIGHT + Fore.CYAN + chr(176) + Style.RESET_ALL)
                    elif int(c) < int((max(outputmap)) * ( 6 / 11 ) ):
                        line += ( Style.DIM + Fore.GREEN + chr(177) + Style.RESET_ALL)
                    elif int(c) < int((max(outputmap)) * ( 7 / 11 ) ):
                        line += ( Style.BRIGHT + Fore.GREEN + chr(177) + Style.RESET_ALL)
                    elif int(c) < int((max(outputmap)) * ( 8 / 11 ) ):
                        line += ( Style.DIM + Fore.YELLOW + chr(178) + Style.RESET_ALL)
                    elif int(c) < int((max(outputmap)) * ( 9 / 11 ) ):
                        line += ( Style.BRIGHT + Fore.YELLOW + chr(178) + Style.RESET_ALL)
                    elif int(c) < int((max(outputmap)) * ( 10 / 11 ) ):
                        line += ( Style.DIM + Fore.RED + chr(219) + Style.RESET_ALL)
                    else:
                        line += ( Style.BRIGHT + Fore.RED + chr(219) + Style.RESET_ALL)
                   
                   
                if index % (disk_vis_form.width - 1) == 0:
                    if line.replace(' ','') == "":
                        line = "_"
                    results += str(line) + "\n"
                    line = ""
            
            results += "_\n"
            results += Style.BRIGHT + Fore.WHITE + "Scale" + Style.RESET_ALL
            # results += Style.BRIGHT + Fore.WHITE + str(len((outputmap))) + Style.RESET_ALL
            results += (4*" ") + 6*chr(249)
            results += 6*( Style.DIM + Fore.BLUE + chr(176) + Style.RESET_ALL)
            results += 6*( Style.BRIGHT + Fore.BLUE + chr(176) + Style.RESET_ALL)
            results += 6*( Style.DIM + Fore.CYAN + chr(176) + Style.RESET_ALL)
            results += 6*( Style.BRIGHT + Fore.CYAN + chr(176) + Style.RESET_ALL)
            results += 6*( Style.DIM + Fore.GREEN + chr(177) + Style.RESET_ALL)
            results += 6*( Style.BRIGHT + Fore.GREEN + chr(177) + Style.RESET_ALL)
            results += 6*( Style.DIM + Fore.YELLOW + chr(178) + Style.RESET_ALL)
            results += 6*( Style.BRIGHT + Fore.YELLOW + chr(178) + Style.RESET_ALL)
            results += 6*( Style.DIM + Fore.RED + chr(219) + Style.RESET_ALL)
            results += 6*( Style.BRIGHT + Fore.RED + chr(219) + Style.RESET_ALL)
                    
            disk_vis_form.add_content(results)
            
            return disk_vis_form.render()
        else:
            return 0
        
    def render_speed_histogram(self, start_row):
        cpus = psutil.cpu_percent(percpu=True)
        speed_bar_form = Form('Speed Histogram', y=start_row, x=1, width=(int(self.columns)-( 2*len(cpus) + 7) - 77), height=22)
        speeds = []
        self.conversion_speeds = Media.get_conversion_speeds()
        # if len(self.conversion_speeds) < 500:
            # output = "Processing, please wait...\n"
        # else:
     
        n=25
        speed_chunks = [self.conversion_speeds[i * n:(i + 1) * n] for i in range((len(self.conversion_speeds) + n - 1) // n )]  
        for chunk in speed_chunks:
            speeds.append( max(chunk) )
        
        while len(speeds) < 110:
            speeds.insert(0, 0)
            
        speeds.reverse()
        speeds = speeds[0:105]
        speeds.reverse()
        res_max = max(float(speed) for speed in speeds) 
        
        if res_max < 5:
            res_max = 5

        output = ""
        for r in range(0,20):
            if r == 0:
                output += ("{:>5} " + chr(179)).format( (str(round(res_max,2)) ) )
            elif r == 5:
                output += ("{:>5} " + chr(179)).format( (str(round(3*res_max/4,2)) ) )
            elif r == 10:
                output += ("{:>5} " + chr(179)).format( (str(round(res_max/2,2)) ) )
            elif r == 15:
                output += ("{:>5} " + chr(179)).format( (str(round(res_max/4,2)) ) )
            elif r == 20:
                output += ("{:>5} " + chr(179)).format( "0" )
            else:
                output += ("{:>5} " + chr(179)).format( "_" )
                
            for speed in speeds:
                if r < 5:
                    output += Fore.RED
                elif r < 10:
                    output += Fore.YELLOW
                elif r < 15:
                    output += Fore.GREEN
                else:
                    output += Fore.CYAN
                    
                if int(20*speed/res_max) >= 20 - r:
                    output += chr(254)
                else:
                    output += " "
            
            output += "\n"
        
        xaxis = ""
        for c in range(0, (int(self.columns)-( 2*len(cpus) + 8 ) - 77 ) ):
            if (int(self.columns)-c + 2) % 25 == 0:
                xaxis += chr(193)
            else:
                xaxis += chr(196)
        xaxis += "\n"
    
        output += xaxis
        output += "Samples: " + str( len(self.conversion_speeds))
        
        speed_bar_form.add_content(output)
        return speed_bar_form.render()
    
def main():
    # pylint: disable=C0103
    colorama.init()
    Utils.clear()
    cw = CompressionWatcher()
    steps = 0

    while True:
        cw.rows, cw.columns = os.popen('stty size', 'r').read().split()
        
        disk_usage_row = cw.render_disk_usage(['/Storage/Television/', '/Storage/Movies/'])
        summary_row = cw.render_summary(disk_usage_row)
        proc_row = cw.render_procs(disk_usage_row)
        
        file_data_row = cw.render_file_data(summary_row)
        poster_row = cw.render_poster(disk_usage_row)
        media_row = cw.render_media_info(proc_row)
        conversions_row = cw.render_conversions(media_row)
        histogram_row = cw.render_speed_histogram(conversions_row)
        disk_vis_row = cw.render_disk_visualization(conversions_row)
        
        prog_row = cw.render_progress(histogram_row, steps, clear=False)
        cpu_percent_row = cw.render_cpu_percent(conversions_row)
        
        
        
        steps = 0
        while steps < 60:
            steps += 1
            cw.render_procs(disk_usage_row)
            file_data = cw.render_file_data(summary_row)
            if(file_data == -1):
                steps = 61
            conversions_row = cw.render_conversions(media_row)
            
            histogram_row = cw.render_speed_histogram(conversions_row)
            prog_row = cw.render_progress(histogram_row, steps, clear=False)
            cpu_percent_row = cw.render_cpu_percent(conversions_row)
            
            time.sleep(1)
        
        cw.render_progress(histogram_row, steps, clear=True)
    # pylint: enable=C0103

if __name__ == "__main__":
   try:
      main()
   except KeyboardInterrupt:
      # Utils.clear()
      pass
