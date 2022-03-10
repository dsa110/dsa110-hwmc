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
    LUA_DIR = '/home/ubuntu/proj/dsa110-shell/dsa110-hwmc/lua-scripts/'
    # Code and firmware version numbers (minimum)
    LJ_HW_VER = 1.300
    LJ_FW_VER = 1.029
    LJ_BOOT_VER = 0.940
    LUA_VER = 2.000
    # Product ID (exact match)
    LJ_PROD_ID = 7

    def print_config(self):
        """Print out the current values of the variables in this store"""
        print(f"SUBSYSTEM: {self.SUBSYSTEM}")
        print(f"APPLICATION: {self.APPLICATION}")
        print(f"LOGGING_LEVEL: {self.LOGGING_LEVEL}")
        print(f"VERSION: {self.VERSION}")
        print(f"SIM: {self.SIM}")
        print(f"VERBOSE: {self.VERBOSE}")
        print(f"ETCD_ENDPOINT: {self.ETCD_ENDPOINT}")
        print(f"LUA_DIR: {self.LUA_DIR}")
        print(f"LJ_HW_VER: {self.LJ_HW_VER}")
        print(f"LJ_FW_VER: {self.LJ_FW_VER}")
        print(f"LJ_BOOT_VER: {self.LJ_BOOT_VER}")
        print(f"LJ_PROD_ID: {self.LJ_PROD_ID}")


class Const:
    """Contains any constants required by the hwmc package"""
    MAX_ANTS = 127

    def print_config(self):
        """Print out the current values of the constants in this store"""
        print(f"MAX_ANTS: {self.MAX_ANTS}")
