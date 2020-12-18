"""Utility to allow storage of configuration parameters in LabJack T7 flash memory"""

import time as time

import dsautils.dsa_syslog as dsl
from labjack import ljm
from labjack.ljm import constants as ljc

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

INTERNAL_FLASH_KEY = 61800
INTERNAL_FLASH_ERASE = 61820
INTERNAL_FLASH_WRITE_POINTER = 61830
INTERNAL_FLASH_WRITE = 61832
INTERNAL_FLASH_READ_POINTER = 61810
INTERNAL_FLASH_READ = 61812
INTERNAL_FLASH_USER_KEY = 0x6615E336


def write_config_to_flash(lj_handle, cal_table):
    """Write the supplied configuration values to the LabJack T7 flash memory

    This function will take a list of values and write them to the flash memory in the LabJack T7,
    starting at the beginning of the user flash memory area.

    Args:
        lj_handle (int): A handle to address the T7 module where the data are to be written.
        cal_table (:obj:'list' of 'float'): Table of configuration values to write to flash.

    Raises:
        ljm.LJMError: An error occurred accessing the LabJack drivers.

    """

    # Check to see if new values are different from stored values.
    same = True
    addr = 0
    old_table = []
    for value in cal_table:
        ljm.eWriteAddress(lj_handle, INTERNAL_FLASH_READ_POINTER, ljc.INT32, addr)
        old = ljm.eReadAddressArray(lj_handle, INTERNAL_FLASH_READ, ljc.FLOAT32, 1)[0]
        old_table.append(old)
        # Numerical representations of new value and value in flash may not be identical.
        # Also test for NaN
        if (old != old) or (abs(old - value) > 0.001):
            same = False
        addr = addr + 4

    # Write new values if they are different.
    if not same:
        LOGGER.info("Writing new inclinometer calibration values.")
        LOGGER.info("Old values: {}".format(old_table))
        LOGGER.info("New values: {}".format(cal_table))
        # Start by erasing flash to avoid errors.
        a_addresses = [INTERNAL_FLASH_KEY, INTERNAL_FLASH_ERASE]
        a_data_types = [ljc.INT32, ljc.INT32]
        a_values = [INTERNAL_FLASH_USER_KEY, 0]
        num_frames = len(a_addresses)
        ljm.eWriteAddresses(lj_handle, num_frames, a_addresses, a_data_types, a_values)
        # Set up for writing flash
        a_addresses = [INTERNAL_FLASH_KEY, INTERNAL_FLASH_WRITE_POINTER, INTERNAL_FLASH_WRITE]
        a_data_types = [ljc.INT32, ljc.INT32, ljc.FLOAT32]
        a_values = [INTERNAL_FLASH_USER_KEY, 0, 0.0]
        num_frames = len(a_addresses)
        # Write values one-by-one to avoid overflowing allowed packet size.
        addr = 0
        for value in cal_table:
            a_values[1] = addr
            a_values[2] = value
            ljm.eWriteAddresses(lj_handle, num_frames, a_addresses, a_data_types, a_values)
            addr = addr + 4
        time.sleep(1.0)
        # Restart Lua script to pick up new values from flash
        # Disable a running script by writing 0 to LUA_RUN twice
        ljm.eWriteName(lj_handle, "LUA_RUN", 0)
        # Wait for the Lua VM to shut down (and some T7 firmware versions need a longer time to
        # shut down than others).
        time.sleep(1.0)
        ljm.eWriteName(lj_handle, "LUA_RUN", 0)
        time.sleep(2.0)
        try:
            ljm.eWriteName(lj_handle, 'LUA_RUN', 1)
        except ljm.LJMError:
            LOGGER.error("Failed to restart Lua script after writing config data.")
