#!/usr/bin/python3

#Author: David Johnston
#Description: Command-Line google music player.

#Imports standard library things
import configparser, os, json, threading, time, random, sys

#Imports Custom Code
import TerminalVelocity, googleJukesLib

#Make sure libav is in the path variable before pydub is imported
#This is the converter library
os.environ["PATH"] = os.environ["PATH"] + ";" + os.getcwd() + os.sep + "libav" + os.sep + "win64" + os.sep + "usr" + os.sep + "bin"

#Import non-standard libraries that must be installed
#Each is checked individually so that information on how to install them can be given to the user
importErrors = False
try:
    #Used for playing audio
    import pyaudio
except:
    print("pyaudio is not installed. Install it with 'pip install pyaudio'")
    importErrors = True
try:
    #Used for converting audio from mp3 to a pseudo wav
    import pydub
except:
    print("pydub is not installed. Install it with 'pip install pydub'")
    importErrors = True
if importErrors:
    print("Required Libraries not installed. Please install them and try again.")
    print("Press any key to exit")
    from msvcrt import getch
    junk = getch()
    exit()

#Initialize standard python things
playlist = []
playlistIterator = -1
loopVar = 0
playspeed = 1.0
volume = 0.0
frameCounter = 0.0
active = True
playing = False
paused = False
shuffleVar = False

#Initialize library things
playlistParser = configparser.ConfigParser()
skipper = threading.Event()
audioOut = pyaudio.PyAudio()

#check for config file
if not os.path.isfile(os.getcwd() + os.sep + "config.ini"):
    #If it doesn't exist create it
    with open(os.getcwd() + os.sep + "config.ini", "w") as config:
        #Write the basic config
        config.write('[software]\nvolume = 0.0\nspeed = 1.0\ngithub = Gator-Boy11/JukePi')
        #close the file
        config.close

#Set initial audio and play speed values
playlistParser.read(os.getcwd() + os.sep + "config.ini")
volume = playlistParser.getfloat("software", "volume")
playspeed = playlistParser.getfloat("software", "speed")

#Initialize waveforms as None so that we can know if the program just started
wf = None
rawWf = None

def saveConfig():
    global playlistParser
    with open(os.getcwd() + os.sep + "config.ini", "w", encoding = "utf-8") as configFile:
        playlistParser.write(configFile)
        configFile.close()

def callback(in_data, frame_count, time_info, status):
    """Internal callback for actually handling the playing of audio"""
    #Get global variables
    global paused, frameCounter, playspeed
    #Figure out how many bytes are required
    frame_count = frame_count * wf.frame_width
    #Just give '0's when paused or speed is 0
    if playspeed == 0 or paused:
        data = b"\x00" * frame_count
    #Give data in a special reversed order for negative playback speeds
    elif playspeed < 0:
        rawdata = wf.raw_data[int(frameCounter*frame_count): int(frameCounter*frame_count+frame_count)]
        data = b""
        for i in range(0,len(rawdata),wf.frame_width):
            data = rawdata[i:i+wf.frame_width] + data
    #Otherwise just give data normally
    else:
        data = wf.raw_data[int(frameCounter)*frame_count: int(frameCounter)*frame_count+frame_count]
    #Increment the internal counter unless the program is paused
    if not paused:
        frameCounter += playspeed
    #Return the data
    return (data, pyaudio.paContinue)

def playerHandler():
    """Internal player for handling starting/stopping audio"""
    #Get global variables
    global playlist, playlistIterator, active, rawWf, wf, playing, shuffleVar, loopVar, frameCounter, time, audioOut
    #Keep looping until the program stops
    while active:
        #If the player has actually been told to play
        if playing:
            #Load Music
            rawWf = pydub.AudioSegment.from_file(os.getcwd() + "/songs/" + playlist[playlistIterator] + ".mp3")
            #Apply volume
            wf = rawWf.apply_gain(volume)
            #Reset the frame counter and account for negative speeds
            if playspeed < 0:
                frameCounter = wf.frame_count()/1024-(wf.frame_width-(wf.frame_count()%1024)/256)
            else:
                frameCounter = 0
            #Open the audio stream
            stream = audioOut.open(format=audioOut.get_format_from_width(wf.sample_width),
                channels=wf.channels,
                rate=wf.frame_rate,
                output=True,
                stream_callback=callback)
            stream.start_stream()
            #Wait while the music is still playing
            #The skipper controls this somewhat so other commands that temporarily stop the music actually take affect
            skipper.set()
            while playing and stream.is_active():
                skipper.clear()
                time.sleep(0.01)
                skipper.set()
            #Increment the iterator assuming it's not set to loop single
            if playing and loopVar != 1:
                playlistIterator += 1
            #Close the old stream
            stream.stop_stream()
            stream.close()
            #Stop playing, shuffle, or loop the music if the end was reached
            if playlistIterator >= len(playlist):
                playlistIterator = 0
                if loopVar == 2:
                    if shuffleVar:
                        random.shuffle(playlist)
                else:
                    time.sleep(0.2)
                    playing = False
        else:
            #have the CPU wait when not playing so it doesn't overheat
            time.sleep(0.1)
    #Stop pyaudio
    audioOut.terminate()

def updateHandler():
    """Automatic update Handler"""
    global active
    time.sleep(1)
    while active:
        print("Automatic update started.\n")
        googleJukesLib.checkForUpdates(True)
        print("Automatic update complete.\n")
        counter = 1 * 60 * 10
        while active and counter > 0:
            time.sleep(0.1)
            counter -= 1

def logout(source, *args):
    """
Usage: {0}
        Logs out the user
        """
    #Get global variables
    global active, playerThread, updateThread
    #Tells play thread to stop
    active = False
    #Tells audio to stop
    stop(source)
    #Waits for player thread to rejoin
    playerThread.join()
    #Waits for update thread to rejoin
    updateThread.join()
    #Closes the program
    exit()

def play(source, *args):
    """
Usage: {0} song [SONGNAME]
        Plays the specified song

Usage: {0} playlist [PLAYLIST]
        Plays the specified playlist

Usage: {0} library
        Plays the entire song library
        """
    #Get global variables
    global playlist, playlistIterator, playlistParser, playing, shuffleVar, paused, frameCounter
    #Convert the arguments to a list for editing
    args = list(args)
    #If there is something else there
    if len(args) != 0:
        #If the user stated it is a playlist
        if args[0].lower() == "playlist":
            #Remove the first item to make processing easier
            del args[0]
            #Read the library file
            playlistParser.read(os.getcwd() + os.sep + "config.ini")
            #Create a playlist to check for songs without messing with the songs already playing
            preplaylist = []
            #Scan for songs exactly matching a certain name
            for song in json.loads(googleJukesLib.unescapeName(playlistParser["library"]["playlists"])):
                #Check if the song has the exact same name
                if googleJukesLib.unescapeName(playlistParser[song]["name"]) == " ".join(args):
                    #Add the song to the pre playlist
                    preplaylist.append(song)
            #If there wasn't exactly one song found look for any with names that have parenthesis or have different capitalization
            if len(preplaylist) != 1:
                #Scan for songs with names that have parenthesis or have different capitalization
                for song in json.loads(googleJukesLib.unescapeName(playlistParser["library"]["playlists"])):
                    #Check if the song has the exact same name but isn't already on the playlist
                    if googleJukesLib.debracket(googleJukesLib.unescapeName(playlistParser[song]["name"]).lower()) == " ".join(args).lower() and not song in preplaylist:
                        #Add the song to the pre playlist
                        preplaylist.append(song)
            #If there were more than one songs found
            if len(preplaylist) > 1:
                #Print out each song name with a number and the artist
                for song in range(0,len(preplaylist)):
                    #Print out one line showing the song, artist name and a number
                    source.put(str(song+1) + ".  " + playlistParser[preplaylist[song]]["name"] + " " * (len(max(preplaylist, key = len))-len(playlistParser[preplaylist[song]]["name"])+8) + playlistParser[preplaylist[song]]["artist"])
                #Print out an extra cancel option
                source.put(str(len(preplaylist)+1) + ". Cancel")
                #Ask the user to pick a song
                pick = source.get("Pick a song: ")
                #Check if the pick is a integer
                validPick = pick.isdigit()
                #If it is
                if validPick:
                    #Set the picked song to the number it is on the list
                    pick = int(pick) - 1
                    #Verify the number isn't too large or too small
                    validPick = pick <= len(preplaylist) and pick >= 0
                #Keep asking the user for a different number until they give one that is viable
                while not validPick:
                    #Ask the user to pick another song
                    pick = source.get("Pick a song: ")
                    #Check if the pick is a integer
                    validPick = pick.isdigit()
                    #If it is
                    if validPick:
                        #Set the picked song to the number it is on the list
                        pick = int(pick) - 1
                        #Verify the number isn't too large or too small
                        validPick = pick <= len(preplaylist)
                #If the user didn't select cancel
                if pick != len(preplaylist):
                    #set the value to the user's selection
                    preplaylist = [preplaylist[pick]]
                #OtherWise
                else:
                    #Don't change the song
                    preplaylist = None
            #Stop the Music
            playing = False
            #Wait for the player to confirm it is finished
            skipper.wait(1)
            #If the user actually selected a song
            if preplaylist != None:
                #Set the playlist to that song
                playlist = [z for y in [json.loads(googleJukesLib.unescapeName(playlistParser[x]["tracks"])) for x in preplaylist]  for z in y]
            #Reset the playlist counter
            playlistIterator = 0
            #Verify there is a playlist
            if len(playlist) > 0:
                #If shuffling has been enabled
                if shuffleVar:
                    #Shuffle the playlist
                    random.shuffle(playlist)
                #Tell the player to start
                playing = True
                #Make sure the music isn't paused
                paused = False
            else:
                #Otherwise just inform the user of their mistake
                source.err("Song could not be found.")
        elif args[0].lower() == "library":
            #Remove the first item to make processing easier
            del args[0]
            #Read the library file
            playlistParser.read(os.getcwd() + os.sep + "config.ini")
            #Stop the music
            playing = False
            #Wait for the player to confirm it is finished
            skipper.wait(1)
            #Read the list of tracks
            playlist = json.loads(googleJukesLib.unescapeName(playlistParser["library"]["tracks"]))
            #If shuffle is on shuffle the music
            if shuffleVar:
                random.shuffle(playlist)
            #Reset the playlist counter
            playlistIterator = 0
            #Verify there is a playlist
            if len(playlist) > 0:
                #If shuffling has been enabled
                if shuffleVar:
                    #Shuffle the playlist
                    random.shuffle(playlist)
                #Tell the player to start
                playing = True
                #Make sure the music isn't paused
                paused = False
            else:
                #Otherwise just inform the user of their mistake
                source.err("Library seems to be empty!")
        elif args[0].lower() == "song-id" or args[0].lower() == "songid":
            #Remove the first item to make processing easier
            del args[0]
            #Read the library file
            playlistParser.read(os.getcwd() + os.sep + "config.ini")
            #Stop the music
            playing = False
            #Wait for the player to confirm it is finished
            skipper.wait(1)
            #Read the list of tracks
            playlist = json.loads(googleJukesLib.unescapeName(playlistParser["library"]["tracks"]))
            #Verify song exists
            if "-".join(args) in playlist:
                #If it does make it the only thing in the list
                playlist = ["-".join(args)]
            #Otherwise
            else:
                #Clear the playlist
                playlist = []
            #If shuffle is on shuffle the music
            if shuffleVar:
                random.shuffle(playlist)
            #Reset the playlist counter
            playlistIterator = 0
            #Verify there is a playlist
            if len(playlist) > 0:
                #Tell the player to start
                playing = True
                #Make sure the music isn't paused
                paused = False
            else:
                #Otherwise just inform the user of their mistake
                source.err("Song does not Exist!")
        elif args[0].lower() == "playlist-id" or args[0].lower() == "playlistid":
            #Remove the first item to make processing easier
            del args[0]
            #Read the library file
            playlistParser.read(os.getcwd() + os.sep + "config.ini")
            #Stop the music
            playing = False
            #Wait for the player to confirm it is finished
            skipper.wait(1)
            #Read the list of playlists
            preplaylist = json.loads(googleJukesLib.unescapeName(playlistParser["library"]["playlists"]))
            #Verify playlist exists
            if "-".join(args) in preplaylist:
                #If it does make it the only thing in the list
                preplaylist = ["-".join(args)]
                playlist = [z for y in [json.loads(googleJukesLib.unescapeName(playlistParser[x]["tracks"])) for x in preplaylist]  for z in y]
            #Otherwise
            else:
                #Clear the playlist
                playlist = []
            #If shuffle is on shuffle the music
            if shuffleVar:
                random.shuffle(playlist)
            #Reset the playlist counter
            playlistIterator = 0
            #Verify there is a playlist
            if len(playlist) > 0:
                #If shuffling has been enabled
                if shuffleVar:
                    #Shuffle the playlist
                    random.shuffle(playlist)
                #Tell the player to start
                playing = True
                #Make sure the music isn't paused
                paused = False
            else:
                #Otherwise just inform the user of their mistake
                source.err("Playlist does not Exist!")
        #05caf410-211c-49e4-a81f-a6f942dfcd08
        elif args[0].lower() == "song":
            #Remove the first item to make processing easier
            del args[0]
            #Read the library file
            playlistParser.read(os.getcwd() + os.sep + "config.ini")
            #Create a playlist to check for songs without messing with the songs already playing
            preplaylist = []
            #Scan for songs exactly matching a certain name
            for song in json.loads(googleJukesLib.unescapeName(playlistParser["library"]["tracks"])):
                #Check if the song has the exact same name
                if googleJukesLib.unescapeName(playlistParser[song]["title"]) == " ".join(args):
                    #Add the song to the pre playlist
                    preplaylist.append(song)
            #If there wasn't exactly one song found look for any with names that have parenthesis or have different capitalization
            if len(preplaylist) != 1:
                #Scan for songs with names that have parenthesis or have different capitalization
                for song in json.loads(googleJukesLib.unescapeName(playlistParser["library"]["tracks"])):
                    #Check if the song has the exact same name but isn't already on the playlist
                    if googleJukesLib.debracket(googleJukesLib.unescapeName(playlistParser[song]["title"]).lower()) == " ".join(args).lower() and not song in preplaylist:
                        #Add the song to the pre playlist
                        preplaylist.append(song)
            #If there were more than one songs found
            if len(preplaylist) > 1:
                #Print out each song name with a number and the artist
                for song in range(0,len(preplaylist)):
                    #Print out one line showing the song, artist name and a number
                    source.put(str(song+1) + ".  " + playlistParser[preplaylist[song]]["title"] + " " * (len(max(preplaylist, key = len))-len(playlistParser[preplaylist[song]]["title"])+8) + playlistParser[preplaylist[song]]["artist"])
                #Print out an extra cancel option
                source.put(str(len(preplaylist)+1) + ". Cancel")
                #Ask the user to pick a song
                pick = source.get("Pick a song: ")
                #Check if the pick is a integer
                validPick = pick.isdigit()
                #If it is
                if validPick:
                    #Set the picked song to the number it is on the list
                    pick = int(pick) - 1
                    #Verify the number isn't too large or too small
                    validPick = pick <= len(preplaylist) and pick >= 0
                #Keep asking the user for a different number until they give one that is viable
                while not validPick:
                    #Ask the user to pick another song
                    pick = source.get("Pick a song: ")
                    #Check if the pick is a integer
                    validPick = pick.isdigit()
                    #If it is
                    if validPick:
                        #Set the picked song to the number it is on the list
                        pick = int(pick) - 1
                        #Verify the number isn't too large or too small
                        validPick = pick <= len(preplaylist)
                #If the user didn't select cancel
                if pick != len(preplaylist):
                    #set the value to the user's selection
                    preplaylist = [preplaylist[pick]]
                #OtherWise
                else:
                    #Don't change the song
                    preplaylist = None
            #Stop the Music
            playing = False
            #Wait for the player to confirm it is finished
            skipper.wait(1)
            #If the user actually selected a song
            if preplaylist != None:
                #Set the playlist to that song
                playlist = [x for x in preplaylist]
            #Reset the playlist counter
            playlistIterator = 0
            #Verify there is a playlist
            if len(playlist) > 0:
                #If shuffling has been enabled
                if shuffleVar:
                    #Shuffle the playlist
                    random.shuffle(playlist)
                #Tell the player to start
                playing = True
                #Make sure the music isn't paused
                paused = False
            else:
                #Otherwise just inform the user of their mistake
                source.err("Song could not be found.")
        else:
            #Otherwise just inform the user of their mistake
            source.err((args[0] + " is not a valid parameter."))
    #Otherwise just play or unpause the last stopped song or playlist
    else:
        #Verify there is a playlist
        if len(playlist) > 0:
            #Tell the player to start
            playing = True
            #Make sure the music isn't paused
            paused = False
        else:
            #Otherwise just inform the user of their mistake
            source.err("Playlist is empty!")

def listItems(source, *args):
    """
Usage: {0} playlist(s)
        Lists all the playlists

Usage: {0} songs
        Lists all the songs

Usage: {0} playlist [PLAYLIST]
        Lists all the songs in a playlist
        """
    #Get global variables
    global playlist
    #Convert the arguments to a list for editing
    args = list(args)
    #If there is something else there
    if len(args) != 0:
        #If the user asked for playlists
        if args[0].lower() == "playlists":
            #Read the library file
            playlistParser.read(os.getcwd() + os.sep + "config.ini")
            #Get a list of every playlist
            for item in json.loads(googleJukesLib.unescapeName(playlistParser["library"]["playlists"])):
                #Print out each playlist name
                source.put(googleJukesLib.unescapeName(playlistParser[item]["name"]))
        #Otherwise if the user asked for songs
        elif args[0].lower() == "songs" or args[0].lower() == "library":
            #Read the library file
            playlistParser.read(os.getcwd() + os.sep + "config.ini")
            #Get a list of every song
            for item in json.loads(googleJukesLib.unescapeName(playlistParser["library"]["tracks"])):
                #Print out each song name
                source.put(googleJukesLib.unescapeName(playlistParser[item]["title"]))
        #Otherwise if the user asked for songs in a playlist or playlists
        elif args[0].lower() == "playlist":
            #If they only asked for 'playlist'
            #Read the library file
            playlistParser.read(os.getcwd() + os.sep + "config.ini")
            if len(args) == 1:
                #Get a list of every playlist
                for item in json.loads(googleJukesLib.unescapeName(playlistParser["library"]["playlists"])):
                    #Print out each playlist name
                    source.put(googleJukesLib.unescapeName(playlistParser[item]["name"]))
            else:
                #Remove the first item to make processing easier
                del args[0]
                #Get a list of every song in the playlist
                for item in json.loads(googleJukesLib.unescapeName(playlistParser["library"]["playlists"])):
                    if googleJukesLib.unescapeName(playlistParser[item]["name"]).lower() == " ".join(args).lower():
                        for song in json.loads(googleJukesLib.unescapeName(playlistParser[item]["tracks"])):
                            #Print out each song name
                            source.put(googleJukesLib.unescapeName(playlistParser[song]["title"]))                           

def shuffle(source, *args):
    """
Usage: {0}
        Show whether shuffle is on or not

Usage: {0} on
        Turns on shuffle (and shuffles right now)

Usage: {0} off
        Turns off shuffle

Usage: {0} now
        Shuffles playlist once (disables Shuffling)
        """
    #Get global variables
    global shuffleVar, playing, playlistIterator, skipper
    #If there is something else there
    if len(args) != 0:
        if args[0].lower() == "on":
            #Save the player state for later
            wasPlaying = playing
            #Stop the music
            playing = False
            #Wait for the player to confirm it is finished
            skipper.wait(1)
            #Shuffle music now
            random.shuffle(playlist)
            #Reset the iterator
            playlistIterator = 0
            #Enable auto reshuffling
            shuffleVar = True
            #If the music was playing earlier
            if wasPlaying:
                #Start the Music
                playing = True
        elif args[0].lower() == "off":
            #Disable auto reshuffling
            shuffleVar = False
        elif args[0].lower() == "now":
            #Save the player state for later
            wasPlaying = playing
            #Stop the music
            playing = False
            #Wait for the player to confirm it is finished
            skipper.wait(1)
            #Shuffle music now
            random.shuffle(playlist)
            #Reset the iterator
            playlistIterator = 0
            #Disable auto reshuffling
            shuffleVar = False
            #If the music was playing earlier
            if wasPlaying:
                #Start the Music
                playing = True
        else:
            #Otherwise just inform the user of their mistake
            source.err(args[0] + " is not a valid parameter.")
    #State the shuffle state to the user
    return shuffleVar

def loop(source, *args):
    """
Usage: {0}
        Show whether loop is on or not

Usage: {0} on
        Turns on looping

Usage: {0} all
        Turns on looping

Usage: {0} single
        Turns on looping for one song

Usage: {0} off
        Turns off looping
        """
    #Get global variables
    global loopVar
    if len(args) != 0:
        if args[0].lower() == "on" or args[0].lower() == "all":
            #set it to 2 to loop all
            loopVar = 2
        elif args[0].lower() == "off":
            #Set it to 0 for off
            loopVar = 0
        elif args[0].lower() == "single":
            #Set it to one to loop one track
            loopVar = 1
        else:
            #Otherwise just inform the user of their mistake
            source.err(args[0] + " is not a valid parameter.")
    #State the loop state to the user
    return ["Off", "Single", "On"][loopVar]
        
        

def stop(source, *args):
    """
Usage: {0}
        Stops playing music
        """
    #Get global variables
    global playing
    #Set the playing
    playing = False

def skip(source, *args):
    """
Usage: {0}
        Skips playing music
        """
    #Get global variables
    global playing, playlistIterator, skipper
    #If the music is actually playing
    if playing:
        #Stop the music
        playing = False
        #Wait for the player to confirm it is finished
        skipper.wait(1)
        #Increment the music counter
        playlistIterator += 1
        #Start the Music
        playing = True

def pause(source, *args):
    """
Usage: {0}
        Pauses playing music
        """
    #Get global variables
    global paused
    #Set the paused flag
    paused = True

def unpause(source, *args):
    """
Usage: {0}
        Unpauses playing music
        """
    #Get global variables
    global paused
    #Set the paused flag
    paused = False

def setSpeed(source, *args):
    """
Usage: {0}
        Returns the music playspeed

Usage: {0} [SPEED]
        Sets the music playspeed
        """
    #Get global variables
    global playspeed, playlistParser
    playlistParser.read(os.getcwd() + os.sep + "config.ini")
    playspeed = playlistParser.getfloat("software", "speed")
    #If there is something else there
    if len(args) != 0:
        try:
            #Try and set the speed to a number
            playspeed = float(args[0])
            playlistParser["software"]["speed"] = str(playspeed)
            saveConfig()
        except:
            #Otherwise just inform the user of their mistake
            source.err(args[0] + " is not a valid number.")
    #State the speed to the user
    return playspeed

def setVolume(source, *args):
    """
Usage: {0}
        Returns the music volume

Usage: {0} [SPEED]
        Sets the music volume
        """
    #Get global variables
    global wf, rawWf, volume, playlistParser
    playlistParser.read(os.getcwd() + os.sep + "config.ini")
    volume = playlistParser.getfloat("software", "volume")
    #If there is something else there
    if len(args) != 0:
        try:
            #Try and set the volume to a number
            volume = float(args[0])
            playlistParser["software"]["volume"] = str(volume)
            saveConfig()
        except:
            #Otherwise just inform the user of their mistake
            source.err(args[0] + " is not a valid number.")
        if wf != None and rawWf != None:
            #set the volume assuming the waveforms have been created
            wf = rawWf.apply_gain(volume)
    #State the volume to the user
    return volume

def update(source, *args):
    """
Usage: {0}
        Updates copies of saved songs.
        """
    googleJukesLib.checkForUpdates(True)

def changeUser(source, *args):
    """
Usage: {0}
        Changes current user.
        """
    with open(os.getcwd() + os.sep + "config.ini", "w") as userFile:
        #Write the basic config
        userFile.write(source.get("Username: ") + "\n" + source.get("Password: "))
        #close the file
        userFile.close

def login():
    #check for user info file
    if not os.path.isfile(os.getcwd() + os.sep + "user.txt"):
        #If it doesn't exist create it
        with open(os.getcwd() + os.sep + "user.txt", "w") as userFile:
            #Write the basic config
            userFile.write(input("Username: ") + "\n" + input("Password: "))
            #close the file
            userFile.close
    with open(os.getcwd() + os.sep + "user.txt") as userFile:
            #Write the basic config
            userInfo = userFile.readlines()
            #close the file
            userFile.close
    googleJukesLib.user = (userInfo[0], userInfo[1])

googleJukesLib.login = login

#Add commands to dictionary for velocity
jukeCommands = {
    #Name    Function
    "help":         TerminalVelocity.tvl.helper,
    "logout":       logout,
    "exit":         logout,
    "quit":         logout,
    "play":         play,
    "list":         listItems,
    "shuffle":      shuffle,
    "loop":         loop,
    "stop":         stop,
    "skip":         skip,
    "pause":        pause,
    "unpause":      unpause,
    "echoColumns":  TerminalVelocity.tvl.echoColumns,
    "speed":        setSpeed,
    "setSpeed":     setSpeed,
    "volume":       setVolume,
    "setVolume":    setVolume,
    "update":       update,
    "login":        changeUser,
}

#create player thread
playerThread = threading.Thread(target = playerHandler)
#create update thread
updateThread = threading.Thread(target = updateHandler)

if __name__ == "__main__":
    #Start the player thread
    playerThread.start()
    #Start the update thread
    updateThread.start()
    #Start velocity
    v = TerminalVelocity.Velocity(jukeCommands)
    v.start()
    #Print a dividing line
    v.put("-"*120)
    #Print the ASCII art
    v.put('''
   _____                           _               _           _                 
  / ____|                         | |             | |         | |                
 | |  __    ___     ___     __ _  | |   ___       | |  _   _  | | __   ___   ___ 
 | | |_ |  / _ \\   / _ \\   / _` | | |  / _ \\  _   | | | | | | | |/ /  / _ \\ / __|
 | |__| | | (_) | | (_) | | (_| | | | |  __/ | |__| | | |_| | |   <  |  __/ \__ \\
  \\_____|  \\___/   \\___/   \__, | |_|  \\___|  \\____/   \__,_| |_|\\_\\  \___| |___/
                            __/ |                                                
                           |___/
                           ''')
    #Print a dividing line
    v.put("-"*120)
    #Print opening text
    v.put("Welcome To Google Jukes! Unofficial Google Jukebox.")
    v.put('Type "help" to see what you can do, or type "help" [COMMAND] to get help with a specific command.')
    v.put("If you can't hear the tunes, open up volume mixer and make sure 'Python' isn't muted, it may be by default!")
    v.put("If you see a black window pop up, don't worry. It's just an audio converter.")
    #Print a dividing line
    v.put("-"*120)
    #Check for commands from the user
    while active:
        v.ask()
