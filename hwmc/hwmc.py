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
from hwmc.common import Config as Conf

# Set up module-level logging.
MODULE_NAME = __name__
LOGGER = dsl.DsaSyslogger(Conf.SUBSYSTEM, Conf.LOGGING_LEVEL, MODULE_NAME)
LOGGER.app(Conf.APPLICATION)
LOGGER.version(Conf.VERSION)
LOGGER.info("{} logger created".format(MODULE_NAME))


class Hwmc:
    """Hardware monitor and control class to coordinate analog system via LabJack T7 modules"""

    def __init__(self):
        """Initialize the antenna and backend monitor and control system state.

        Initialize the DSA-110 hardware monitor state using the parameters in 'common.py'.
        """
        self.etcd_endpoint = Conf.etcd_endpoint
        self.sim = Conf.sim
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
            print("==================\n Simulation mode!\n==================\n")
            print("Running in LabJack simulation mode")

        # Discover LabJack T7 devices on the network
        devices = dlj.DiscoverT7(sim=self.sim, etcd_endpoint=self.etcd_endpoint)
        self.ants = devices.get_ants()
        self.bebs = devices.get_bebs()
        num_ants = len(self.ants)
        num_bebs = len(self.bebs)

        # Start running antenna control and monitor threads
        LOGGER.function(func_name)
        if num_ants > 0:
            LOGGER.info("Starting {} antenna thread(s)".format(num_ants))
            print("Starting {} antenna thread(s)".format(num_ants))
            for ant_num, ant in self.ants.items():
                LOGGER.debug("Starting ant {} thread".format(ant_num))
                ant_thread = Thread(target=ant.run, name='ant{}'.format(ant_num))
                ant_thread.start()
        else:
            LOGGER.warning("No antennas detected")
            print("No antennas detected")

        if num_bebs > 0:
            print("Starting {} BEB thread(s)".format(num_bebs))
            LOGGER.info("Starting {} BEB thread(s)".format(num_bebs))
            for beb_num, beb in self.bebs.items():
                LOGGER.debug("Starting BEB {} thread".format(beb_num))
                beb_thread = Thread(target=beb.run, name='beb{}'.format(beb_num))
                beb_thread.start()
        else:
            LOGGER.warning("No BEBs detected")
            print("No BEBs detected")

        time.sleep(5)
        thread_count = threading.activeCount()
        LOGGER.info("{} threads started".format(thread_count))
        print("{} threads started".format(thread_count))

    def stop(self):
        """Send signals to stop the running LJ T7 threads"""
        func_name = inspect.stack()[0][3]
        LOGGER.function(func_name)
        LOGGER.info("Stopping antenna thread(s)")
        print("Stopping antenna thread(s)")
        for _, ant in self.ants.items():
            ant.stop_thread()
        LOGGER.info("Stopping BEB thread(s)")
        print("Stopping BEB thread(s)")
        for _, beb in self.bebs.items():
            beb.stop_thread()
