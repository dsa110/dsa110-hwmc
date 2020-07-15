"""Custom formatting to DSA-110 requirements"""

import collections
import json
import logging
import logging.handlers

import astropy.time


class LogConf:
    """Useful constants for logging functions"""
    LOGGER = 'hwmc'
    LOG_SUBSYST = 'hwmc'
    LOG_DIR = '../logs'
    LOG_FILE_NAME = 'dsa_110_log_file.log'
    LOG_FILE = LOG_DIR + '/' + LOG_FILE_NAME


class CustomFormatter(logging.Formatter):
    """Logging formatter.

    This logging formatter is used to combine various pieces of information into a JSON formatted
    string as the log message.
    """

    log_msg_fmt = collections.OrderedDict([('mjd', ''),
                                           ('level', '%(levelname)s'),
                                           ('subsystem', 'HWMC'),
                                           ('app_name', '%(name)s'),
                                           ('app_ver', '0.0'),
                                           ('class', '%(class)s'),
                                           ('func_name', '%(funcName)s'),
                                           ('thread', '%(threadName)s'),
                                           ('msg', '%(message)s'),
                                           ],
                                          )

    def format(self, record):
        """Used by the logger to format the data in DSA-110 format."""
        mjd = astropy.time.Time.now().mjd
        raw_fmt = self.log_msg_fmt
        raw_fmt['mjd'] = mjd
        log_fmt = json.dumps(raw_fmt)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)
