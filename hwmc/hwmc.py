"""Main application for monitoring and controlling DSA-110 analog hardware.

This application searches for LabJack T7 modules connected to the network and identifies them as
antenna or backend devices. It starts a thread for each T7 to query for the monitor points and
handle commands. This module also sets up the monitor point queue and server, as well as
instantiating the parent logger.
"""

import logging
import logging.handlers
import threading
import time
from threading import Thread

from hwmc import dsa_labjack as dlj
from hwmc.hwmc_logging import CustomFormatter
from hwmc.hwmc_logging import LogConf as Conf


class Hwmc:
    """Hardware monitor and control class to coordinate analog system via LabJack T7 modules"""

    def __init__(self, config):
        """Initialize the antenna and backend monitor and control system state.

        Initialize the DSA-110 hardware monitor state using the parameters in the supplied argument.

        Args:
            """

        class_name = str(self.__class__)
        self.my_class = (class_name[class_name.find('.') + 1: class_name.find("'>'") - 1])
        self.etcd_endpoint = config['etcd_endpoint']
        self.sim = config['sim']
        self.log_file = config['log_file']
        self.log_priority = config['log_priority']
        self.ants = None
        self.bebs = None

    def run(self):
        """Start all the threads required for monitor and control.

        This function starts all the threads required for the hardware monitor and control
        functionality. These are primarily the threads to run the antenna and backend box
        LabJack DAQ modules.
        """
        class_name = str(self.__class__)
        self.my_class = (class_name[class_name.find('.') + 1: class_name.find("'>'") - 1])

        if self.sim is True:
            print("==================\n Simulation mode!\n==================\n")

        # Set up logging. Loggers in other modules should be children of this.
        logger = logging.getLogger(Conf.LOGGER)
        logger.setLevel(self.log_priority)

        # Create the file handler (later to be a syslog handler).
        file_handler = logging.handlers.RotatingFileHandler(self.log_file, maxBytes=1000000,
                                                            backupCount=10000)
        file_handler.setLevel(logging.DEBUG)
        # Create formatter and add it to the handlers.
        file_handler.setFormatter(CustomFormatter())
        logger.addHandler(file_handler)
        syslog_handler = logging.handlers.SysLogHandler()
        logger.addHandler(syslog_handler)
        CustomFormatter.log_msg_fmt['class'] = self.my_class
        logger.info("Main logger created")

        # Discover LabJack T7 devices on the network
        devices = dlj.DiscoverT7(sim=self.sim, etcd_endpoint=self.etcd_endpoint)
        self.ants = devices.get_ants()
        self.bebs = devices.get_bebs()

        # Start running antenna control and monitor threads
        print("Starting antenna threads")
        for ant_num, ant in self.ants.items():
            ant_thread = Thread(target=ant.run, name='Ant-{}'.format(ant_num))
            ant_thread.start()

        print("Starting BEB threads")
        for beb_num, beb in self.bebs.items():
            beb_thread = Thread(target=beb.run, name='BEB-{}'.format(beb_num))
            beb_thread.start()

        time.sleep(5)
        thread_count = threading.activeCount()
        print("{} threads started".format(thread_count))

    def stop(self):
        """Send signals to stop the running LJ T7 threads"""
        for _, ant in self.ants.items():
            ant.stop_thread()
        for _, beb in self.bebs.items():
            beb.stop_thread()
