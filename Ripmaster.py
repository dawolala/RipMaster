#/usr/bin/python
# Ripmaster
# A python script to string and automate various ripping processes
# By Sean Wallitsch, 2013/09/04

"""

Description
-----------

Ripmaster's main goal is to take an extracted mkv from makeMkv, and take it
through all the intermediate steps needed to produce a high quality result mkv,
including audio tracks that handbrake can't pass through, and bluray subtitles
that handbrake can't convert.

Process
-------

It's assumed the user rips all the audio tracks, subtitles and movies themselves
into an MKV format, probably using MakeMKV. If the user doesn't want to rip
their own movies, there are other projects out there that will JUST do the
automated ripping. However, in my experience this process requires so much hand
holding (having to pick the right track, etc.) that it's better just to do it
manually.

After that, Ripmaster extracts subtitles and supported audio tracks from the MKV
(since Handbrake cannot handle those directly).

Ripmaster uses BDSupToSub to convert the subtitle sup files into a matching IDX
and SUB pair, while also checking for 'forced' subtitles. If it finds forced
subtitles, either in part or through the entire track, it creates an additional
'forced only' subtitle track. If the original track consists only of forced
subtitles, the 'normal' IDX and SUB pair are not created from that track,
leaving only the 'forced' result.

Handbrake then converts the video track, compressing it according to user
specified criteria, and auto-passing through all audio tracks (except audio
tracks (like trueHD), which it cannot handle).

Finally, mkvmerge takes all resulting files (the IDX-SUB subtitles, the
extracted audio (if present) and the converted video), and merges them together,
setting flags on 'forced' tracks correctly, and setting extracted audio as the
default audio track if it's present (since these tracks are usually the highest
quality).

If at any point in the process the computer crashes (normally during the
Handbrake encoding), Ripmaster starts from the last completed task.

Initial Setup
-------------

The following programs are required for Ripmaster to run:

Python (2.6-2.7: http://www.python.org/)
Java (http://java.com/en/download/index.jsp)
MKVToolNix (http://www.bunkus.org/videotools/mkvtoolnix/)
    MKVToolNix contains MKVMerge, MKVInfo and MKVExtract
BDSup2Sub (v5+ by mjuhasz: https://github.com/mjuhasz/BDSup2Sub/wiki)
Handbrake with CLI (I recommend v9.6 at this time http://handbrake.fr/)

While you can rip to an MKV file using whatever you wish, MakeMKV is probably
the best option: http://www.makemkv.com/

User's need to edit Ripmaster.ini and enter the paths to BDSupToSub, Java and
HandBrakeCLI. Users need to convert windows \s into /s for these install
locations.

Users should also set their desired x264 speed, available options are:
ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow
Default: slow

If you desire a fallback audio other than AC3, you should set that here too.
Options for fallback audio are:

faac
ffaac
ffac3
lame
vorbis
ffflac

But note that not all of these support full surround sound.
Default: ffac3

Sample Ripmaster.ini file:

================================================================================

Java = C:/Program Files (x86)/Java/jre7/bin/java
BDSupToSub = C:/Program Files (x86)/MKVToolNix/BDSup2Sub.jar
HandbrakeCLI = C:/Program Files/Handbrake/HandBrakeCLI.exe

x264 Speed = slow
Baseline Quality
    1080p = 20
    720p = 20
    480p = 20
High Quality
    1080p = 19
    720p = 19
    480p = 19
Ultra Quality
    1080p = 16
    720p = 16
    480p = 16

Language = English
Audio Fallback = ffac3

================================================================================

Leading and trailing whitespaces are automatically removed, but all entries
are case sensitive. Make sure there's still a space between the argument
and the '=' sign.

Users need to Rip their own movies from disk, preferably using MakeMKV, then
they need to decide on how they want each movie processed, this is done by
changing the folder name that contains a single or multiple mkv files.

Encoding Instructions
---------------------

A sample folder name might be:

Akira__1080_hq_animation

Anything before the double underscore ('__') is considered the title of the
movie. Anything after is part of the instruction set.

RESOLUTION:

You at least need a resolution, accepted arguments for this are:

1080, 720, 480

If you don't provide a target resolution, it defaults to 1080 (although in the
future it will try and pass through the incoming resolution).

QUALITY:

Optionally, you can provide a quality preset:

uq, hq, bq

This preset will be cross referenced with the resolution to get the 'rf' quality
setting Handbrake will use for the video encode.

If you don't provide a quality, it defaults to 'bq' for the resolution.

X264 TUNING:

Selects the x264 tuning preset to be used. Options are:

film animation grain stillimage psnr ssim fastdecode zerolatency

But it's recommended to only stick to 'film', 'animation', or 'grain'.

SET FPS:

Some material needs to be 'forced' to a certain fps, especially DVD material:

30p, 25p, 24p

DE-INTERLACING:

If your file needs to be de-interlaced, give the instruction set:

tv

And it will do a high quality de-interlacing pass.

How To:
-------

Save your mkv to a folder with the title of the movie and the encoding
instructions (see above). Place that folder in ripmaster's 'toConvert' folder,
which is where Ripmaster will search for movies to encode.

Double click on Ripmaster.py to begin the process.

If you want Ripmaster to automatically start up after a crash, place a shortcut
to Ripmaster.py in your startup folder, but be warned that EVERY time you start
your computer, Ripmaster will start with it. Just close the window if you don't
want Ripmaster doing things right now, the crash protection will pickup where
you left off.

Starting Fresh:
---------------

If you mess something up, or you want to start an entire encode batch over again
(say you changed the ini settings), simply delete the following from the folder:

movies.p
movies.p.bak

Once those are deleted, every movie ripmaster finds will be treated as a new
movie to be converted.

"""

#===============================================================================
# IMPORTS
#===============================================================================

# Standard Imports
import os
import pickle
from shutil import copyfile

# Ripmaster Imports
from tools import Config, Movie

#===============================================================================
# FUNCTIONS
#===============================================================================

# Utility

def get_movies(dir):
    """Gets the movies from the specified directory"""
    movieList = []

    directories = os.listdir(dir)
    for d in directories:
        # We need to remove directories without instruction sets
        if '__' not in d:
            directories.remove(d)
            continue
        files = os.listdir("{root}/{subdir}".format(root=dir, subdir=d))
        for f in files:
            # Don't add .mkv's that are handbrake encodes.
            if '--converted' not in f and '.mkv' in f:
                movie = Movie(dir, d, f)
                movieList.append(movie)

    return movieList

#===============================================================================
# MAIN
#===============================================================================	

def main():
    """Main app process. This controls every step of the process"""
    # TODO: Allow users to supply alt configs?
    config = Config('./Ripmaster.ini')
    config.debug()

    root = os.getcwd() + '/toConvert/'

    # See if we have a backup copy. Our backup copy is more likely to be
    # complete than the master. See issue #23 on github
    # http://github.com/shidarin/RipMaster/issues/23
    try:
        copyfile("./movies.p.bak", "./movies.p")
    except IOError:
        pass

    # TODO: We should really try the main file first before copying over the
    # backup.

    try:
        with open("./movies.p", "rb") as f:
            movies = pickle.load(f)
    except (IOError, EOFError):
        print "No existing movie in process found. Starting from scratch"
        movies = []

    print ""
    print "Found the following movies in progress:"
    for entry in movies:
        print entry.path
    print ""

    newMovies = get_movies(root)

    for movie in movies:
        for raw in newMovies:
            # If a movie that get_movies() found already matches a movie in our
            # pickled list, we should remove it, otherwise we'll add it twice.
            if movie.path == raw.path:
                newMovies.remove(raw)

    print ""

    # Now that we've removed duplicates, we'll extend the main list of movie
    # objects by the new movies found.
    movies.extend(newMovies)

    print "Total movie list after adding new movies:"
    for entry in movies:
        print entry.path

    with open("./movies.p", "wb") as f:
        pickle.dump(movies, f)
    # Create a copy immediately after a successful dump
    copyfile("./movies.p", "./movies.p.bak")

    for movie in movies:
        if not movie.extracted:
            movie.extractTracks()
            with open("./movies.p", "wb") as f:
                pickle.dump(movies, f)
        copyfile("./movies.p", "./movies.p.bak")
    for movie in movies:
        if not movie.converted:
            movie.convertTracks()
            with open("./movies.p", "wb") as f:
                pickle.dump(movies, f)
        copyfile("./movies.p", "./movies.p.bak")
    for movie in movies:
        if not movie.encoded:
            movie.encodeMovie()
            with open("./movies.p", "wb") as f:
                pickle.dump(movies, f)
        copyfile("./movies.p", "./movies.p.bak")
    for movie in movies:
        if not movie.merged:
            # TODO: Add mkvMerge
            pass

    print ""
    print "The following movies have been completed:"
    for movie in movies:
        print movie.path
    print ""

if __name__ == "__main__":
    main()

# Keep the shell up to show results
raw_input('Press enter to close')