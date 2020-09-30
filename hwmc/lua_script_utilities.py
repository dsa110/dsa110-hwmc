"""This defines a class for handling Lua scripts for LabJack T7 DAQ modules"""

import inspect
import time
from pathlib import Path
from time import sleep
from tkinter import Tk
from tkinter import filedialog

import dsautils.dsa_syslog as dsl
from labjack import ljm

from hwmc.common import Config as CONF

# Set up module-level logging.
MODULE_NAME = __name__
LOGGER = dsl.DsaSyslogger(subsystem_name=CONF.SUBSYSTEM,
                          log_level=CONF.LOGGING_LEVEL,
                          logger_name=MODULE_NAME)
LOGGER.app(CONF.APPLICATION)
LOGGER.version(CONF.VERSION)
LOGGER.level(CONF.LOGGING_LEVEL)
LOGGER.info("{} logger created".format(MODULE_NAME))


class LuaScriptUtilities:
    """Handle loading and running Lua scripts for the LabJack T7 DAQ modules."""

    def __init__(self, lua_script_name, lj_handle):
        """Initialize an object to handle a Lua script for a specified antenna.

        Try to open the specified Lua script. In this version, if a script is not found, a dialog
        box is opened to allow the user to select a script. In the future this will probably be
        removed since it is not compatible with a multi-user system.

        Args:
            lua_script_name (str): A fully qualified filename for a valid Lua script.
            lj_handle (int): A handle to the LabJack that the script is to be loaded into.
        """
        my_class = str(self.__class__)
        self.class_name = (my_class[my_class.find('.') + 1: my_class.find("'>'") - 1])

        func = inspect.stack()[0][3]
        func_name = "{}::{}".format(self.class_name, func)
        LOGGER.function(func_name)
        LOGGER.info("Initializing Lua script class")

        self.handle = lj_handle
        self.err = True
        check = Path(lua_script_name)
        if check.is_file():
            self.err = False
        else:
            check = Path(lua_script_name)
            lua_script_name = lua_script_name + ".lua"
            if check.is_file():
                self.err = False
        self.script = lua_script_name
        if self.err is True:
            root = Tk()
            root.filename = filedialog.askopenfilename(initialdir="/", title="Select file",
                                                       filetypes=(("Lua files", "*.lua"),
                                                                  ("all files", "*.*")))
            check = Path(root.filename)
            if check.is_file():
                self.script = root.filename
                self.err = False
            root.destroy()
        if self.err is True:
            LOGGER.info("Found Lua script '{}'".format(self.script))
        else:
            LOGGER.info("No valid Lua script found")

    def load(self):
        """Load the current Lua file into the LabJack T7.

        This function halts any Lua script running in the T7 and loads the script into it."""
        if self.err is False:
            # Get class for logging.
            msg = "Loading script: {}".format(self.script)
            LOGGER.info(msg)

            # Disable a running script by writing 0 to LUA_RUN twice
            ljm.eWriteName(self.handle, "LUA_RUN", 0)

            # Wait for the Lua VM to shut down (and some T7 firmware versions need a longer time to
            # shut down than others).
            sleep(0.6)
            ljm.eWriteName(self.handle, "LUA_RUN", 0)

            # Read in the file.
            file_handler = open(self.script, 'r')
            lines = file_handler.readlines()
            script = ''
            script = script.join(lines)

            # Check for terminating '\0' and add if missing.
            if script[-1] != '\0':
                script += '\0'
            script_length = len(script)
            print(script)

            # Write the size and the Lua Script to the device.
            ljm.eWriteName(self.handle, "LUA_SOURCE_SIZE", script_length)
            ljm.eWriteNameByteArray(self.handle, "LUA_SOURCE_WRITE", script_length,
                                    bytearray(script, 'ascii'))

    def run(self, debug=False):
        """Run the Lua script currently loaded into the LabJack T7"""
        success = False
        if self.err is False:
            # Start the script with debug output enabled, if required
            if debug is True:
                dbg = 1
            else:
                dbg = 0
            ljm.eWriteName(self.handle, "LUA_DEBUG_ENABLE", dbg)
            ljm.eWriteName(self.handle, "LUA_RUN", 1)
            for _ in range(20):
                if ljm.eReadName(self.handle, "LUA_RUN") == 1.0:
                    success = True
                    break
                time.sleep(0.5)
        return success

    def run_on_startup(self):
        """Set the flag on the LabJack T7 to start the script in flash on power up."""
        if self.err is False:
            ljm.eWriteName(self.handle, "LUA_RUN_DEFAULT", 1)

    def save_to_flash(self):
        """Save the Lua script on the LabJack T7 in the T7 flash memory"""
        ljm.eWriteName(self.handle, "LUA_SAVE_TO_FLASH", 1)
