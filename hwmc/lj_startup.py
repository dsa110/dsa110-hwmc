"""LabJack T7 start_up _check"""

import time
import inspect

from labjack import ljm
import dsautils.dsa_syslog as dsl
from hwmc.common import Config as CONF


MODULE_NAME = __name__


def t7_startup_check(lj_handle, lua_required, ant_num):
    """Read various parameters from the LabJack T7 device.

    Parameters that are read from the LabJack T7 include code versions, hardware serial number, etc.
    The information is put into a monitor point dictionary, and the values are compared with the
    requirements.

    Args:
        lj_handle (int): Unique handle for the LabJack driver for this antenna.
        lua_required (bool): Indicates if a Lua script should be present and running.

    Returns:
        start_up_state (dict): Dictionary of monitor points with the startup information acquired.
    """
    # Set up class-level logging (per class instance).
    class_name = 'None'
    func = inspect.stack()[0][3]
    print(func)
    func_name = "{}".format(func)
    logger_name = '{}_Ant{}'.format(MODULE_NAME, ant_num)
    logger = dsl.DsaSyslogger(subsystem_name=CONF.SUBSYSTEM,
                                   log_level=CONF.LOGGING_LEVEL,
                                   logger_name=logger_name)
    logger.app(CONF.APPLICATION)
    logger.version(CONF.VERSION)
    logger.function(func_name)
    logger.info("{} logger created".format(logger_name))
    logger.info("Initializing")
    logger.info("Antenna {} connected".format(ant_num))

    start_up_state = dict(factory=False, prod_id=-1, hw_ver=0.0, fw_ver=0.0, boot_ver=0.0, ser_no=0,
                          dev_name='', lua_running=False, lua_code_ver=-1, config_valid=True)

    # Read relevant device information and configuration registers.
    start_up_state['factory'] = bool(ljm.eReadName(lj_handle, 'IO_CONFIG_CHECK_FOR_FACTORY'))
    start_up_state['prod_id'] = int(ljm.eReadName(lj_handle, 'PRODUCT_ID'))
    start_up_state['hw_ver'] = float(format(ljm.eReadName(lj_handle, 'HARDWARE_VERSION'), '.4f'))
    start_up_state['fw_ver'] = float(format(ljm.eReadName(lj_handle, 'FIRMWARE_VERSION'), '.4f'))
    start_up_state['boot_ver'] = float(format(ljm.eReadName(lj_handle, 'BOOTLOADER_VERSION'),
                                              '.4f'))
    start_up_state['ser_no'] = int(ljm.eReadName(lj_handle, 'SERIAL_NUMBER'))
    dev_name = bytes(ljm.eReadNameByteArray(lj_handle, 'DEVICE_NAME_DEFAULT', 49))
    d_name = ''
    for device in dev_name:
        if device == 0:
            break
        d_name += chr(device)
    start_up_state['dev_name'] = d_name
    start_up_state['lua_running'] = bool(ljm.eReadName(lj_handle, 'LUA_RUN'))
    if start_up_state['lua_running'] is False and lua_required is True:
        print('Lua script not running. Attempting to load and start script')
        ljm.eWriteName(lj_handle, 'LUA_LOAD_SAVED', 1)
        time.sleep(2.0)
        try:
            ljm.eWriteName(lj_handle, 'LUA_RUN', 1)
        except ljm.LJMError as e:
            logger.error("No script loaded in T7: {}".format(ljm.errorToString(e)))

        time.sleep(2.0)
        start_up_state['lua_running'] = bool(ljm.eReadName(lj_handle, 'LUA_RUN'))
        if start_up_state['lua_running'] is False:
            print('Failed to start script')
            start_up_state['config_valid'] = False

    start_up_state['lua_code_ver'] = format(float(ljm.eReadAddress(lj_handle, 46000, 3)), '.3f')

    for k, val in start_up_state.items():
        print(" --{}: {}".format(k, val))

    if start_up_state['factory'] is False or start_up_state['prod_id'] != 7:
        start_up_state['config_valid'] = False
    return start_up_state
