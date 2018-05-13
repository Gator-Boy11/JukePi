#!/usr/bin/python3

import os
import platform
import sys
import subprocess
import traceback
import shutil
canElevate = True
try:
    import win32com.shell.shell as shell
except:
    canElevate = False

ASADMIN = 'asadmin'

#==============================================================
#               Default Definitions                                                                                   
#==============================================================

# this is a copy of python's license agreement
_licenseCopy = '''
MIT License\n
\n
Copyright (c) 2016 Olli-Pekka Heinisuo, Carlos Martinez\n
\n
Permission is hereby granted, free of charge, to any person obtaining a copy\n
of this software and associated documentation files (the "Software"), to deal\n
in the Software without restriction, including without limitation the rights\n
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell\n
copies of the Software, and to permit persons to whom the Software is\n
furnished to do so, subject to the following conditions:\n
\n
The above copyright notice and this permission notice shall be included in all\n
copies or substantial portions of the Software.\n
\n
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\n
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\n
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\n
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\n
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\n
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE\n
SOFTWARE.\n
'''

#==============================================================
#               Controls                                                                                                 
#==============================================================
    
def putter(string, *args):
    print(string)
    
def getter(string, *args):
    return input(string)
    
def error(string, *args):
    print(string, file= sys.stderr)

def close(code = 0, *args):
    exit(code)

#==============================================================
#               Commands                                                                                             
#==============================================================

def start(source, *args):
    source.put(source.variables["VERSION"])
    if source.variables["ISADMIN"]:
        source.put("Currently running with administrator priveledges.")
    return None

def closer(source, *args):
    """
Usage: {0}
        Displays {DATA} in [COLUMNS] columns.
        """
    source.close(0)

def echoColumns(source, columns, *args):
    """
Usage: {0} [COLUMNS] (DATA)
        Returns (DATA) in [COLUMNS] columns.
        """
    args = list(args)
    for i in range(0, len(args) % columns):
        args.append("")
    data = [args[i:i+columns] for i in range(0, len(args), columns)]
    col_width = len(max(args, key=len)) + 2  # padding
    output = ""
    for row in data:
        buf = ""
        for word in row:
            buf = buf + "".join(word.ljust(col_width))
        output = output + buf + "\n"
    output = output.rstrip("\n")
    return str(output)

def variable(source, *args):
    """
Usage: {0} $[NAME] = (VALUE)
        Sets [NAME] to (Value),
        Returns the value of [NAME]

Usage: {0} $[NAME]
        Returns the value of [NAME]
        """
    args = list(args)
    value = "source.variables['" + args.pop(0)[1:] + "']"
    for num in range(len(args)):
        if args[num][0] == "$":
            args[num] = "source.variables['" + args[num][1:] + "']"
    equation = " ".join(args)
    exec(value + equation)
    return eval(value)
            
def getVersion(source, *args):
    """
Usage: {0}
        Returns the current Terminal Velocity Version
        """
    return source.variables["VERSION"]

def hello(source, *args):
    """
Usage: {0}
        Says hello to you.
        """
    return "Hello {0}!".format(os.environ.get('USERNAME'))

def execute(source, *args):
    """
Usage: {0} (COMMAND)
        Runs (COMMAND) in the system terminal.
        """
    try:
        return str(subprocess.check_output(*args, shell=True, universal_newlines=True))
    except subprocess.CalledProcessError:
        return "'ip' is not recognized as an internal or external command,\noperable program or batch file."

def pwd(source, *args):
    """
Usage: {0}
        Prints the current working directory
        """
    return os.getcwd()

def cd(source, *args):
    """
Usage: {0} [LOCATION]
        Changes current working directory to [LOCATION]
        """
    args = list(args)
    if len(args) > 0:
        if "-A" in args:
            os.chdir(args[0])
        else:
            path = os.getcwd()
            while args[0] == "../" or args[0] == "..\\":
                args[0] = args[0][2:]
                if path.rfind("\\") != -1:
                    path = path[:path.rfind("\\")]
                else:
                    path = path[:path.rfind("/")]
            path = path + "\\" + args[0]
            os.chdir(path)        
    else:
        source.err("No Input")

def cp(source, *args):
    """
Usage: {0} [SOURCE] [DESTINATION]
        Copies [SOURCE] to [DESTINATION].
        """
    if len(args) >= 2:
        shutil.copy2(args[0], args[1])
    else:
        return "Invalid Input"

def helper(source, *args):
    """
Usage: {0}
        Gives a list of commands that
        can be used

Usage: {0} [COMMAND]
        Gives information on how to use
        [COMMAND]
        """
    args = list(args)
    if len(args) == 0:
        return 'Type "help help" for information on the help command\n' + echoColumns(source, 2, *sorted(list(source.commands.keys())))
    elif len(args) == 1:
        return str(source.commands[args[0]].__doc__).format(str(args[0]))
    else:
        return helper(source, "help")

 
def python(source, *args):
    """
Usage: {0}
        Opens a virtual python environment.

Usage: {0} [FILE]
        Runs a python file
        """
    source.put("\n\nPython " + sys.version)
    source.put('Type "copyright", "credits" or "license()" for more information.')
    source.put("You are now running Terminal Velocity's Python environment.")
    source.put("This is still in development, and may be buggy.")
    if len(args) != 0:
        with open (args[0], "r") as myfile:
            source.put(">>> \n=== RESTART: {} ===".format(os.path.abspath(args[0])))
            data=myfile.read()
            data = data.replace("print(", "source.put(")
            try:
                exec(data)
            except Exception as e:
                source.err(e)
    running = True
    while running:
        command = source.get(">>> ")
        if command == "exit()":
            running = False
        elif command == "copyright":
            source.put(copyright)
        elif command == "credits":
            source.put(credits)
        elif command == "license()":
            source.put(_licenseCopy)
        else:
            if command.rstrip()[-1] == ":":
                while command.replace[-1] != "\n":
                    command = command + "\n" + source.get(" " * 4)
            command = command.replace("print(", "source.put(")
            try:
                value = eval(command)
                if value != None:
                    source.put(value)
            except:
                try:
                    exec(command)
                except Exception as e:
                    source.err(source.exc(e))

def elevate(source, *args):
    """
Usage: {0}
        Elevates the current user
        """
    global canElevate
    if canElevate:
        if not source.variables["ISADMIN"]:
            script = os.path.abspath(sys.argv[0])
            params = ' '.join([script] + sys.argv[1:] + [ASADMIN])
            shell.ShellExecuteEx(lpVerb='runas', lpFile=sys.executable, lpParameters=params)
            print("elevated")
    else:
        return "User cannot be elevated"

#==============================================================
#               Definitions                                                                                              
#==============================================================


basic_Controls = {
    "__put__": putter,
    "__get__": getter,
    "__err__": error,
    "__exit__": close
    }
            
basic_Commands = {
    "getVersion": getVersion,
    "python": python,
    "python{0}".format(sys.version_info[0]): python,
    "python{0}.{1}".format(sys.version_info[0], sys.version_info[1]): python,
    "hello": hello,
    "execute": execute,
    "pwd": pwd,
    "cd": cd,
    "cp": cp,
    "help": helper,
    "var": variable,
    "echoColumns": echoColumns,
    "__start__": start,
    "elevate": elevate
    }

basic_Variables = {
    "VERSION": "Terminal Velocity - 1.0",
    "ISADMIN": sys.argv[-1] == ASADMIN,
    "": "0.0.1",
    "OS": platform.system(),
    "OS_RELEASE": platform.release(),
    "OS_VERSION": platform.version(),
    "PLATFORM": platform.platform()
}


