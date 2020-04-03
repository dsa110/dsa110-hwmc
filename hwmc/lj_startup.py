"""LabJack T7 start_up _check"""

import time
from labjack import ljm


def t7_startup_check(lj_handle):
    """Read various parameters from the LabJack T7 device.

    Parameters that are read from the LabJack T7 include code versions, hardware serial number, etc.
    The information is put into a monitor point dictionary, and the values are compared with the
    requirements.

    Args:
        lj_handle (int): Unique handle for the LabJack driver for this antenna.

    Returns:
        start_up_state (dict): Dictionary of monitor points with the startup information acquired.
    """

    start_up_state = dict(factory=False, prod_id=-1, hw_ver=0.0, fw_ver=0.0, boot_ver=0.0, ser_no=0,
                          dev_name='', lua_running=False, lua_code_ver=-1, config_valid=True)

    # Read relevant device information and configuration registers.
    start_up_state['factory'] = bool(ljm.eReadName(lj_handle, 'IO_CONFIG_CHECK_FOR_FACTORY'))
    start_up_state['prod_id'] = int(ljm.eReadName(lj_handle, 'PRODUCT_ID'))
    start_up_state['hw_ver'] = format(float(ljm.eReadName(lj_handle, 'HARDWARE_VERSION')), '.3f')
    start_up_state['fw_ver'] = format(float(ljm.eReadName(lj_handle, 'FIRMWARE_VERSION')), '.3f')
    start_up_state['boot_ver'] = format(float(ljm.eReadName(lj_handle, 'BOOTLOADER_VERSION')),
                                        '.3f')
    start_up_state['ser_no'] = int(ljm.eReadName(lj_handle, 'SERIAL_NUMBER'))
    dev_name = bytes(ljm.eReadNameByteArray(lj_handle, 'DEVICE_NAME_DEFAULT', 49))
    d_name = ''
    for device in dev_name:
        if device == 0:
            break
        d_name += chr(device)
    start_up_state['dev_name'] = d_name
    start_up_state['lua_running'] = bool(ljm.eReadName(lj_handle, 'LUA_RUN'))
    if start_up_state['lua_running'] is False:
        print('Lua script not running. Attempting to load and start script')
        ljm.eWriteName(lj_handle, 'LUA_LOAD_SAVED', 1)
        time.sleep(2.0)
        ljm.eWriteName(lj_handle, 'LUA_RUN', 1)
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
