#!/home/ubuntu/anaconda3/envs/casa/bin/python
"""Start the DSA-110 hardware monitor and control system.

Arguments may be supplied to control how the system is configured. Type

    ./start_hwmc.py --help

for more information.
"""

import argparse
from logging.handlers import SysLogHandler as Syslog
from time import sleep
from typing import Dict, Union

import dsautils.dsa_functions36 as util

from hwmc import hwmc
from hwmc.common import Config
# Mapping of priority values for arguments to this script to Syslog constants
from hwmc.hwmc import Hwmc

log_priorities: Dict[str, int] = {'emerg': int(Syslog.LOG_EMERG),
                                  'alert': int(Syslog.LOG_ALERT),
                                  'crit': int(Syslog.LOG_CRIT),
                                  'err': int(Syslog.LOG_ERR),
                                  'warning': int(Syslog.LOG_WARNING),
                                  'notice': int(Syslog.LOG_NOTICE),
                                  'info': int(Syslog.LOG_INFO),
                                  'debug': int(Syslog.LOG_DEBUG),
                                  }


def get_args(config_dict):
    """get_args interprets the arguments supplied on the command line for configuring HWMC

    Args:
        config_dict (Dict[str, Union[bool, str, int, float]]):

    Returns:
        Dict[str, Union[bool, str, int, float]]:
    """

    parser = argparse.ArgumentParser(description="Run the DSA-110 hardware monitor and control"
                                                 "system")
    parser.add_argument('-c', '--config-file', metavar='CONFIG_FILE_NAME', type=str, required=False,
                        default=None,
                        help="Fully qualified name of YAML configuration file. "
                             "If used, other arguments are ignored, except for '-s', '--s'")
    parser.add_argument('-i', '--etcd-ip', metavar='ETCD_IP', type=str, required=False,
                        default=config_dict['etcd_endpoint'],
                        help="Etcd server IP address and port."
                             " Default: {}".format(config_dict['etcd_endpoint']))
    parser.add_argument('-p', '--log-priority', metavar='LOG_PRIORITY', type=str, default=7,
                        required=False, help="Logging priority (emerg, alert, crit, err, warning, "
                                             "notice, info, debug)")
    parser.add_argument('-s', '--sim', default=False, action='store_true', required=False,
                        help="Run in simulation mode, which does not communicate with real "
                             "antenna monitor hardware")
    args = parser.parse_args()
    p = str(args.log_priority)
    if p not in log_priorities:
        p = 'info'
    config_dict['log_priority'] = log_priorities[p]
    config_dict['etcd_endpoint'] = args.etcd_ip.split(':')
    config_dict['sim'] = args.sim
    return config_dict


def read_config(config_file, config_dict):
    """Read the configuration information from a YAML file

    Configuration information for several items, such as the etcd endpoint, logging priority and
    so on, is read from a configuration file. The file name is supplied to this function,
    along with a dictionary to populate.

    Args:
        config_file (str): Fully qualified name of file to read
        config_dict (object): Dictionary of configuration parameters

    Returns:
        Dict[str, Union[bool, str, int, float]]
    """
    yaml_fn = config_file
    yaml_config = util.read_yaml(yaml_fn)
    for item in yaml_config:
        if item == 'etcd_endpoint':
            config_dict[item] = yaml_config[item].split(':')
        elif item == 'log_priority':
            p = yaml_config[item]
            if p in log_priorities:
                config_dict[item] = log_priorities[p]
            else:
                config_dict[item] = 'info'
        else:
            config_dict[item] = yaml_config[item]
    return config_dict


def store_config(config):
    """Store the supplied configuration information in a common area.

    Args:
        config (object):
    """
    Config.SIM = config['sim']
    Config.ETCD_ENDPOINT = config['etcd_endpoint']
    Config.LOGGING_LEVEL = config['log_priority']
    Config.LUA_DIR = config['lua_dir']
    Config.LJ_HW_VER = config['lj_hw_ver']
    Config.LJ_FW_VER = config['lj_fw_ver']
    Config.LJ_BOOT_VER = config['lj_boot_ver']
    Config.LJ_PROD_ID = config['lj_prod_id']


def main():
    """Set up and run the DSA-110 analog hardware monitoring and control system.

    This is the method for starting the monitoring system for the DSA-110 antennas and backends.
    It may be started with or without arguments (use '--help' to get argument description). If
    a configuration file is specified in the arguments, that is used to determine the
    configuration parameters. If no configuration file is specified, any arguments supplied will
    override the default arguments.
    """
    # Dictionary of configuration parameters for setting up hardware monitor subsystem
    hwmc_config: Dict[str, Union[bool, str, int, float]] = {'sim': False,
                                                            'etcd_endpoint': '192.168.1.132:2379',
                                                            'log_priority': log_priorities['info'],
                                                            'lua_dir': '../lua_scripts',
                                                            'lj_hw_ver': 1.300,
                                                            'lj_fw_ver': 1.092,
                                                            'lj_boot_ver': 0.94,
                                                            'lj_prod_id': 7,
                                                            'config_file': None,
                                                            }

    hwmc_config = get_args(hwmc_config)
    if hwmc_config['config_file'] is not None:
        hwmc_config = read_config(hwmc_config['config_file'], hwmc_config)
    store_config(hwmc_config)

    # Create and start in instance of the hardware monitor and control system.
    hardware_mc: Hwmc = hwmc.Hwmc()
    hardware_mc.run()
    stop_proc = False

    while stop_proc is False:
        resp = input("Press 's' to stop: ")
        if resp.lower() == 's':
            hardware_mc.stop()
            sleep(5)
            stop_proc = True
    print('Done\n')


if __name__ == '__main__':
    main()
