#!/usr/bin/python3

#Author: David Johnston
#Description: Wrapper for googleJukes for the raspberry pi

WINDOWS_DEBUG_ON = False #Set to true to allow the program to run in windows. With the screen disabled, of course

PI_DEBUG_ON = False #Set to true to show any raspberry pi debug messages

#ALSA Lib likes to send out annoying messages, this allows them to be disabled
if not WINDOWS_DEBUG_ON:
    from ctypes import *
    ERROR_HANDLER_FUNC = CFUNCTYPE(None, c_char_p, c_int, c_char_p, c_int, c_char_p)
    def py_error_handler(filename, line, function, err, fmt):
        global PI_DEBUG_ON
        if PI_DEBUG_ON:
            print('ALSA lib had some problem...                             ...AGAIN.')
    c_error_handler = ERROR_HANDLER_FUNC(py_error_handler)
    asound = cdll.LoadLibrary('libasound.so')
    asound.snd_lib_error_set_handler(c_error_handler)

import googleJukes, configparser, os, time, copy
#googleJukes.pyaudio.pa.__file__ = '/home/pi/.local/lib/python3.5/site-packages/_portaudio.cpython-35m-arm-linux-gnueabihf.so'

if not WINDOWS_DEBUG_ON:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    
    GPIO.setup(17, GPIO.IN)#, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(27, GPIO.IN)#, pull_up_down=GPIO.PUD_DOWN)
    GPIO.setup(22, GPIO.IN)#, pull_up_down=GPIO.PUD_DOWN)

    GPIO.setup(5, GPIO.IN)#, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(6, GPIO.IN)#, pull_up_down=GPIO.PUD_UP)
    GPIO.setup(13, GPIO.IN)#, pull_up_down=GPIO.PUD_UP)

importErrors = False
try:
    from luma.core.interface.serial import spi
    from luma.oled.device import ssd1351
except:
    print("Luma is not installed. Install it with 'sudo apt-get install libfreetype6-dev libjpeg-dev build-essential' and 'sudo -H pip3 install --upgrade luma.oled'")
    if not WINDOWS_DEBUG_ON:
        importErrors = True
try:
    from PIL import Image, ImageFont, ImageDraw
except:
    print("Pillow is not installed. Install it with 'pip3 install Pillow'")
    importErrors = True
if importErrors:
    print("Required Libraries not installed. Please install them and try again.")
    junk = getch()
    exit()

#Setup OLED screen
if not WINDOWS_DEBUG_ON:
    device = ssd1351(spi(device=1, port=0))


screenState = True
menuActive = False
buttonsActive = True

#load image stuffs, like backgrounds, diskmasks, fonts, etc.
songBackground = Image.open("background.jpg").convert("RGBA")
menuBackground = Image.open("menu.jpg").convert("RGBA")
infoBackground = Image.open("info.jpg").convert("RGBA")
diskMask = Image.open("diskMask.png").convert("RGBA")
blankDisk = Image.new("RGBA", (67,67), (0,0,0,0))
blankDisplay =  Image.new("RGB", (128,128), (0,0,0))
blankText = Image.new("RGBA", (122,34), (255,255,255,255))
songFont = ImageFont.truetype("roboto/Roboto-Condensed.ttf", 15)
headerFont = ImageFont.truetype("roboto/Roboto-BoldCondensed.ttf", 15)
displayFont = ImageFont.truetype("roboto/Roboto-Condensed.ttf", 45)

#Create button map
buttonMap = {
    17:0,
    27:1,
    22:2,
    5:3,
    6:4,
    13:5
    }

#draw Background
drawing = songBackground.copy()
if not WINDOWS_DEBUG_ON:
    device.display(drawing.convert("RGB"))

#Create modified form of the player handler. This one uses dead time from the regular one to update the screen
def customPlayerHandler():
    global device, songBackground, diskMask, blankDisk, blankText, songFont, googleJukes, configparser, ImageDraw
    songNameParser = configparser.ConfigParser()
    songNameParser.read(os.getcwd() + os.sep + "config.ini")
    while googleJukes.active:
        if googleJukes.playing:
            if os.path.exists(os.getcwd() + "/albumArt/" + googleJukes.playlist[googleJukes.playlistIterator] + ".jpg"):
                albumArt = Image.open(os.getcwd() + "/albumArt/" + googleJukes.playlist[googleJukes.playlistIterator] + ".jpg").resize((67,67)).convert("RGBA")
                pictureDisk = Image.composite(albumArt, blankDisk.copy(), diskMask)
            else:
                pictureDisk = diskMask.copy()
            songText = blankText.copy()
            songDraw = ImageDraw.Draw(songText)
            songDraw.text((0, 0), googleJukes.googleJukesLib.unescapeName(songNameParser[googleJukes.playlist[googleJukes.playlistIterator]]["title"]) + "\n" + songNameParser[googleJukes.playlist[googleJukes.playlistIterator]]["artist"] , (0,0,0,255), songFont)
            googleJukes.rawWf = googleJukes.pydub.AudioSegment.from_file(os.getcwd() + "/songs/" + googleJukes.playlist[googleJukes.playlistIterator] + ".mp3")
            googleJukes.wf = googleJukes.rawWf.apply_gain(googleJukes.volume)
            if googleJukes.playspeed < 0:
                googleJukes.frameCounter = googleJukes.wf.frame_count()/1024-(googleJukes.wf.frame_width-(googleJukes.wf.frame_count()%1024)/256)
            else:
                googleJukes.frameCounter = 0
            stream = googleJukes.audioOut.open(format=googleJukes.audioOut.get_format_from_width(googleJukes.wf.sample_width),
                channels=googleJukes.wf.channels,
                rate=googleJukes.wf.frame_rate,
                output=True,
                stream_callback=googleJukes.callback)
            stream.start_stream()
            googleJukes.skipper.set()
            while googleJukes.playing and stream.is_active():
                googleJukes.skipper.clear()
                drawing = songBackground.copy()
                drawing.alpha_composite(pictureDisk.rotate(googleJukes.frameCounter*1024/googleJukes.wf.frame_rate/60*(33+(1.0/3.0))*360), (30,16))
                drawing.alpha_composite(songText, (3, 92))
                if (screenState and not menuActive) and not WINDOWS_DEBUG_ON:
                    device.display(drawing.convert("RGB"))
                googleJukes.skipper.set()
            if googleJukes.playing and googleJukes.loopVar != 1:
                googleJukes.playlistIterator += 1
            stream.stop_stream()
            stream.close()
            if googleJukes.playlistIterator >= len(googleJukes.playlist):
                googleJukes.playlistIterator = 0
                if googleJukes.loopVar == 2:
                    if googleJukes.shuffleVar:
                        googleJukes.random.shuffle(googleJukes.playlist)
                else:
                    googleJukes.skipper.wait(1)
                    googleJukes.playing = False
        else:
            googleJukes.skipper.set()
            googleJukes.skipper.clear()
    googleJukes.audioOut.terminate()

googleJukes.playerThread = googleJukes.threading.Thread(target = customPlayerHandler)

def display(source, *args):
    """
Usage: {0}
        Show whether display is on or not

Usage: {0} on
        Turns on display

Usage: {0} off
        Turns off display

Usage: {0} type
        Describes the display device

Usage: {0} reset
        resets the display device if it glitches
        """
    global screenState, device, googleJukes
    if len(args) != 0:
        if args[0].lower() == "on":
            if not WINDOWS_DEBUG_ON:
                device.show()
            screenState = True
        elif args[0].lower() == "off":
            screenState = False
            googleJukes.skipper.wait(1)
            if not WINDOWS_DEBUG_ON:
                device.hide()
        elif args[0].lower() == "type":
            if WINDOWS_DEBUG_ON:
                source.put("Windows does not have a display. :(")
            elif isinstance(device, ssd1351):
                source.put("(Adafruit?) SSD1351 Based SPI OLED Screen, 128x128px.")
        elif args[0].lower() == "reset":
            if WINDOWS_DEBUG_ON:
                source.put("Windows does not have a display to reset. :(")
            elif isinstance(device, ssd1351):
                source.put("Resetting (Adafruit?) SSD1351 Based SPI OLED Screen, 128x128px.")
                device.cleanup()
                device = ssd1351(spi(device=1, port=0))
                drawing = background.copy()
                device.display(drawing.convert("RGB"))
    return screenState

def volumeDisplay(source, *args):
    """
Usage: {0}
        Returns the music volume

Usage: {0} [VOLUME]
        Sets the music volume
        """
    global device, blankDisplay, displayFont, googleJukes, time, ImageDraw, screenState, songBackground
    out = googleJukes.setVolume(source, *args)
    if not WINDOWS_DEBUG_ON:
        if screenState:
            screenState = False
            googleJukes.skipper.wait(1)
            if isinstance(out, float):
                disp = blankDisplay.copy()
                dispDraw = ImageDraw.Draw(disp)
                dispDraw.text((2,2), "Volume:", (255,255,255), songFont)
                dispDraw.text((2,32), str(out), (255,255,255), displayFont)
                device.display(disp)
                time.sleep(2)
                drawing = songBackground.copy()
                device.display(drawing.convert("RGB"))
            screenState = True
        else:
            device.show()
            if isinstance(out, float):
                disp = blankDisplay.copy()
                dispDraw = ImageDraw.Draw(disp)
                dispDraw.text((2,2), "Volume:", (255,255,255), songFont)
                dispDraw.text((2,32), str(out), (255,255,255), displayFont)
                device.display(disp)
                time.sleep(2)
                drawing = songBackground.copy()
                device.display(drawing.convert("RGB"))
            device.hide()

def volumeControl(source, *args):
    """
Usage: {0}
        Returns the music volume

Usage: {0} [VOLUME]
        Sets the music volume
        """
    global device, blankDisplay, displayFont, googleJukes, time, ImageDraw, screenState, menuBackground, buttonsActive
    out = googleJukes.setVolume(source)
    if not WINDOWS_DEBUG_ON:
        buttonsActive = False
        if screenState:
            screenState = False
            googleJukes.skipper.wait(1)
            while GPIO.input(27) != 1:
                if GPIO.input(22) == 1:
                    out += 1
                    time.sleep(0.25)
                elif GPIO.input(13) == 0:
                    out -= 1
                    time.sleep(0.25)
                if isinstance(out, float):
                    disp = blankDisplay.copy()
                    dispDraw = ImageDraw.Draw(disp)
                    dispDraw.text((2,2), "Volume:", (255,255,255), songFont)
                    dispDraw.text((2,32), str(out), (255,255,255), displayFont)
                    device.display(disp)
            googleJukes.setVolume(source, out)
            screenState = True
        else:
            device.show()
            while GPIO.input(27) != 1:
                if GPIO.input(22) == 1:
                    out += 1
                    time.sleep(0.25)
                elif GPIO.input(13) == 0:
                    out -= 1
                    time.sleep(0.25)
                if isinstance(out, float):
                    disp = blankDisplay.copy()
                    dispDraw = ImageDraw.Draw(disp)
                    dispDraw.text((2,2), "Volume:", (255,255,255), songFont)
                    dispDraw.text((2,32), str(out), (255,255,255), displayFont)
                    device.display(disp)
            googleJukes.setVolume(source, out)
            device.hide()
        openMenu(source)

def speedDisplay(source, *args):
    """
Usage: {0}
        Returns the music playspeed

Usage: {0} [SPEED]
        Sets the music playspeed
        """
    global device, blankDisplay, displayFont, googleJukes, time, ImageDraw, screenState, songBackground
    out = googleJukes.setSpeed(source, *args)
    if not WINDOWS_DEBUG_ON:
        if screenState:
            screenState = False
            googleJukes.skipper.wait(1)
            if isinstance(out, float):
                disp = blankDisplay.copy()
                dispDraw = ImageDraw.Draw(disp)
                dispDraw.text((2,2), "Speed:", (255,255,255), songFont)
                dispDraw.text((2,32), str(out), (255,255,255), displayFont)
                device.display(disp)
                time.sleep(2)
                drawing = songBackground.copy()
                device.display(drawing.convert("RGB"))
            screenState = True
        else:
            device.show()
            if isinstance(out, float):
                disp = blankDisplay.copy()
                dispDraw = ImageDraw.Draw(disp)
                dispDraw.text((2,2), "Speed:", (255,255,255), songFont)
                dispDraw.text((2,32), str(out), (255,255,255), displayFont)
                device.display(disp)
                time.sleep(2)
                drawing = songBackground.copy()
                device.display(drawing.convert("RGB"))
            device.hide()

def speedControl(source, *args):
    """
Usage: {0}
        Returns the music playspeed

Usage: {0} [VOLUME]
        Sets the music playspeed
        """
    global device, blankDisplay, displayFont, googleJukes, time, ImageDraw, screenState, menuBackground, buttonsActive
    print(buttonsActive)
    out = googleJukes.setSpeed(source)
    if not WINDOWS_DEBUG_ON:
        buttonsActive = False
        if screenState:
            screenState = False
            googleJukes.skipper.wait(1)
            while GPIO.input(27) != 1:
                if GPIO.input(22) == 1:
                    out += 1
                    time.sleep(0.25)
                elif GPIO.input(13) == 0:
                    out -= 1
                    time.sleep(0.25)
                if isinstance(out, float):
                    disp = blankDisplay.copy()
                    dispDraw = ImageDraw.Draw(disp)
                    dispDraw.text((2,2), "Speed:", (255,255,255), songFont)
                    dispDraw.text((2,32), str(out), (255,255,255), displayFont)
                    device.display(disp)
            googleJukes.setSpeed(source, out)
            screenState = True
        else:
            device.show()
            while GPIO.input(27) != 1:
                if GPIO.input(22) == 1:
                    out += 1
                    time.sleep(0.25)
                elif GPIO.input(13) == 0:
                    out -= 1
                    time.sleep(0.25)
                if isinstance(out, float):
                    disp = blankDisplay.copy()
                    dispDraw = ImageDraw.Draw(disp)
                    dispDraw.text((2,2), "Speed:", (255,255,255), songFont)
                    dispDraw.text((2,32), str(out), (255,255,255), displayFont)
                    device.display(disp)
            googleJukes.setSpeed(source, out)
            device.hide()

menuTree = [
    {
        "header":"System & Settings",
        "options": [
            "Volume",
            "Speed",
            "User",
            "Timeout",
            "Logout",
            "Last Tab"
            ],
        "functions": [
            "volumeControl",
            "speedControl",
            None,
            None,
            "logout",
            "lastTab",
            ],
        "information": [
            "Control the playback volume",
            "Control the playback speed",
            "Change the user information",
            "Set the screen timeout",
            "Shut down the system",
            "Go to the last tab"
            ],
        },
    {
        "header":"Playlist",
        "options": [
            "Library",
            "Last Tab",
            ],
        "functions": [
            "play library",
            "lastTab",
            ],
        "information": [
            "Play the entire library",
            "Go to the last tab",
            ],
        },
    {
        "header":"Songs",
        "options": [
            "Last Tab",
            ],
        "functions": [
            "lastTab",
            ],
        "information": [
            "Go to the last tab",
            ],
        },
    ]

googleJukes.playlistParser.read(os.getcwd() + os.sep + "config.ini")

for item in googleJukes.json.loads(googleJukes.googleJukesLib.unescapeName(googleJukes.playlistParser["library"]["playlists"])):
    menuTree[1]["options"].insert(-1, googleJukes.googleJukesLib.unescapeName(googleJukes.playlistParser[item]["name"]))
    menuTree[1]["functions"].insert(-1, "play playlist-id " + googleJukes.googleJukesLib.unescapeName(googleJukes.playlistParser[item]["id"]))
    menuTree[1]["information"].insert(-1, "Plays playlist " + googleJukes.googleJukesLib.unescapeName(googleJukes.playlistParser[item]["name"]))
    
for item in googleJukes.json.loads(googleJukes.googleJukesLib.unescapeName(googleJukes.playlistParser["library"]["tracks"])):
    menuTree[2]["options"].insert(-1, googleJukes.googleJukesLib.unescapeName(googleJukes.playlistParser[item]["title"]))
    menuTree[2]["functions"].insert(-1, "play song-id " + googleJukes.googleJukesLib.unescapeName(googleJukes.playlistParser[item]["id"]))
    menuTree[2]["information"].insert(-1, "Plays song " + googleJukes.googleJukesLib.unescapeName(googleJukes.playlistParser[item]["title"]) + "\nBy: " + googleJukes.googleJukesLib.unescapeName(googleJukes.playlistParser[item]["artist"]))

tab = 0
showing = 0
selection = 0
tree = []

def getAt(list, index, default=None):
    return list[index] if max(~index, index) < len(list) else default

def openMenu(source, *args):
    """
Usage: {0}
        Opens the mini-screen menu
    """
    global menuTree, tab, showing, selection, tree
    tree = copy.deepcopy(menuTree[tab]["options"])
    displayMenu(source, menuTree[tab]["header"], getAt(tree, showing+0, ""), getAt(tree, showing+1, ""), getAt(tree, showing+2, ""), getAt(tree, showing+3, ""), selection - showing + 1)

def downMenu(source, *args):
    """
Usage: {0}
        Move one tab down in the menu
    """
    global menuTree, tab, showing, selection, tree
    selection += 1
    if selection >= len(tree):
        selection = 0
        showing = 0
    elif selection > showing+3:
        showing += 1
    displayMenu(source, menuTree[tab]["header"], getAt(tree, showing+0, ""), getAt(tree, showing+1, ""), getAt(tree, showing+2, ""), getAt(tree, showing+3, ""), selection - showing + 1)

def upMenu(source, *args):
    """
Usage: {0}
        Move one tab up in the menu
    """
    global menuTree, tab, showing, selection, tree
    selection -= 1
    if selection < 0:
        selection = len(tree) - 1
        showing = len(tree) - 4
    elif selection < showing:
        showing -= 1
    displayMenu(source, menuTree[tab]["header"], getAt(tree, showing+0, ""), getAt(tree, showing+1, ""), getAt(tree, showing+2, ""), getAt(tree, showing+3, ""), selection - showing + 1)

def nextTab(source, *args):
     global tab, selection
     tab += 1
     if tab >= len(menuTree):
         tab = 0
     selection = 0
     openMenu(source)

def lastTab(source, *args):
     global tab, selection
     tab -= 1
     if tab < 0:
         tab = len(menuTree) - 1
     selection = 0
     openMenu(source)

def selectMenu(source, *args):
    global menuTree, tab, showing, selection
    if getAt(menuTree[tab]["functions"], selection) != None:
        return source.command(menuTree[tab]["functions"][selection])

def infoMenu(source, *args):
    """
Usage: {0} Text
        Opens the mini-screen menu
    """
    global menuActive, infoBackground, device, songFont, headerFont
    if not (WINDOWS_DEBUG_ON or screenState):
        device.show()
    menuActive = True
    googleJukes.skipper.wait(1)
    disp = infoBackground.copy()
    dispDraw = ImageDraw.Draw(disp)
    dispDraw.text((4,4), " ".join(args), (0,0,0), songFont)
    if not (WINDOWS_DEBUG_ON or not screenState):
        device.display(disp.convert("RGB"))

def displayMenu(source, *args):
    """
Usage: {0} [HEADER] [OPTION1] [OPTION2] [OPTION3] [OPTION4] [SELECTED]
        Opens the mini-screen menu
    """
    global menuActive, menuBackground, device, songFont, headerFont
    options = list(args) + ["","","","",""]
    selected = -1
    if len(args) >= 6:
        if str(args[5]).isdigit():
            selected = int(args[5])
    if not (WINDOWS_DEBUG_ON or screenState):
        device.show()
    menuActive = True
    googleJukes.skipper.wait(1)
    disp = menuBackground.copy()
    dispDraw = ImageDraw.Draw(disp)
    dispDraw.text((4,4), options[0], (0,0,0), headerFont)
    for i in range(1,5):
        if i == selected:
            dispDraw.rectangle((2,2+i*25,125,25+i*25), (65, 169, 244), (66, 134, 244))
            dispDraw.text((4,4+i*25), options[i], (255,255,255), songFont)
        else:
            dispDraw.text((4,4+i*25), options[i], (0,0,0), songFont)
    if not (WINDOWS_DEBUG_ON or not screenState):
        device.display(disp.convert("RGB"))

def closeMenu(source, *args):
    """
Usage: {0}
        Closes the mini-screen menu
    """
    global menuActive, menuBackground, device
    args = list(args) + ["","","",""]
    drawing = songBackground.copy()
    if not WINDOWS_DEBUG_ON:
        device.display(drawing.convert("RGB"))
    if screenState:
        menuActive = False
    else:
        menuActive = False
        if not WINDOWS_DEBUG_ON:
            device.hide()

def buttonCallback(channel):
    global v, buttonMap, menuActive, menuTree, selection, buttonsActive
    if buttonsActive:
        if menuActive:
            out = v.command(
                [
                    "info " + getAt(menuTree[tab]["information"], selection, "No info found!"),
                    "closeMenu",
                    "upMenu",
                    "closeMenu",
                    "nextTab",
                    "downMenu"
                    ][buttonMap[channel]])
            if buttonMap[channel] == 1:
                v.command("select")
        else:
            out = v.command(
                [
                    "shuffle off" if googleJukes.shuffleVar else "shuffle on",
                    "pause" if not googleJukes.paused else "play",
                    "stop",
                    "openMenu",
                    "loop on" if googleJukes.loopVar == 0 else ("loop single" if googleJukes.loopVar == 2 else "loop off"),
                    "skip"
                    ][buttonMap[channel]])
        v.put("Button " + str(buttonMap[channel]) + " pushed")
        return out
    else:
        if buttonMap[channel] == 1:
            buttonsActive = True
    
GPIO.add_event_detect(17, GPIO.RISING, callback=buttonCallback, bouncetime=500)
GPIO.add_event_detect(27, GPIO.RISING, callback=buttonCallback, bouncetime=500)
GPIO.add_event_detect(22, GPIO.RISING, callback=buttonCallback, bouncetime=500)

GPIO.add_event_detect(5, GPIO.FALLING, callback=buttonCallback, bouncetime=500)
GPIO.add_event_detect(6, GPIO.FALLING, callback=buttonCallback, bouncetime=500)
GPIO.add_event_detect(13, GPIO.FALLING, callback=buttonCallback, bouncetime=500)
    
#Add extra commands to googleJukes
googleJukes.jukeCommands["display"] = display
googleJukes.jukeCommands["screen"] = display
googleJukes.jukeCommands["volume"] = volumeDisplay
googleJukes.jukeCommands["setvolume"] = volumeDisplay
googleJukes.jukeCommands["speed"] = speedDisplay
googleJukes.jukeCommands["setspeed"] = speedDisplay
googleJukes.jukeCommands["openMenu"] = openMenu
googleJukes.jukeCommands["openmenu"] = openMenu
googleJukes.jukeCommands["showMenu"] = displayMenu
googleJukes.jukeCommands["showmenu"] = displayMenu
googleJukes.jukeCommands["upMenu"] = upMenu
googleJukes.jukeCommands["upmenu"] = upMenu
googleJukes.jukeCommands["downMenu"] = downMenu
googleJukes.jukeCommands["downmenu"] = downMenu
googleJukes.jukeCommands["closeMenu"] = closeMenu
googleJukes.jukeCommands["closemenu"] = closeMenu
googleJukes.jukeCommands["nextTab"] = nextTab
googleJukes.jukeCommands["nexttab"] = nextTab
googleJukes.jukeCommands["lastTab"] = lastTab
googleJukes.jukeCommands["lasttab"] = lastTab
googleJukes.jukeCommands["select"] = selectMenu
googleJukes.jukeCommands["info"] = infoMenu
googleJukes.jukeCommands["volumeControl"] = volumeControl
googleJukes.jukeCommands["volumecontrol"] = volumeControl
googleJukes.jukeCommands["speedControl"] = speedControl
googleJukes.jukeCommands["speedcontrol"] = speedControl

if __name__ == "__main__":
    googleJukes.playerThread.start()
    v = googleJukes.TerminalVelocity.Velocity(googleJukes.jukeCommands)
    v.start()
    v.put("-"*120)
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
    v.put("-"*120)
    v.put("Welcome To Google Jukes! Unofficial Google Jukebox.")
    v.put('Type "help" to see what you can do, or type "help" [COMMAND] to get help with a specific command.')
    v.put("You're using the Raspberry Pi(and Beagle Bone?) version, capable of running an OLED screen.")
    v.put("Sorry if their are pops/clicks/audio that fades in/out. it seems to be a kernal/pyaudio issue.")
    v.put("If you see text that starts with 'ALSA lib' you can ignore it. It won't cause issues.")
    v.put("-"*120)
    while True:
        v.ask()
        time.sleep(0.1)

