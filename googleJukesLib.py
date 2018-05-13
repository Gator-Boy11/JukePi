#!/usr/bin/python3

#Author: David Johnston
#Description: Library of support functions for google Jukes

import gmusicapi, os, urllib.request, configparser, json
from multiprocessing.pool import ThreadPool

directory = os.getcwd()

songs, playlists, google = None, None, None

#Characters will be replaced in this order. & MUST be first
specialCharMap = [
    ("&",38),
    ("[",91),
    ("]",93),
    ("=",61),
    ]

def escapeName(name):
    global specialCharMap
    for char in specialCharMap:
        name = name.replace(char[0], "&#" + str(char[1]) + ";")
    return name

def unescapeName(name):
    global specialCharMap
    for char in reversed(specialCharMap):
        name = name.replace("&#" + str(char[1]) + ";", char[0])
    return name

def debracket(text, brackets="()[]{}"):
    '''from jfs at https://stackoverflow.com/questions/14596884/remove-text-between-and-in-python'''
    count = [0] * (len(brackets) // 2) # count open/close brackets
    saved_chars = []
    for character in text:
        for i, b in enumerate(brackets):
            if character == b: # found bracket
                kind, is_close = divmod(i, 2)
                count[kind] += (-1)**is_close # `+1`: open, `-1`: close
                if count[kind] < 0: # unbalanced bracket
                    count[kind] = 0  # keep it
                else:  # found bracket to remove
                    break
        else: # character is not a [balanced] bracket
            if not any(count): # outside brackets
                saved_chars.append(character)
    return ''.join(saved_chars).strip()
    
def connect(username, password, verbose=True):
    source = gmusicapi.Mobileclient()
    #print(help(source))
    try:
        source.login(username, password, source.FROM_MAC_ADDRESS, "en_US")
        if not source.is_authenticated():
            print("MAC adress was not authenticated")
            raise Exception
        if verbose:
            print("MAC address worked")
        return source
    except Exception as e:
        #Sometimes gmusicapi is weird, and because I don't want to have to modify it, I can manually control certain aspects because python has no proper encapsulation.
        #Basically, I'm "stealing" a device id from gmusicapi.
        import uuid
        #raise e
        if source.session.login(username, password, gmusicapi.utils.utils.create_mac_string(uuid.getnode()).replace(":","")):
            devices = source.get_registered_devices()
            print(devices)
            source.logout()
            for option in devices:
                if option["type"] == "ANDROID":
                    print(option["type"])
                    if source.login(username, password, option['id'][2:] if option['id'].startswith('0x') else option['id'].replace(':', '')):
                        if verbose:
                            print(option["id"])
                        return source
            for option in devices:
                if source.login(username, password, option['id'][2:] if option['id'].startswith('0x') else option['id'].replace(':', '')):
                    if verbose:
                        print(option["id"])
                    break
            return source
        else:
            print("FAILED LOGIN")
            from gmusicapi.utils import utils
            print(utils.log_filepath)

def download(location):
    try:
        if not os.path.isfile(location[1]):
            urllib.request.urlretrieve(google.get_stream_url(location[0]["id"]),location[1])
        if (not os.path.isfile(location[2])) and location[0].get("albumArtRef", None) != None:
            urllib.request.urlretrieve(location[0]["albumArtRef"][0]["url"],location[2])
        return location[1], None
    except Exception as e:
        return location[0], e

def getSongFromTrack(track):
    global songs
    return [item for item in songs if item["id"] == track["trackId"]][0]

def checkForUpdates():
    global songs, playlists, google
    google = connect(input("Username: "), input("Password: "))

    playlists = google.get_all_user_playlist_contents()
    songs = google.get_all_songs()

    if not os.path.exists(directory + os.sep + "songs"):
        os.makedirs(directory + os.sep + "songs")
    if not os.path.exists(directory + os.sep + "albumArt"):
        os.makedirs(directory + os.sep + "albumArt")

    tracks = []
    trackDestinations = []
    imageDestinations = []
    for track in songs:
        tracks.append(track)
        trackDestinations.append(directory + os.sep + "songs" + os.sep + track["id"] + ".mp3")
        imageDestinations.append(directory + os.sep + "albumArt" + os.sep + track["id"] + ".jpg")
    results = ThreadPool(16).imap_unordered(download, [[tracks[i], trackDestinations[i], imageDestinations[i]] for i in range(len(songs))])
    errors = False
    for file, error in results:
        if error is None:
            print("%r fetched successfully" % (file))
        else:
            print("error fetching %r: %s" % (file, error))
            errors = True
    '''while errors:
        results = ThreadPool(16).imap_unordered(download, [[tracks[i], destinations[i]] for i in range(len(songs))])
        errors = False
        for file, error in results:
            if error is None:
                print("%r fetched successfully" % (file))
            else:
                print("error fetching %r: %s" % (file, error))
                errors = True'''

    index = configparser.ConfigParser()
    indexLocation = directory + os.sep + "config.ini"
    index.read(indexLocation)

    playlistIds = []

    for playlist in range(len(playlists)):
        index[playlists[playlist]["id"]] = playlists[playlist]
        playlistIds.append(playlists[playlist]["id"])
        order = []
        for track in playlists[playlist]["tracks"]:
            order.append(getSongFromTrack(track)["id"])
        index[playlists[playlist]["id"]]["tracks"] = escapeName(json.dumps(order))
    
    order = []
    for song in songs:
        index[song["id"]] = song
        index[song["id"]]["title"] = escapeName(song["title"])
        index[song["id"]]["album"] = escapeName(song["album"])
        order.append(song["id"])
        try:
            index[song["id"]]["albumArtRef"] = escapeName(json.dumps(song["albumArtRef"]))
        except Exception as e:
            pass
        try:
            index[song["id"]]["artistId"] = escapeName(json.dumps(song["artistId"]))
        except Exception as e:
            pass
    index["library"] = {
        "tracks": escapeName(json.dumps(order)),
        "playlists": escapeName(json.dumps(playlistIds)),
    }
    with open(indexLocation, "w", encoding = "utf-8") as indexFile:
        index.write(indexFile)
        indexFile.close()

    google.logout()

    
if __name__ == "__main__":
    checkForUpdates()
