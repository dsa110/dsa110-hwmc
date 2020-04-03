#!/home/lamb/anaconda3/bin/python
"""Start the DSA-110 hardware monitor and control system.

Arguments may be supplied to control how the system is configured. Type

    ./start_hwmc.py --help

for more information.
"""
import argparse
from logging.handlers import SysLogHandler as Syslog
from time import sleep

from hwmc import hwmc
from get_yaml_config import read_yaml

# Mapping of priority values for arguments to this script to Syslog constants
log_priorities = {0: Syslog.LOG_EMERG,
                  1: Syslog.LOG_ALERT,
                  2: Syslog.LOG_CRIT,
                  3: Syslog.LOG_ERR,
                  4: Syslog.LOG_WARNING,
                  5: Syslog.LOG_NOTICE,
                  6: Syslog.LOG_INFO,
                  7: Syslog.LOG_DEBUG,
                  }

# Dictionary of configuration parameters for setting up hardware monitor subsystem
hwmc_config = {'sim': False,
               'etcd_endpoint': '192.168.1.132:2379',
               'log_priority': log_priorities[7],
               'log_file': '../logs/dsa_110_log_file.log',
               'lua_dir': '../lua_scripts',
               'lj_hw_conf_dir:': '../config',
               'lj_hw_ver': 1.300,
               'lj_fw_ver': 1.092,
               'lj_boot_ver': 0.94,
               'lj_prod_id': 7,
               }

parser = argparse.ArgumentParser(description="Run the DSA-110 hardware monitor and control"
                                             "system")
parser.add_argument('-c', '--config-file', metavar='CONFIG_FILE_NAME', type=str, required=False,
                    help="Fully qualified name of YAML configuration file. "
                    "If used, other arguments are ignored, except for '-s', '--s'")
parser.add_argument('-i', '--etcd_ip', metavar='ETCD_IP', type=str, required=False,
                    default=hwmc_config['etcd_endpoint'],
                    help="Etcd server IP address and port."
                    " Default: {}".format(hwmc_config['etcd_endpoint']))
parser.add_argument('-p', '--log-priority', metavar='LOG_PRIORITY', type=int, default=7,
                    required=False, help="Logging priority (0 to 7, default: 7)")
parser.add_argument('-lf', '--log-file', metavar='LOG_FILE', type=str, required=False,
                    default=hwmc_config['log_file'],
                    help='Base name for rotating log file')
parser.add_argument('-s', '--sim', default=False, action='store_true', required=False,
                    help="Run in simulation mode which does not communicate with real"
                    "antenna monitor hardware")

args = parser.parse_args()

if args.config_file is not None:
    yaml_fn = args.config_file
    yaml_config = read_yaml(yaml_fn)
    for item in yaml_config:
        if item == 'etcd_endpoint':
            hwmc_config[item] = yaml_config[item].split(':')
        else:
            hwmc_config[item] = yaml_config[item]
    if args.sim is True:
        hwmc_config['sim'] = True
else:
    hwmc_config = dict(etcd_endpoint=args.etcd_ip.split(':'),
                       log_priority=args.log_priority,
                       log_file=args.log_file, sim=args.sim
                       )

# Create and start in instance of the hardware monitor and control system.
HARDWARE_MC = hwmc.Hwmc(hwmc_config)
HARDWARE_MC.run()
stop_proc = False
while stop_proc is False:
    resp = input("Press 's<Enter>' to stop: ")
    if resp.lower() == 's':
        HARDWARE_MC.stop()
        sleep(5)
        stop_proc = True

print('Done\n')
