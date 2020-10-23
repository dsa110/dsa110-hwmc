"""Contains constants and configuration information for the analog hardware M&C package"""
from logging.handlers import SysLogHandler as Syslog

import dsautils.version as ver


class Config:
    """Contains various configuration parameters required in the hwmc package"""
    SUBSYSTEM = 'analog'
    APPLICATION = 'hwmc'
    LOGGING_LEVEL = Syslog.LOG_INFO
    try:
        VERSION = ver.get_git_version()
    except AttributeError:
        VERSION = '0.0.1'
    SIM = False
    VERBOSE = False
    # etcd connection details
    ETCD_ENDPOINT = "etcdv3service.sas.pvt:2379"
    # Lua script directory
    LUA_DIR = '../lua-scripts'
    # Code and firmware version numbers (minimum)
    LJ_HW_VER = 1.300
    LJ_FW_VER = 1.029
    LJ_BOOT_VER = 0.940
    LUA_VER = 1.000
    # Product ID (exact match)
    LJ_PROD_ID = 7

    def print_config(self):
        """Print out the current values of the variables in this store"""
        print("SUBSYSTEM: {}".format(self.SUBSYSTEM))
        print("APPLICATION: {}".format(self.APPLICATION))
        print("LOGGING_LEVEL: {}".format(self.LOGGING_LEVEL))
        print("VERSION: {}".format(self.VERSION))
        print("SIM: {}".format(self.SIM))
        print("VERBOSE: {}".format(self.VERBOSE))
        print("ETCD_ENDPOINT: {}".format(self.ETCD_ENDPOINT))
        print("LUA_DIR: {}".format(self.LUA_DIR))
        print("LJ_HW_VER: {}".format(self.LJ_HW_VER))
        print("LJ_FW_VER: {}".format(self.LJ_FW_VER))
        print("LJ_BOOT_VER: {}".format(self.LJ_BOOT_VER))
        print("LJ_PROD_ID: {}".format(self.LJ_PROD_ID))


class Const:
    """Contains any constants required by the hwmc package"""
    MAX_ANTS = 127

    def print_config(self):
        """Print out the current values of the constants in this store"""
        print("MAX_ANTS: {}".format(self.MAX_ANTS))
