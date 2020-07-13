"""Utility to allow storage of configuration parameters in LabJack T7 flash memory"""

import logging
import logging.handlers

from labjack import ljm
from labjack.ljm import constants as ljc

from hwmc.hwmc_logging import CustomFormatter
from hwmc.hwmc_logging import LogConf as Conf

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
        lj_handle (int): A handle to address the T7 module, where the data are to be written.
        cal_table (:obj:'list' of 'float'): Table of configuration values to write to flash.

    Raises:
        ljm.LJMError: An error occurred accessing the LabJack drivers.

    """

    # Set up logging.
    logger = logging.getLogger(Conf.LOGGER + '.' + __name__)

    # Set class name for logging.
    CustomFormatter.log_msg_fmt['class'] = 'None'

    # Check to see if new values are different from stored values.
    same = True
    addr = 0
    for value in cal_table:
        ljm.eWriteAddress(lj_handle, INTERNAL_FLASH_READ_POINTER, ljc.INT32, addr)
        old = ljm.eReadAddressArray(lj_handle, INTERNAL_FLASH_READ, ljc.FLOAT32, 1)[0]
        # Numerical representations of new value and value in flash may not be identical.
        if abs(old - value) > 0.0001:
            same = False
            break
        addr = addr + 4

    # Write new values if they are different.
    if not same:
        logger.info("Writing new inclinometer calibration values.")
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
