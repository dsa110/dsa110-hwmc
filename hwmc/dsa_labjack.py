"""Handle all the communications between the control system and the LabJack T7 modules.

   This class provides wrappers for the calls to the LabJack device driver calls specifically
   tailored to the DSA-110 hardware configuration and requirements.

    This module has four classes:

        DiscoverT7:
            Discovers for all the LabJack T7 modules on the network and determines whether
            they are antenna or back-end modules.

        DsaAntLabJack:
            Handles the communications with the antenna Y7 modules (one per antenna).

        DsaBebLabJack:
            Handles the back-end box T7s (each handling multiple antennas).

        Constants:
            Collection of constants that define the configuration. These are values that
            should not change often, and are integral enough to be hard-coded.

    Examples:
        device_list = dsa_labjack.Discover(['localhost', '2379'])
        for ant_num, ant in device_list.ants: ant.run()
    """

import inspect
import json
import time

import dsautils.dsa_syslog as dsl
import etcd3 as etcd
from astropy.time import Time
from dsautils import dsa_constants as Const
from labjack import ljm

import hwmc.lua_script_utilities as lua
from hwmc import lj_startup as sf
from hwmc.common import Config as CONF
from hwmc.utilities import vprint as vprint
from hwmc.write_config import write_config_to_flash

# Set up module-level logging.
MODULE_NAME = __name__
LOGGER = dsl.DsaSyslogger(subsystem_name=CONF.SUBSYSTEM,
                          log_level=CONF.LOGGING_LEVEL,
                          logger_name=MODULE_NAME)
LOGGER.app(CONF.APPLICATION)
LOGGER.version(CONF.VERSION)
LOGGER.function('None')
LOGGER.info(f"{MODULE_NAME} logger created")


# -------------- LabJack T7 initialization class ------------------
class DiscoverT7:
    """Handles searching and identification for all LabJack T7 modules on the network.

    This class provides functionality for searching for LabJack T7 data acquisition devices on the
    network. When devices are discovered, their ID is queried to find out whether they are antenna
    (ant), or back-end box (beb) modules, and which instance they are."""

    def __init__(self, etcd_endpoint: list, sim=False):
        """Discover Model T7 LabJack devices on network and return their information

        Searches on the network for any LabJack T7 devices, and queries them for their DHCP-assigned
        IP address. The devices are queried for their hardware identifier (DIP switch on to the
        LabJack interface board) to determine if they are for an antenna (ant) or analog back-end
        box (BEB), as well as the associated number. For the antennas, this is the antenna number.
        Each BEB device is associated with multiple antennas.

        Args:
            etcd_endpoint (:obj:'list' of 'str'): A list with the etcd IP address and port number
            sim (bool): Indicates if simulated (True) or real (False) data

        Raises:
            ljm.LJMError: An error occurred accessing the LabJack drivers.

        """

        # Get the name of this for logging purposes.
        my_class = str(self.__class__)
        self.class_name = (my_class[my_class.find('.') + 1: my_class.find("'>'") - 1])

        # Set up logging.
        func = inspect.stack()[0][3]
        func_name = f"{self.class_name}::{func}"
        LOGGER.function(func_name)
        LOGGER.info("Searching for LabJack T7s")

        # Set up arrays to hold device information for discovered LabJack devices.
        self.num_ant = 0
        self.num_beb = 0
        self.ants = {}
        self.bebs = {}

        if sim:
            a_connection_types, a_device_types, a_serial_numbers = self._create_sim_devices()
            for i in range(len(a_device_types)):
                vprint(f"Device type: {a_device_types[i]}, connection type: {a_connection_types[i]},"
                       f" serial number: {a_serial_numbers[i]}")
        else:
            a_device_types, a_connection_types, a_serial_numbers = self._find_devices()
            for i in range(len(a_device_types)):
                vprint(f"Device type: {a_device_types[i]}, connection type: {a_connection_types[i]},"
                       f" serial number: {a_serial_numbers[i]}")
        if self.num_found > 0:
            sim_ant_num = 1
            sim_beb_num = 1
            for i in range(self.num_found):
                lj_handle = None
                try:
                    lj_handle = ljm.open(a_device_types[i], a_connection_types[i],
                                         a_serial_numbers[i])
                except ljm.LJMError:
                    self.num_found -= self.num_found
                    if self.num_found <= 0:
                        return

                if sim:
                    if i % 2 == 0:
                        (lj_type, lj_location) = (Constants.ANT_TYPE, sim_ant_num)
                        sim_ant_num += 1
                    else:
                        (lj_type, lj_location) = (Constants.BEB_TYPE, sim_beb_num)
                        sim_beb_num += 10
                else:
                    (lj_type, lj_location) = self._get_type_and_location(lj_handle)
                if lj_type == Constants.ANT_TYPE:
                    self.ants[lj_location] = DsaAntLabJack(lj_handle, lj_location,
                                                           etcd_endpoint, sim)
                    self.num_ant += 1
                    LOGGER.info(f"Antenna {lj_location} found")
                    vprint(f"Antenna {lj_location} found")
                elif lj_type == Constants.BEB_TYPE:
                    self.bebs[lj_location] = DsaBebLabJack(lj_handle, lj_location, etcd_endpoint)
                    self.num_beb += 1
                    LOGGER.info(f"BEB {lj_location} found")
                    vprint(f"Analog backend {lj_location} found")

    def _create_sim_devices(self):
        """Create simulated LJ T7 interfaces.

        In simulate mode, connect to the LJ drivers in demo mode. Fake out some of the data.
        This does not simulate any realistic hardware responses.
        """
        a_device_types = []
        a_connection_types = []
        a_serial_numbers = []
        a_ip_addresses = []
        self.num_found = 2 * Constants.NUM_SIM
        for i in range(self.num_found):
            a_device_types.append(ljm.constants.dtT7)
            a_connection_types.append(ljm.constants.ctETHERNET)
            a_serial_numbers.append("-2")
            a_ip_addresses.append(f"192.168.1.{i}")
        return a_connection_types, a_device_types, a_serial_numbers

    def _find_devices(self):
        """Search the network for LJ T& modules.

        In non-simulate mode check to see if LabJacks can be detected. Log and raise error if
        there is a problem.
        """
        func = inspect.stack()[0][3]
        func_name = f"{self.class_name}::{func}"
        try:
            self.num_found, a_device_types, a_connection_types, a_serial_numbers, _ = \
                ljm.listAll(ljm.constants.dtT7, ljm.constants.ctETHERNET)

        except ljm.LJMError as err:
            LOGGER.function(func_name)
            LOGGER.critical(f"Error searching for LabJack devices. LJMError: {err}")
            raise ljm.LJMError
        return a_device_types, a_connection_types, a_serial_numbers

    def _get_type_and_location(self, lj_handle):
        """Decode LJ type and number

        Take the byte corresponding to the DIP switch (antennas), or hard-wiring (BEBs) and split it
        into the type and number. The type is encoded in the upper bit; 0: antenna,
        1: analog backend. The lower seven bits give the antenna number for antenna LabJack T7s,
        and the antenna group (first antenna of group of ten) for the analog backends.

        Arguments:
            lj_handle (object): Handle for the LabJack communications

        Returns:
            lj_type (int): Constants.NULL_TYPE (undefined type) or constants.ANT_TYPE, or
            constants.BEB_TYPE
            location (int): antenna number for antenna type, or first of 10 antennas if BEB type
        """

        func = inspect.stack()[0][3]
        func_name = f"{self.class_name}::{func}"
        try:
            addr_bits = int(ljm.eReadName(lj_handle, Constants.ID_WORD))
            if addr_bits < 128:
                lj_type = Constants.ANT_TYPE
            else:
                lj_type = Constants.BEB_TYPE
            location = int(addr_bits & 0x7f)
        except ljm.LJMError as err:
            LOGGER.function(func_name)
            LOGGER.error(f"Error reading LabJack. LJMError: {err}")
            lj_type = Constants.NULL_TYPE
            location = 0
        return lj_type, location

    def get_ants(self):
        """Return a list of antenna objects corresponding to discovered LJ T7s.

        Returns:
            A list of objects of type 'ant'
        """
        return self.ants

    def get_bebs(self):
        """Return a list of BEB objects corresponding to discovered LJ T7s.

        Returns:
            A list of objects of type 'ant'
        """
        return self.bebs


# -------------- LabJack antenna class ------------------

class DsaAntLabJack:
    """Class handles communications with LabJack T7s located at antennas.

    Functions are provided in this class for initializing an antenna object and running it. The
    antenna object handles polling the antenna monitor points and publishing them to the etcd
    server, receiving commands from the etcd server and sending them to the antenna.
    """

    NUM_FRAMES = 5
    A_NAMES = ('AIN0', 'TEMPERATURE_DEVICE_K', 'DIO_STATE', 'USER_RAM1_F32', 'USER_RAM1_U16')
    A_WRITES = (0, 0, 0, 0, 0)
    A_NUM_VALS = (14, 1, 1, 10, 2)
    LEN_VALS = sum(A_NUM_VALS)

    DRIVE_STATE = {0: ' Off', 1: 'North', 2: 'South', 3: ' Bad'}
    BRAKE_STATE = {0: ' On', 1: 'Off'}
    LIMIT_STATE = {0: ' On', 1: 'Off'}

    def __init__(self, lj_handle, ant_num, etcd_endpoint, sim=False):
        """Initialize an instance of an antenna object.

        Initializes several attributes of the antenna object, such as the etcd connection
        information, the monitor point dictionary, and the command list.

        Args:
            lj_handle (int): A handle to the LabJack module to be used by this antenna instance
            ant_num (int): The antenna number to be handled by this instance. Should be unique.
            etcd_endpoint (:obj:'list' of :obj:'str): A list of the IP address/hostname, and
            port for the etcd key/value store.

        """
        self.valid = False
        # Set up class-level logging (per class instance).
        my_class = str(self.__class__)
        self.class_name = (my_class[my_class.find('.') + 1: my_class.find("'>'") - 1])
        func = inspect.stack()[0][3]
        func_name = f"{self.class_name}::ant{ant_num}.{func}"
        logger_name = f'{MODULE_NAME}_Ant{ant_num}'
        self.logger = dsl.DsaSyslogger(subsystem_name=CONF.SUBSYSTEM,
                                       log_level=CONF.LOGGING_LEVEL,
                                       logger_name=logger_name)
        self.logger.app(CONF.APPLICATION)
        self.logger.version(CONF.VERSION)
        self.logger.function(func_name)
        self.logger.info(f"{logger_name} logger created")
        self.logger.info("Initializing")
        self.logger.info(f"Antenna {ant_num} connected")

        self.sim = sim
        self.stop = False
        self.lj_handle = lj_handle
        self.ant_num = ant_num

        self.etcd_mon_key = f'/mon/ant/{ant_num:d}'
        self.etcd_cmd_key = f'/cmd/ant/{ant_num:d}'
        self.etcd_cal_key = f'/cal/ant/{ant_num:d}'
        self.etcd_cmd_all_key = '/cmd/ant/0'
        self.etcd_client = etcd.client(host=etcd_endpoint[0], port=etcd_endpoint[1])
        vprint(f"Etcd client: {etcd_endpoint[0]}\nPort :{etcd_endpoint[1]}")
        self.etcd_valid = True
        self.cmd_watch_id = None
        self.cmd_all_watch_id = None
        # Install callback function to handle commands
        try:
            self.cmd_watch_id = self.etcd_client.add_watch_callback(self.etcd_cmd_key,
                                                                    self.cmd_callback)
            self.cmd_all_watch_id = self.etcd_client.add_watch_callback(self.etcd_cmd_all_key,
                                                                        self.cmd_callback)
            self.etcd_valid = True
            self.logger.info("Etcd command watchers installed")
        except etcd.exceptions.ConnectionFailedError:
            self.logger.critical("Unable to connect to etcd store")
            self.etcd_valid = False
        self.move_cmd = None
        # Install callback function to handle new calibration parameters
        self.cal_watch_id = None
        try:
            self.cal_watch_id = self.etcd_client.add_watch_callback(self.etcd_cal_key,
                                                                    self.cal_callback)
            self.etcd_valid = True
            self.logger.info("Connected to etcd store")
        except etcd.exceptions.ConnectionFailedError:
            self.logger.critical("Etcd cal watcher installed")
            self.etcd_valid = False
        self.move_cmd = None
        self.monitor_points = {'sim': self.sim,
                               'ant_num': ant_num,
                               'time': 0.0,
                               'ant_el': 0.0,
                               'ant_cmd_el': 0.0,
                               'ant_el_err': 0.0,
                               'ant_el_raw': 0.0,
                               'drv_cmd': 0,
                               'drv_act': 0,
                               'drv_state': 0,
                               'at_north_lim': False,
                               'at_south_lim': False,
                               'brake_on': False,
                               'motor_temp': -273.15,
                               'focus_temp': -273.15,
                               'lna_current_a': 0.0,
                               'lna_current_b': 0.0,
                               'noise_a_on': 0,
                               'noise_b_on': 0,
                               'rf_pwr_a': -100.0,
                               'rf_pwr_b': -100.0,
                               'feb_current_a': 0.0,
                               'feb_current_b': 0.0,
                               'laser_volts_a': 0.0,
                               'laser_volts_b': 0.0,
                               'feb_temp_a': -273.15,
                               'feb_temp_b': -273.15,
                               'psu_volt': 0.0,
                               'lj_temp': 0.0,
                               'v_scale': 999.0,
                               'v_off': 999.0,
                               'ang_off': 999.0,
                               'a_off': 999.0,
                               'collim': 999.0,
                               'v_psu_avg': 999.0,
                               'fan_err': 0,
                               'emergency_off': False,
                               }
        self.lj_ant_cmds = {'noise_a_on': self.switch_noise_a,
                            'noise_b_on': self.switch_noise_b,
                            'move': self._move_ang,
                            'halt': self._halt,
                            'script': self.load_script,
                            }

        # Initialize LabJack settings and report status to control system.
        self.valid = True
        startup_mp = self._init_ant_labjack()
        if startup_mp:
            self.send_to_etcd(self.etcd_mon_key, startup_mp)

    def _init_ant_labjack(self):
        """Initialize the LabJack T7 hardware.

        This function queries the antenna LabJack to get information about its hardware and
        software versions and states. It sets the range for the analog inputs, and the states of
        the digital IO (i.e., for each bit, input, output or tri-state). This is a safety measure,
        since these should be set in the power-up hardware defaults, and then also by the Lua
        script that should run on start-up.

        Returns:
            startup_mp (:obj:'dict'): A monitor point dictionary of values queried from the
            LabJack T7 on start up.
        """

        func = self.ant_num, inspect.stack()[0][3]
        func_name = f"{self.class_name}::{self.ant_num}.{func}"
        self.logger.function(func_name)
        self.logger.info("Initializing antenna")
        vprint(f"Initializing antenna {self.ant_num}")

        # Digital section
        # Input register for LabJack ID
        ljm.eWriteName(self.lj_handle, "FIO_DIRECTION", 0b00000000)
        # Output register for drive motor control
        ljm.eWriteName(self.lj_handle, "EIO_DIRECTION", 0b00011110)
        # Input register for drive status
        ljm.eWriteName(self.lj_handle, "CIO_DIRECTION", 0b00000000)
        # Input/output for noise source and fan
        ljm.eWriteName(self.lj_handle, "MIO_DIRECTION", 0b00000000)

        # Analog section
        # Input voltage range
        ljm.eWriteName(self.lj_handle, "AIN_ALL_RANGE", 10.0)

        # Query LabJack for its current configuration.
        startup_mp = sf.t7_startup_check(self.lj_handle, lua_required=True, ant_num=self.ant_num)

        # Check for inclinometer calibration constants.
        self._check_cal()

        return startup_mp

    def __del__(self):
        if self.valid is True:
            ljm.close(self.lj_handle)

    def _check_cal(self):
        func = self.ant_num, inspect.stack()[0][3]
        func_name = f"{self.class_name}::ant{self.ant_num}.{func}"
        if self.etcd_valid:
            val = self.etcd_client.get(self.etcd_cal_key)
            if val[0] is not None:
                j_pkt = val[0].decode('utf-8')
                cal_info = json.loads(j_pkt)
                cal_table = cal_info['cal_table']
                write_config_to_flash(self.lj_handle, self.ant_num, cal_table)
            else:
                self.logger.function(func_name)
                self.logger.error(f"Unable to get inclinometer cal for Ant{self.ant_num}")

    def _execute_cal(self, cal_info):
        func = self.ant_num, inspect.stack()[0][3]
        func_name = f"{self.class_name}::ant{self.ant_num}.{func}"
        self.logger.function(func_name)
        if self.etcd_valid:
            vprint(f"cal_info: {cal_info}")
            cal_table = cal_info['cal_table']
            write_config_to_flash(self.lj_handle, self.ant_num, cal_table)
            self.logger.info(f"Updating inclinometer cal for Ant{self.ant_num}")
        else:
            self.logger.error(f"Unable to get inclinometer cal for Ant{self.ant_num}")

    def load_script(self, script_name):
        """Load a specified Lua script into the LabJack

        This will load a script into the current LabJack, store it in the flash memory, configure
        the LabJack to run the script on start up, and start the script.

        Args:
            script_name (str): Fully qualified name of Lua script to load
        """

        func = self.ant_num, inspect.stack()[0][3]
        func_name = f"{self.class_name}::ant{self.ant_num}.{func}"
        self.logger.function(func_name)
        script = lua.LuaScriptUtilities(script_name, self.lj_handle)
        if script.err is False:
            script.load(compress = True)
            self.logger.info("Saving script to flash")
            time.sleep(1.0)
            script.save_to_flash()
            time.sleep(1.0)
            self.logger.info("Configuring to run on startup")
            script.run_on_startup()
            time.sleep(1.0)
            self.logger.info("Starting script")
            if script.run(debug=False) is True:
                self.logger.info("Script started OK")
            else:
                self.logger.info("Failed to start script")
        else:
            self.logger.info(f"Script {script_name} not found")
            vprint(f"Script '{script_name}' not found")

    def _get_data(self):
        """Read data from LJ T7 and insert into monitor point dictionary.

        Values are read from the current LabJack T7 in a single operation through the ljm driver.
        These are converted into the appropriate data types in the relevant units and put in the
        one-second cadence monitor point dictionary.
        """
        a_values = [0] * self.LEN_VALS
        a_values = ljm.eNames(self.lj_handle, self.NUM_FRAMES, self.A_NAMES, self.A_WRITES,
                              self.A_NUM_VALS, a_values)
        time_stamp = float(f"{Time.now().mjd:.8f}")
        self.monitor_points['time'] = float(time_stamp)
        self.monitor_points['ant_el'] = a_values[17]
        self.monitor_points['ant_cmd_el'] = a_values[16]
        self.monitor_points['ant_el_err'] = a_values[18]
        self.monitor_points['focus_temp'] = 100 * a_values[0] - 50
        self.monitor_points['motor_temp'] = 100 * a_values[1] - 50
        self.monitor_points['laser_volts_a'] = a_values[2]
        self.monitor_points['rf_pwr_a'] = 28.571 * a_values[3] - 90
        self.monitor_points['feb_current_a'] = 1000 * a_values[4]
        self.monitor_points['lna_current_a'] = 100 * a_values[5]
        self.monitor_points['feb_temp_a'] = 100 * a_values[6] - 50
        self.monitor_points['lna_current_b'] = 100 * a_values[7]
        self.monitor_points['rf_pwr_b'] = 28.571 * a_values[8] - 90
        self.monitor_points['laser_volts_b'] = a_values[9]
        self.monitor_points['feb_current_b'] = 1000 * a_values[10]
        self.monitor_points['feb_temp_b'] = 100 * a_values[11] - 50
        self.monitor_points['psu_volt'] = a_values[12]
        self.monitor_points['ant_el_raw'] = a_values[19]
        self.monitor_points['lj_temp'] = a_values[14] + Const.ABS_ZERO
        self.monitor_points['v_scale'] = a_values[20]
        self.monitor_points['v_off'] = a_values[21]
        self.monitor_points['ang_off'] = a_values[22]
        self.monitor_points['a_off'] = a_values[23]
        self.monitor_points['collim'] = a_values[24]
        self.monitor_points['v_psu_avg'] = a_values[25]
        self.monitor_points['lj_temp'] = a_values[14] + Const.ABS_ZERO
        dig_val = int(a_values[15])
        self.monitor_points['emergency_off'] = bool((dig_val >> 8) & 0b01)
        self.monitor_points['drv_cmd'] = (dig_val >> 9) & 0b11
        self.monitor_points['drv_act'] = (dig_val >> 14) & 0b11
        self.monitor_points['drv_state'] = int(a_values[26])
        self.monitor_points['brake_on'] = bool(1 - ((dig_val >> 13) & 0b01))
        self.monitor_points['at_north_lim'] = bool(1 - ((dig_val >> 20) & 0b01))
        self.monitor_points['at_south_lim'] = bool(1 - ((dig_val >> 21) & 0b01))
        self.monitor_points['fan_err'] = bool((dig_val >> 22) & 0b01)
        self.monitor_points['noise_a_on'] = bool(1 - ((dig_val >> 11) & 0b01))
        self.monitor_points['noise_b_on'] = bool(1 - ((dig_val >> 12) & 0b01))
        return self.monitor_points

    def execute_cmd(self, cmd):
        """Take the command from etcd and call the appropriate function to execute it.

        Args:
            cmd (:obj:'dict' of 'str':'bool' or 'str' or 'float'): Command far antenna system to
            execute, along with any argument required.
        """
        func = self.ant_num, inspect.stack()[0][3]
        func_name = f"{self.class_name}::ant{self.ant_num}.{func}"
        cmd_name = cmd['cmd']
        cmd_name = cmd_name.lower()
        if cmd_name in self.lj_ant_cmds:
            self.logger.function(func_name)
            if len(cmd) > 1:
                args = cmd['val']
                if isinstance(args, str):
                    args = args.lower()
                self.lj_ant_cmds[cmd_name](args)
                self.logger.info(f"Executing command '{cmd_name}' with argument '{args}'")
            else:
                self.lj_ant_cmds[cmd_name]()
                self.logger.info(f"Executing command '{cmd_name}'")
        else:
            self.logger.error(f"Unknown command received : '{cmd_name}'")

    def cmd_callback(self, event):
        """Etcd watch callback function. Called when values of watched keys are updated.

        Args:
            event (:obj:): Etcd event containing the key and value.
        """
        value = event.events[0].value.decode('utf-8')
        cmd_d = json.loads(value)
        self.execute_cmd(cmd_d)

    def cal_callback(self, event):
        """Etcd watch callback function. Called when values of watched keys are updated.

        Args:
            event (:obj:): Etcd event containing the key and value.
        """
        value = event.events[0].value.decode('utf-8')
        cal_info = json.loads(value)
        self._execute_cal(cal_info)

    def get_cal_from_etcd(self):
        if self.etcd_valid:
            key = f'/cal/ant/{self.ant_num}'
            vprint(f"Getting key: {key}")
            raw = self.etcd_client.get(key)[0]
            if raw is None:
                vprint("No key found")
            else:
                val = raw.decode('ascii')
                mps = json.loads(val)
                cal_info = mps['cal_table']
                vprint(f"Cal table: {cal_info}")
                self._execute_cal(cal_info)

    def send_to_etcd(self, key, mon_data):
        """Convert a monitor point dictionary to JSON and send to etdc key/value store."""
        if self.etcd_valid:
            j_pkt = json.dumps(mon_data)
            result = self.etcd_client.put(key, j_pkt)

    def run(self):
        """Run the communication code for the antenna LJ T7.

        This function should be run in a thread for this antenna instance."""

        func = inspect.stack()[0][3]
        func_name = f"{self.class_name}::ant{self.ant_num}.{func}"
        self.logger.function(func_name)
        self.logger.debug(f"Running antenna {self.ant_num} thread")
        # Run data query loop until stop flag set
        while not self.stop:
            mon_data = self._get_data()
            self.send_to_etcd(self.etcd_mon_key, mon_data)

            t_now = time.time()
            next_time = (int(t_now / Constants.POLLING_INTERVAL) + 1) * Constants.POLLING_INTERVAL
            sleep_time = next_time - time.time()
            if sleep_time > 0.0:
                time.sleep(sleep_time)
        self.logger.function(func_name)
        self.logger.info(f"Antenna {self.ant_num} disconnecting")
        vprint(f"Antenna {self.ant_num} disconnecting")
        if self.etcd_valid:
            self.logger.info(f"Antenna {self.ant_num} closing etcd connection")
            vprint(f"Antenna {self.ant_num} closing etcd connection")
            if self.cmd_watch_id is not None:
                self.etcd_client.cancel_watch(self.cmd_watch_id)
                self.logger.info(f"Antenna {self.ant_num}: terminating cmd callback")
                vprint(f"Antenna {self.ant_num}: terminating cmd callback")
            if self.cmd_all_watch_id is not None:
                self.etcd_client.cancel_watch(self.cmd_all_watch_id)
                self.logger.info(f"Antenna {self.ant_num}: terminating cmd all callback")
                vprint(f"Antenna {self.ant_num}: terminating cmd all callback")
            if self.cal_watch_id is not None:
                self.etcd_client.cancel_watch(self.cal_watch_id)
                self.logger.info(f"Antenna {self.ant_num}: terminating cal callback")
                vprint(f"Antenna {self.ant_num}: terminating cal callback")
            self.etcd_client.close()
            self.logger.info(f"Antenna {self.ant_num}: terminating etcd client")
            vprint(f"Antenna {self.ant_num}: terminating etcd client")

        time.sleep(1)

    def switch_noise_a(self, state):
        """Turn noise source A on or off"""
        pol = 'a'
        self.switch_noise(pol, state)

    def switch_noise_b(self, state):
        """Turn noise source B on or off"""
        pol = 'b'
        self.switch_noise(pol, state)

    def switch_noise(self, pol, state):
        """Set the bit in the LJ T7 to turn the specified noise source on or off.

        Args:
            pol (str): 'a' or 'b' according to the requested polarization.
            state (str): 'on' or 'off'
        """
        func = inspect.stack()[0][3]
        func_name = f"{self.class_name}::ant{self.ant_num}.{func}"
        if state is False:
            state_val = 1
        elif state is True:
            state_val = 0
        else:
            msg = f"Ant {self.ant_num}: Invalid noise diode state requested: {state}"
            self.logger.function(func_name)
            self.logger.error(msg)
            return
        if pol == 'a':
            msg = f"Ant {self.ant_num}: Turning polarization A noise diode {state}"
            self.logger.function(func_name)
            self.logger.info(msg)
            ljm.eWriteName(self.lj_handle, Constants.NOISE_A, state_val)
        elif pol == 'b':
            msg = f"Ant {self.ant_num}: Turning polarization B noise diode {state}"
            self.logger.function(func_name)
            self.logger.info(msg)
            ljm.eWriteName(self.lj_handle, Constants.NOISE_B, state_val)
        else:
            msg = f"Ant {self.ant_num}: Invalid noise diode state requested: {pol}"
            self.logger.function(func_name)
            self.logger.error(msg)

    def _motor_cmd(self, cmd, arg=0):
        """Set a flag register ad position register in the antenna LJ T7 to execute a motion.

        A command register in the LJ is set to move or halt the antenna elevation drive. If the
        command is to move, as opposed to halt, the position register for the target elevation is
        set first so the value is present when the move flag is set.

        Args:
            cmd (str): 'halt' or 'move'
            arg (float): Target elevation in degrees. Required only with 'move'
        """
        cmd_list = {'halt': 1,
                    'move': 2,
                    }
        if cmd == 'move' and arg is not None:
            ljm.eWriteName(self.lj_handle, 'USER_RAM1_F32', float(arg))
            ljm.eWriteName(self.lj_handle, 'USER_RAM0_U16', cmd_list[cmd])
        elif cmd == 'halt':
            ljm.eWriteName(self.lj_handle, 'USER_RAM0_U16', cmd_list[cmd])

    def _halt(self, _):
        """Stop any elevation movement immediately.

        Logs the command and calls the low-level function to control the motor.
        """
        func = inspect.stack()[0][3]
        func_name = f"{self.class_name}::ant{self.ant_num}.{func}"
        msg = f"Ant {self.ant_num}: Stopping antenna"
        self.logger.function(func_name)
        self.logger.info(msg)
        self._motor_cmd('halt')

    def _move_ang(self, pos):
        """Move the antenna to a specified elevation angle.

        Logs the command and calls the low-level function to control the motor.

        Args:
            pos (float): Target elevation for antenna move command.
        """
        func = inspect.stack()[0][3]
        func_name = f"{self.class_name}::ant{self.ant_num}.{func}"

        pos = _validate_num(pos)
        if pos is not None:
            msg = f"Ant {self.ant_num}: Moving to {pos: .2f}"
            self.logger.function(func_name)
            self.logger.info(msg)
            self._motor_cmd('move', pos)

    def stop_thread(self):
        """Set a flag to terminate the thread this object is run in."""
        func = inspect.stack()[0][3]
        func_name = f"{self.class_name}::beb{self.ant_num}.{func}"
        self.logger.function(func_name)
        self.logger.info(f"Stopping Ant {self.ant_num}")
        vprint(f"Stopping Ant {self.ant_num}")
        self.stop = True


def _validate_num(val):
    if isinstance(val, str):
        try:
            val = float(val)
            return val
        except ValueError:
            return None
    elif isinstance(val, float):
        return val
    elif isinstance(val, int):
        return float(val)
    return None


# -------------- LabJack analog backend class ------------------

class DsaBebLabJack:
    """Class handles communications with LabJack T7s monitoring the backend boxes.

    Functions are provided in this class for initializing an antenna object and running it. The
    antenna object handles polling the antenna monitor points and publishing them to the etcd
    server..
    """
    BEB_PER_LJ = 10

    def __init__(self, lj_handle, beb_num, etcd_endpoint):
        """Initialize an instance of a backend monitor object."""
        # Set up class-level logging (per class instance).
        self.valid = False
        module_name = __name__
        my_class = str(self.__class__)
        self.class_name = (my_class[my_class.find('.') + 1: my_class.find("'>'") - 1])
        func = inspect.stack()[0][3]
        func_name = "{self.class_name}::beb{beb_num}.{func}"
        logger_name = f'{module_name}_BEB{beb_num}'
        self.logger = dsl.DsaSyslogger(subsystem_name=CONF.SUBSYSTEM,
                                       log_level=CONF.LOGGING_LEVEL,
                                       logger_name=logger_name)
        self.logger.app(CONF.APPLICATION)
        self.logger.version(CONF.VERSION)
        self.logger.function(func_name)
        self.logger.info(f"{logger_name} logger created")
        self.stop = False
        self.lj_handle = lj_handle
        self.etcd_mon_key = []
        self.etcd_cnf_key = []
        self.beb_num = beb_num
        self.etcd_valid = False
        for i in range(self.BEB_PER_LJ):
            self.etcd_mon_key.append(f'/mon/beb/{beb_num + i:d}')
        self.etcd_client = etcd.client(host=etcd_endpoint[0], port=etcd_endpoint[1])
        try:
            self.etcd_client.status()
            self.etcd_valid = True
            self.logger.info(f"BEB {beb_num} connected to Etcd store")
        except etcd.exceptions.ConnectionFailedError:
            self.logger.info(f"BEB {beb_num} cannot connect to Etcd store")
            self.etcd_valid = False
        self.valid = False

        self.monitor_points = list()
        for i in range(self.BEB_PER_LJ):
            self.monitor_points.append(
                {'ant_num': beb_num + i,
                 'time': 0,
                 'pd_current_a': 0.0,
                 'beb_current_a': 0.0,
                 'if_pwr_a': 0.0,
                 'pd_current_b': 0.0,
                 'beb_current_b': 0.0,
                 'if_pwr_b': 0.0,
                 'lo_mon': 0.0,
                 'beb_temp': 0.0,
                 'psu_voltage': 0.0,
                 'psu_current': 0.0,
                 'lj_temp': 0.0,
                 }
            )
        # Initialize LabJack settings
        self.valid = True
        startup_mps = self._init_beb_labjack()
        self.send_to_etcd(self.etcd_mon_key[0], startup_mps)

    def _init_beb_labjack(self):
        """Check the configuration of the LJ T7 and set analog ranges.

        Returns:
            :obj:'dict': Dictionary of monitor points containing LJ T7 startup information.
        """
        func = inspect.stack()[0][3]
        func_name = f"{self.class_name}::beb{self.beb_num}.{func}"
        self.logger.function(func_name)
        self.logger.info(f"Initializing BEB {self.beb_num}")
        vprint(f"Initializing BEB {self.beb_num}")
        startup_mp = sf.t7_startup_check(self.lj_handle, lua_required=False, ant_num=self.beb_num)
        # Analog section
        # Input voltage range
        ljm.eWriteName(self.lj_handle, "AIN_ALL_RANGE", 10.0)
        return startup_mp

    def __del__(self):
        if self.valid is True:
            ljm.close(self.lj_handle)

    @property
    def _get_data(self):
        """Read data from LJ T7 and insert into monitor point dictionary.

        Values are read from the current LabJack T7 in a single operation through the ljm driver.
        These are converted into the appropriate data types in the relevant units and put in the
        one-second cadence monitor point dictionaries for each of the connected antennas.
        """
        if self.valid is True:
            psu_vals = ljm.eReadNameArray(self.lj_handle, "AIN0", 2)
            lj_temp = ljm.eReadName(self.lj_handle, "TEMPERATURE_DEVICE_K")
            analog_vals = ljm.eReadNameArray(self.lj_handle, "AIN48", 80)
            time_stamp = float(f"{Time.now().mjd:.8f}")
            j = 0
            for i in range(self.BEB_PER_LJ):
                self.monitor_points[i]['ant_num'] = self.beb_num + i
                self.monitor_points[i]['time'] = float(time_stamp)
                self.monitor_points[i]['pd_current_a'] = analog_vals[j]
                j += 1
                self.monitor_points[i]['pd_current_b'] = analog_vals[j]
                j += 1
                self.monitor_points[i]['if_pwr_a'] = 1000 * analog_vals[j] / 35.0 - 90.0
                j += 1
                self.monitor_points[i]['if_pwr_b'] = 1000 * analog_vals[j] / 35.0 - 90.0
                j += 1
                self.monitor_points[i]['lo_mon'] = analog_vals[j]
                j += 1
                self.monitor_points[i]['beb_current_a'] = 100.0 * analog_vals[j]
                j += 1
                self.monitor_points[i]['beb_current_b'] = 100.0 * analog_vals[j]
                j += 1
                self.monitor_points[i]['beb_temp'] = 100.0 * analog_vals[j] - 50.0
                j += 1
                self.monitor_points[i]['psu_voltage'] = psu_vals[0]
                self.monitor_points[i]['psu_current'] = 1000 * psu_vals[1]
                self.monitor_points[i]['lj_temp'] = lj_temp
        return self.monitor_points

    def send_to_etcd(self, key, mon_data):
        """Convert a monitor point dictionary to JSON and send to etcd key/value store."""
        if self.etcd_valid:
            j_pkt = json.dumps(mon_data)
            self.etcd_client.put(key, j_pkt)

    def run(self):
        """Run the communication code for the BEB LJ T7.

        This function should be run in a thread for this BEB instance."""

        # Set up logging
        func = inspect.stack()[0][3]
        func_name = f"{self.class_name}::beb{self.beb_num}.{func}"
        self.logger.function(func_name)
        self.logger.info(f"Running BEB {self.beb_num} thread")

        # Run data query loop until stop flag set
        while not self.stop:
            mon_data = self._get_data
            enumerate(mon_data)
            for i, dat in enumerate(mon_data):
                self.send_to_etcd(self.etcd_mon_key[i], dat)
            t_now = time.time()
            next_time = (int(t_now / Constants.POLLING_INTERVAL) + 1) * Constants.POLLING_INTERVAL
            sleep_time = next_time - time.time()
            if sleep_time > 0.0:
                time.sleep(sleep_time)

        self.logger.function(func_name)
        self.logger.info(f"BEB {self.beb_num} disconnecting")
        self.etcd_client.close()

    def stop_thread(self):
        """Set a flag to stop the thread this instance is run in"""
        self.stop = True


class Constants:
    """Useful constants for the LabJack classes to use"""

    # Number of LabJack T7 modules to simulate
    NUM_SIM = 3

    # Types of LJ T7
    NULL_TYPE = 0
    ANT_TYPE = 1
    BEB_TYPE = 2

    # Time between queries
    POLLING_INTERVAL = 1

    # Digital Ports
    ID_WORD = "FIO_STATE"
    DRIVE = "EIO1"  # This is the 'north' bit; next is 'south' bit
    NOISE_A = "EIO3"
    NOISE_B = "EIO4"
