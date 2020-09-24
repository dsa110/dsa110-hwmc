#!/home/lamb/anaconda3/bin/python
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

log_priorities = {'emerg': Syslog.LOG_EMERG,
                  'alert': Syslog.LOG_ALERT,
                  'crit': Syslog.LOG_CRIT,
                  'err': Syslog.LOG_ERR,
                  'warning': Syslog.LOG_WARNING,
                  'notice': Syslog.LOG_NOTICE,
                  'info': Syslog.LOG_INFO,
                  'debug': Syslog.LOG_DEBUG,
                  }


def get_args(config_dict):
    """get_args interprets the arguments supplied on the command line for configuring HWMC"""

    parser = argparse.ArgumentParser(description="Run the DSA-110 hardware monitor and control"
                                                 "system")
    parser.add_argument('-c', '--config-file', metavar='CONFIG_FILE_NAME', type=str, required=False,
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
                        help="Run in simulation mode, which does not communicate with real"
                             "antenna monitor hardware")
    return parser.parse_args()


def read_config(config_file, config_dict):
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


def parse_args(args, config_dict):
    p = args.log_priority
    if p not in log_priorities:
        p = 'info'
    config_dict['etcd_endpoint'] = args.etcd_ip.split(':')
    config_dict['log_priority'] = log_priorities[p]
    config_dict['sim'] = args.sim
    return config_dict


def store_config(config):
    Config.SIM = config['sim']
    Config.ETCD_ENDPOINT = config['etcd_endpoint']
    Config.LOGGING_LEVEL = config['log_priority']
    Config.LUA_DIR = config['lua_dir']
    Config.LJ_HW_VER = config['lj_hw_ver']
    Config.LJ_FW_VER = config['lj_fw_ver']
    Config.LJ_BOOT_VER = config['lj_boot_ver']
    Config.LJ_PROD_ID = config['lj_prod_id']


def main():
    # Dictionary of configuration parameters for setting up hardware monitor subsystem
    hwmc_config: Dict[str, Union[bool, str, int, float]] = {'sim': False,
                                                            'etcd_endpoint': '192.168.1.132:2379',
                                                            'log_priority': log_priorities['info'],
                                                            'lua_dir': '../lua_scripts',
                                                            'lj_hw_ver': 1.300,
                                                            'lj_fw_ver': 1.092,
                                                            'lj_boot_ver': 0.94,
                                                            'lj_prod_id': 7,
                                                            }

    args = get_args(hwmc_config)
    if args.config_file is not None:
        hwmc_config = read_config(args.config_file, hwmc_config)
    else:
        hwmc_config = parse_args(args, hwmc_config)
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
