"""Main application for monitoring and controlling DSA-110 analog hardware.

This module contains a class for setting up the monitoring system for DSA-110 analog subsystems.
These include the antenna subsystem (antenna elevation drive and monitor, FEBs; BEBs). The monitor
system is instantiated and then run. When it is run, it searches for LabJack T7 modules connected to
the network and identifies them as antenna or backend devices. For each T7, it starts a thread that
will query the monitor points and handle incoming commands.

Communication with the T7s is over Ethernet, and other communications with the array control system
are via an etcd key/value store.
"""

import inspect
import threading
import time
from threading import Thread

import dsautils.dsa_syslog as dsl

from hwmc import dsa_labjack as dlj
from hwmc.common import Config as CONF
from hwmc.utilities import vprint as vprint

# Set up module-level logging.
MODULE_NAME = __name__
LOGGER = dsl.DsaSyslogger(subsystem_name=CONF.SUBSYSTEM,
                          log_level=CONF.LOGGING_LEVEL,
                          logger_name=MODULE_NAME)
LOGGER.app(CONF.APPLICATION)
LOGGER.version(CONF.VERSION)
LOGGER.info(f"{MODULE_NAME} logger created")


class Hwmc:
    """Hardware monitor and control class to coordinate analog system via LabJack T7 modules"""

    def __init__(self):
        """Initialize the antenna and backend monitor and control system state.

        Initialize the DSA-110 hardware monitor state using the parameters in 'common.py'.
        """
        self.etcd_endpoint = CONF.ETCD_ENDPOINT
        self.sim = CONF.SIM
        self.ants = None
        self.bebs = None

        class_name = str(self.__class__)
        self.my_class = (class_name[class_name.find('.') + 1: class_name.find("'>'") - 1])
        func_name = inspect.stack()[0][3]
        LOGGER.function(func_name)
        LOGGER.info("Hwmc class initialized")

    def run(self):
        """Start all the threads required for monitor and control.

        This function starts all the threads required for the hardware monitor and control
        functionality. These are primarily the threads to run the antenna and backend box
        LabJack T7 DAQ modules.
        """
        class_name = str(self.__class__)
        self.my_class = (class_name[class_name.find('.') + 1: class_name.find("'>'") - 1])

        # Set up logging.
        func_name = inspect.stack()[0][3]
        LOGGER.function(func_name)
        if self.sim is True:
            LOGGER.warning("Running in LabJack simulation mode")
            vprint("==================\n Simulation mode!\n==================\n")
            vprint("Running in LabJack simulation mode")

        # Discover LabJack T7 devices on the network
        devices = dlj.DiscoverT7(sim=self.sim, etcd_endpoint=self.etcd_endpoint)
        self.ants = devices.get_ants()
        self.bebs = devices.get_bebs()
        num_ants = len(self.ants)
        num_bebs = len(self.bebs)

        # Start running antenna control and monitor threads
        LOGGER.function(func_name)
        if num_ants > 0:
            LOGGER.info(f"Starting {num_ants} antenna thread(s)")
            vprint(f"Starting {num_ants} antenna thread(s)")
            for ant_num, ant in self.ants.items():
                LOGGER.debug(f"Starting ant {ant_num} thread")
                ant_thread = Thread(target=ant.run, name=f'ant{ant_num}')
                ant_thread.start()
        else:
            LOGGER.warning("No antennas detected")
            vprint("No antennas detected")

        if num_bebs > 0:
            vprint(f"Starting {num_bebs} BEB thread(s)")
            LOGGER.info(f"Starting {num_bebs} BEB thread(s)")
            for beb_num, beb in self.bebs.items():
                LOGGER.debug(f"Starting BEB {beb_num} thread")
                beb_thread = Thread(target=beb.run, name=f'beb{beb_num}')
                beb_thread.start()
        else:
            LOGGER.warning("No BEBs detected")
            vprint("No BEBs detected")

        time.sleep(5)
        thread_count = threading.activeCount()
        LOGGER.info(f"{thread_count} threads started")
        vprint(f"{thread_count} threads started")

    def stop(self):
        """Send signals to stop the running LJ T7 threads"""
        func_name = inspect.stack()[0][3]
        LOGGER.function(func_name)
        LOGGER.info("Stopping antenna thread(s)")
        vprint("Stopping antenna thread(s)")
        for _, ant in self.ants.items():
            ant.stop_thread()
        LOGGER.info("Stopping BEB thread(s)")
        vprint("Stopping BEB thread(s)")
        for _, beb in self.bebs.items():
            beb.stop_thread()
