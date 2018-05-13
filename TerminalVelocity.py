#!/usr/bin/python3

import VelocityLib as tvl
import traceback
import platform
import os, getpass


#==============================================================
#               Class                                                                                                     
#==============================================================


class Velocity:
    def __init__(self, commands = tvl.basic_Commands, controls = tvl.basic_Controls, variables = tvl.basic_Variables):
        self.commands = commands
        self.controls = controls
        self.variables = variables
        self.superUser = False

    def start(self):
        if "__start__" in self.commands:
            self.command("__start__")

    def ask(self):
       self.command(self.get(getpass.getuser() + "@" + platform.node() + ": "))
        
    def command(self, string):
        arguments = string.split(" ")
        if arguments[0] == "sudo":
            self.superUser = True
            arguments.pop(0)
        com = arguments.pop(0)
        try:
            value = self.commands[com](self, *arguments)
            if value == None:
                self.put("")
            else:
                self.put(value)
        except KeyError as e:
            self.put(str(e).replace("'", '"') + " is not a valid command.")
        except Exception as e:
            self.err(self.exc(e))
        self.superUser = False
            
    def put(self, string):
        self.controls["__put__"](string)
            
    def get(self, string, *args):
        return self.controls["__get__"](string, *args)
            
    def err(self, string, *args):
        self.controls["__err__"](string, *args)

    def close(self, code = 0, *args):
        self.controls["__ext__"](code, *args)

    def exc(self, exc):
        exc_type = exc.__class__.__name__
        return ''.join(traceback.format_exception(exc_type, exc, exc.__traceback__))



        
            
            
if __name__ == "__main__":
    v = Velocity()
    v.start()
    while True:
        v.ask()
            
