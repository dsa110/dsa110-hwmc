"""LabJack T7 start_up _check"""

import time
import inspect

from labjack import ljm
import dsautils.dsa_syslog as dsl
from hwmc.common import Config as CONF
import hwmc.lua_script_utilities as util
from hwmc.utilities import vprint as vprint


# Set up module-level logging.
MODULE_NAME = __name__
LOGGER = dsl.DsaSyslogger(subsystem_name=CONF.SUBSYSTEM,
                          log_level=CONF.LOGGING_LEVEL,
                          logger_name=MODULE_NAME)
LOGGER.app(CONF.APPLICATION)
LOGGER.version(CONF.VERSION)
LOGGER.level(CONF.LOGGING_LEVEL)
LOGGER.info("{} logger created".format(MODULE_NAME))


def t7_startup_check(lj_handle, lua_required, ant_num):
    """Read various parameters from the LabJack T7 device.

    Parameters that are read from the LabJack T7 include code versions, hardware serial number, etc.
    The information is put into a monitor point dictionary, and the values are compared with the
    requirements.

    Args:
        lj_handle (int): Unique handle for the LabJack driver for this antenna.
        lua_required (bool): Indicates if a Lua script should be present and running.
        ant_num (int): Number of the antenna, or first antenna on a BEB.

    Returns:
        start_up_state (dict): Dictionary of monitor points with the startup information acquired.
    """
    # Set up class-level logging (per class instance).
    func = inspect.stack()[0][3]
    func_name = "{}::{}".format(MODULE_NAME, func)
    LOGGER.app(CONF.APPLICATION)
    LOGGER.version(CONF.VERSION)
    LOGGER.function(func_name)
    LOGGER.info("Labjack for Ant/BEB {} started".format(ant_num))

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
        vprint('Lua script not running. Attempting to load and start script')
        LOGGER.info("Labjack for Ant/BEB {} Lua script not running. Attempting to load from memory"
                    "".format(ant_num))
        ljm.eWriteName(lj_handle, 'LUA_LOAD_SAVED', 1)
        time.sleep(2.0)
        try:
            ljm.eWriteName(lj_handle, 'LUA_RUN', 1)
        except ljm.LJMError:
            LOGGER.critical("Labjack for Ant/BEB {} cannot load script".format(ant_num))
            lua_script_name = CONF.LUA_DIR + "/antenna_control.lua"
            LOGGER.critical("Attempting to download script {} to ant {}".format(lua_script_name,
                                                                                ant_num))
            script = util.LuaScriptUtilities(lua_script_name, lj_handle)
            script.load()
            script.save_to_flash()
            script.run_on_startup()
            script.run()
            time.sleep(1.0)
            if bool(ljm.eReadName(lj_handle, 'LUA_RUN')) is True:
                LOGGER.critical("Success downloading script {} to ant {}".format(lua_script_name,
                                                                                 ant_num))
            else:
                LOGGER.critical("Failed to download script {} to ant {}".format(lua_script_name,
                                                                                ant_num))

        time.sleep(2.0)
        start_up_state['lua_running'] = bool(ljm.eReadName(lj_handle, 'LUA_RUN'))
        if start_up_state['lua_running'] is False:
            LOGGER.info("Labjack for Ant/BEB {} cannot run script".format(ant_num))
            start_up_state['config_valid'] = False

    start_up_state['lua_code_ver'] = format(float(ljm.eReadAddress(lj_handle, 46000, 3)), '.3f')

    for k, val in start_up_state.items():
        vprint(" --{}: {}".format(k, val))
        LOGGER.info("Ant-{}  {}: {}".format(ant_num, k, val))

    if start_up_state['factory'] is True or start_up_state['prod_id'] != 7:
        start_up_state['config_valid'] = False
    LOGGER.info("Logging Labjack for Ant/BEB {} startup done".format(ant_num))
    return start_up_state
