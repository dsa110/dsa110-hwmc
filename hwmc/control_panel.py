#! python3
"""This control panel allows presents a GUI interface to a DSA-110 antenna.

When this script is run, a GUI control panel is opened to display monitor points from a selected
DSA_110 antenna. The panel also allows control of the antenna elevation and LNA noise sources.
Configuration information is contained in a YAML file that is read on start up.

Communication to the antenna control is through the DSA-110 etcd key/value store. As this is a
TCP/IP connection, it can easily be tunneled through an SSH connection.
"""
import argparse
import json
import math
import time
import tkinter as tk

import etcd3 as etcd
from hwmc import get_yaml_config

ROW_PAD = 20
COL_PAD = 30

# Dictionary of monitor points to display. This has to be manually synchronized with the antenna
# control system.
MPS = {'time': ("MJD", 'analog', "day"),
       'ant_el': ("Elevation", 'analog', "°"),
       'ant_cmd_el': ("El target", 'analog', "°"),
       'ant_el_err': ("El error", 'analog', "°"),
       'motor_temp': ("Motor temp", 'analog', "°C"),
       'focus_temp': ("Motor temp", 'analog', "°C"),
       'lj_temp': ("LabJack temperature", 'analog', "°C"),
       'lna_current_a': ("LNA A current", 'analog', "mA"),
       'lna_current_b': ("LNA B current", 'analog', "mA"),
       'rf_pwr_a': ("RF A power", 'analog', "dBm"),
       'rf_pwr_b': ("RF B power", 'analog', "dBm"),
       'laser_volts_a': ("Laser A voltage", 'analog', "V"),
       'laser_volts_b': ("Laser B voltage", 'analog', "V"),
       'feb_current_a': ("FEB A current", 'analog', "mA"),
       'feb_current_b': ("FEB B current", 'analog', "mA"),
       'feb_temp_a': ("FEB A temperature", 'analog', "°C"),
       'feb_temp_b': ("FEB B temperature", 'analog', "°C"),
       'psu_volt': ("Power supply", 'analog', "V"),
       'drv_cmd': ("Drive cmd", 'enum', ('halt', 'north', 'south', 'invalid')),
       'drv_act': ("Drive actual", 'enum', ('off', 'north', 'south', 'invalid')),
       'drv_state': ("Drive state", 'enum', ('halt', 'seek', 'acquired', 'timeout', 'fw_lim_n',
                                             'fw_lim_s')),
       'sim': ("Simulate", 'dig', None),
       'brake_on': ("Brake", 'dig', None),
       'at_north_lim': ("North limit", 'dig', None),
       'at_south_lim': ("South limit", 'dig', None),
       'fan_err': ("Fan error", 'dig', None),
       'noise_a_on': ("Noise A", 'dig', None),
       'noise_b_on': ("Noise B", 'dig', None),
       'emergency_off': ("Emergency off", 'dig', None),
       }


class HwmcControlPanel:
    '''Create an instance of a control panel.'''
    def __init__(self, config):
        """Create a control window and populate it with monitor point displays and controls.

        A tkinter winndow is created and poopulated with the appropriate widgets for displaying
        monitor point values and for sending commands to the antenna control system. The
        information for the display and control widgets is taken from the monitor point
        dictionary.

        The layout is semi-automatically created with different types of monitor point or
        control assigned to different frames. Some of the parameters need to be tweaked to
        improve readability, but as an early-implementation tool this is not fully optimized.
        """
        self.quit = False
        self.connected = False
        self.watch_id = None
        self.mp_data = ''
        self.ant = ''
        self.ant_num = None
        self.etcd = None
        self.etcd_endpoint = config['etcd_endpoint']
        self.etcd_mon_key = None
        self.etcd_cmd_key = None
        self.tk_el = None

        # Create a new main window, and a method for handling its exit
        self.root = tk.Tk()
        self.root.protocol("WM_DELETE_WINDOW", self.quit_callback)

        # Add a frame inside this to control edge spacing
        main_frame = self._add_main_frame()

        # Add a sub-frame for the controls, populated with the controls
        self._add_control_frame(main_frame, 1, 0)

        # Add another sub-frame for the analog monitor points
        self._add_analog_frame(main_frame, 1, 1)

        # And a frame for enumeration monitor points
        self._add_enum_frame(main_frame, 2, 1)

        # The frame for the digital (boolean) data
        self._add_dig_frame(main_frame, 2, 2)

        #  A frame for antenna commands
        self._add_cmd_frame(main_frame, 3, 0, 3)

        # And finally, the frame for displaying informational messages
        self._add_msg_frame(main_frame, 4, 0, 3)

    def _add_main_frame(self):
        main_frame = tk.Frame(self.root, relief=tk.RIDGE, bd=4)
        main_frame.grid(row=0)
        main_frame.rowconfigure(0, pad=ROW_PAD)
        label_main = tk.Label(main_frame, text=" Antenna Monitor Point Display ",
                              font=('Arial', 14), fg='blue', bd=4, bg='white', relief=tk.RAISED)
        label_main.grid(row=0, column=0, columnspan=3)
        return main_frame

    def _add_control_frame(self, main_frame, row, col):
        control_frame = tk.Frame(main_frame, relief=tk.GROOVE, bd=4)
        control_frame.grid(row=row, column=col, sticky=tk.NW + tk.SE, rowspan=2)
        control_frame.columnconfigure(0, minsize=50, pad=COL_PAD)
        control_frame.columnconfigure(1, pad=COL_PAD)
        control_frame.columnconfigure(2, pad=COL_PAD)
        control_frame.rowconfigure(0, pad=ROW_PAD)
        control_frame.rowconfigure(1, pad=ROW_PAD)
        control_frame.rowconfigure(2, pad=ROW_PAD)
        control_frame.rowconfigure(3, pad=ROW_PAD)

        # Create Tkinter variable to hold antenna number
        self.tk_ant = tk.StringVar(self.root)

        # Create a spinner for antenna number, with a label
        label_ant = tk.Label(control_frame, text="Connect to antenna")
        label_ant.grid(row=0, column=0, sticky=tk.E)
        self.tk_ant = tk.Spinbox(control_frame, from_=1, to=110, width=6)
        self.tk_ant.grid(row=0, column=1)

        # Create a label and text display for selected antenna
        label_ant_sel = tk.Label(control_frame, text="Antenna connected")
        label_ant_sel.grid(row=1, column=0, sticky=tk.E)
        self.text_ant_sel = tk.Text(control_frame, height=1, width=6, bg='white', fg='blue')
        self.text_ant_sel.grid(row=1, column=1)

        # Add a button to start data capture, and a quit button
        add_button = tk.Button(control_frame, text="Connect", width=6,
                               command=self.connect_callback)
        add_button.grid(row=2, column=1)
        quit_button = tk.Button(control_frame, text="Quit", width=6, command=self.quit_callback)
        quit_button.grid(row=3, column=1)

    def _add_msg_frame(self, main_frame, row, col, span=1):
        # Create a frame for messages
        msg_frame = tk.Frame(main_frame, relief=tk.GROOVE, bd=4)
        msg_frame.grid(row=row, column=col, sticky=tk.NW + tk.SE, columnspan=span)
        msg_frame.columnconfigure(0, pad=COL_PAD)
        msg_frame.rowconfigure(0, pad=ROW_PAD)

        self.msg_field = tk.Text(msg_frame, height=1, bg='white', fg='blue', font=('Courier', 8))
        self.msg_field.grid(row=0, column=0, sticky=tk.W + tk.E)

    def _add_analog_frame(self, main_frame, row, col):
        # Set up the frame for displaying analog values
        a_display_frame = tk.Frame(main_frame, relief=tk.GROOVE, bd=4)
        a_display_frame.grid(row=row, column=col, columnspan=2, sticky=tk.W)

        # Count analog monitor points
        a_cell_info = []
        analog_count = 0
        for key, val in MPS.items():
            mp_name, mp_type, mp_units = val
            if mp_type == 'analog':
                a_cell_info.append((key, mp_name, mp_units))
                analog_count += 1

        n_rows = int(math.sqrt(analog_count) + 0.9999)
        n_cols = int(analog_count / n_rows + 0.9999)

        # Add in fields for monitor points
        a_title = tk.Label(a_display_frame, text="Analog Monitor Points")
        a_title.grid(row=0, column=0, columnspan=2 * n_cols, sticky=tk.S)
        a_labels = []
        a_units = []
        self.a_fields = {}
        i = 0
        width = 13
        for r in range(n_rows):
            for c in range(n_cols):
                if i < analog_count:
                    current_cell_info = a_cell_info[i]
                    a_labels.append(tk.Label(a_display_frame, text=current_cell_info[1]))
                    a_labels[i].grid(row=2 * r + 1, column=2 * c, sticky=tk.S)
                    self.a_fields[current_cell_info[0]] = tk.Text(a_display_frame,
                                                                  background='white', width=width,
                                                                  height=1, bd=3)
                    self.a_fields[current_cell_info[0]].grid(row=2 * r + 2, column=2 * c,
                                                             sticky=tk.N, pady=5)
                    a_units.append(tk.Label(a_display_frame, text=current_cell_info[2]))
                    a_units[i].grid(row=2 * r + 2, column=2 * c + 1, sticky=tk.W)
                    i += 1

    def _add_enum_frame(self, main_frame, row, col):
        # Set up the frame for displaying enumeration values
        e_display_frame = tk.Frame(main_frame, relief=tk.GROOVE, bd=4)
        e_display_frame.grid(row=row, column=col, sticky=tk.NW + tk.SE)
        e_display_frame.columnconfigure(0, pad=COL_PAD)
        e_display_frame.columnconfigure(1, pad=COL_PAD)
        e_display_frame.rowconfigure(0, pad=ROW_PAD)

        # Count enumeration monitor points
        e_cell_info = []
        self.e_enums = {}
        enum_count = 0
        for key, val in MPS.items():
            mp_name, mp_type, enums = val
            if mp_type == 'enum':
                e_cell_info.append((key, mp_name))
                self.e_enums[key] = enums
                enum_count += 1

        n_rows = int(math.sqrt(enum_count) + 0.9999)
        n_rows = max(n_rows, 1)
        n_cols = int(enum_count / n_rows + 0.9999)
        n_cols = max(n_cols, 1)

        # Add in fields for monitor points
        label_enum = tk.Label(e_display_frame, text="Enumeration Monitor Points")
        label_enum.grid(row=0, column=0, columnspan=n_cols)
        e_labels = []
        self.e_fields = {}
        i = 0
        width = 10
        for r in range(n_rows):
            for c in range(n_cols):
                if i < enum_count:
                    current_cell_info = e_cell_info[i]
                    e_labels.append(tk.Label(e_display_frame, text=current_cell_info[1]))
                    e_labels[i].grid(row=2 * r + 1, column=c)
                    self.e_fields[current_cell_info[0]] = tk.Text(e_display_frame,
                                                                  background='white', width=width,
                                                                  height=1, bd=3)
                    self.e_fields[current_cell_info[0]].grid(row=2 * r + 2, column=c, sticky=tk.N)
                    i += 1

    def _add_dig_frame(self, main_frame, row, col):
        # Set up the frame for displaying digital values
        d_display_frame = tk.Frame(main_frame, relief=tk.GROOVE, bd=4)
        d_display_frame.grid(row=row, column=col, sticky=tk.NW + tk.SE)
        d_display_frame.columnconfigure(0, pad=0)
        d_display_frame.columnconfigure(1, pad=0)
        d_display_frame.rowconfigure(0, pad=ROW_PAD)

        # Count digital monitor points
        d_cell_info = []
        digital_count = 0
        for key, val in MPS.items():
            mp_name, mp_type, _ = val
            if mp_type == 'dig':
                d_cell_info.append((key, mp_name))
                digital_count += 1

        n_rows = int(math.sqrt(digital_count) + 0.9999)
        n_rows = max(n_rows, 1)
        n_cols = int(digital_count / n_rows + 0.9999)
        n_cols = max(n_cols, 1)

        # Add in fields for monitor points
        label_dig = tk.Label(d_display_frame, text="Digital Monitor Points")
        label_dig.grid(row=0, column=0, columnspan=n_cols)
        labels = []
        self.d_fields = {}
        i = 0
        width = 10
        for r in range(n_rows):
            for c in range(n_cols):
                if i < digital_count:
                    current_cell_info = d_cell_info[i]
                    labels.append(tk.Label(d_display_frame, text=current_cell_info[1]))
                    labels[i].grid(row=2 * r + 1, column=c, sticky=tk.S)
                    self.d_fields[current_cell_info[0]] = tk.Checkbutton(d_display_frame,
                                                                         width=width, height=1,
                                                                         bd=3)
                    self.d_fields[current_cell_info[0]].grid(row=2*r+2, column=c, sticky=tk.N)
                    i += 1

    def _add_cmd_frame(self, main_frame, row, col, span=1):
        # Set up the frame for the commands to the antennas
        cmd_frame = tk.Frame(main_frame, relief=tk.GROOVE, bd=4)
        cmd_frame.grid(row=row, column=col, columnspan=span, sticky=tk.NW)
        cmd_frame.rowconfigure(0, pad=20)
        label_cmd = tk.Label(cmd_frame, text="Antenna/Frontend Controls")
        label_cmd.grid(row=0, column=0, columnspan=9, sticky=tk.W + tk.E)

        # Add the few controls needed for the antenna/frontend functions
        halt_button = tk.Button(cmd_frame, text="Halt", width=8, command=self.halt_callback)
        halt_button.grid(row=1, column=2, padx=10)
        goto_button = tk.Button(cmd_frame, text="Go to -->", width=8, command=self.move_el_callback)
        goto_button.grid(row=1, column=3, padx=10)
        noise_a_on_button = tk.Button(cmd_frame, text="Noise A on", width=8,
                                      command=self.noise_a_on_callback)
        noise_a_on_button.grid(row=1, column=5, padx=10)
        noise_a_off_button = tk.Button(cmd_frame, text="Noise A off", width=8,
                                       command=self.noise_a_off_callback)
        noise_a_off_button.grid(row=1, column=6, padx=10)
        noise_b_on_button = tk.Button(cmd_frame, text="Noise B on", width=8,
                                      command=self.noise_b_on_callback)
        noise_b_on_button.grid(row=1, column=7, padx=10)
        noise_b_off_button = tk.Button(cmd_frame, text="Noise B off", width=8,
                                       command=self.noise_b_off_callback)
        noise_b_off_button.grid(row=1, column=8, padx=10)

        # Create an entry field for antenna elevation angle
        vcmd = cmd_frame.register(self.el_validate_callback)
        self.el_field = tk.Entry(cmd_frame, width=8, justify=tk.RIGHT, validate='all',
                                 validatecommand=(vcmd, '%P'))
        self.el_field.grid(row=1, column=4, sticky=tk.W)
        self.el_field.insert(0, '0.0')

        # Create Tkinter variable to hold requested elevation
        self.tk_el = tk.DoubleVar(self.root)

    @staticmethod
    def el_validate_callback(p):
        """Verify that the antenna elevation requested is in range."""
        if p == '':
            return True
        try:
            ang = float(p)
        except (NameError, ValueError):
            return False
        if ang < 0.0 or ang > 180.0:
            return False
        return True

    def update(self):
        """Update monitor point values on the control panel if there are new values available."""
        if self.mp_data:
            for mp in self.mp_data:
                val = self.mp_data[mp]
                if mp in self.a_fields:
                    val = "{:.3f}".format(val)
                    self.a_fields[mp].delete(1.0, tk.END)
                    self.a_fields[mp].insert(tk.END, val)
                elif mp in self.e_fields:
                    self.e_fields[mp].delete(1.0, tk.END)
                    self.e_fields[mp].insert(tk.END, self.e_enums[mp][int(val)])
                elif mp in self.d_fields:
                    if val is False:
                        self.d_fields[mp].deselect()
                    else:
                        self.d_fields[mp].select()
        self.root.update()

    def mp_callback(self, event):
        """Etcd watch callback function is called when values of watched monitor key is updated.

        When the monitor key is updated this function reads the new key values and converts them to
        a Python dictionary from a JSON formatted string.

        Args:
            event (:obj:): Etcd event containing the key and value.
        """
        value = event.events[0].value.decode('utf-8')
        self.mp_data = json.loads(value)

    def _open_connection(self, ant_num):
        if self.connected:
            self.etcd.cancel_watch(self.watch_id)
            self.ant_num = None
            self.connected = False
        self.etcd_mon_key = '/mon/ant/{0:d}'.format(ant_num)
        self.etcd_cmd_key = '/cmd/ant/{0:d}'.format(ant_num)
        try:
            self.etcd = etcd.client(host=self.etcd_endpoint[0], port=self.etcd_endpoint[1])
            self.etcd.add_watch_callback(self.etcd_mon_key, self.mp_callback)
            self.ant_num = ant_num
            self.connected = True
        except NameError:
            self._show_msg("Connection to 'ant-{}' refused".format(ant_num))
            self.connected = False
        if self.connected:
            self._show_msg("Connected to 'ant-{}'".format(ant_num))
            self.text_ant_sel.delete(1.0, tk.END)
            self.text_ant_sel.insert(tk.END, self.ant)

    def _close_connection(self):
        pass

    def _show_msg(self, msg):
        self.msg_field.config(state=tk.NORMAL)
        self.msg_field.delete(1.0, tk.END)
        self.msg_field.insert(tk.END, msg)
        self.msg_field.config(state=tk.DISABLED)

    def connect_callback(self):
        """Open an etcd connection for the current antenna."""
        self.ant_num = int(self.tk_ant.get())
        self.ant = 'ant{}'.format(self.ant_num)
        self._open_connection(self.ant_num)

    def quit_callback(self):
        """Exit the control panel application."""
        self._close_connection()
        self.quit = True
        self.root.destroy()

    def halt_callback(self):
        """Halt the antenna drive."""
        if self.ant:
            self.etcd_send('halt', None)

    def move_el_callback(self):
        """Move the antenna to the position read from the front panel."""
        if self.ant:
            self.tk_el = self.el_field.get()
            el = float(self.tk_el)
            self.etcd_send('move', el)

    def noise_a_on_callback(self):
        "Switch noise source A on."
        if self.ant:
            self.etcd_send('noise_a_on', True)

    def noise_a_off_callback(self):
        "Switch noise source A off."
        if self.ant:
            self.etcd_send('noise_a_on', False)

    def noise_b_on_callback(self):
        "Switch noise source B on."
        if self.ant:
            self.etcd_send('noise_b_on', True)

    def noise_b_off_callback(self):
        "Switch noise source B off."
        if self.ant:
            self.etcd_send('noise_b_on', False)

    def etcd_send(self, cmd, val):
        """Pack the specified command and value into a JSON packet and sendit through etcd."""
        j_pkt = json.dumps({'cmd': cmd, 'val': val})
        self.etcd.put(self.etcd_cmd_key, j_pkt)


def main():
    cpl_config = {'etcd_endpoint': '192.168.1.132:2379'
                 }

    parser = argparse.ArgumentParser(description="Run the DSA-110 hardware monitor and control"
                                                 "panel")
    parser.add_argument('-c', '--config-file', metavar='CONFIG_FILE_NAME', type=str, required=False,
                        help="Fully qualified name of YAML configuration file. "
                        "If used, other arguments are ignored, except for '-s', '--s'")
    parser.add_argument('-i', '--etcd_ip', metavar='ETCD_IP', type=str, required=False,
                        default=cpl_config['etcd_endpoint'], help="Etcd server IP address and port."
                        " Default: {}".format(cpl_config['etcd_endpoint']))

    args = parser.parse_args()
    if args.config_file is not None:
        yaml_fn = args.config_file
        yaml_config = get_yaml_config.read_yaml(yaml_fn)
        for item in yaml_config:
            if item == 'etcd_endpoint':
                cpl_config[item] = yaml_config[item].split(':')
            else:
                cpl_config[item] = yaml_config[item]
    else:
        control_panel_config = {'etcd_endpoint': args.etcd_ip.split(':')}

    window = HwmcControlPanel(control_panel_config)

    REFRESH_SECONDS = 0.5
    while not window.quit:
        window.update()
        t = REFRESH_SECONDS - time.time() % REFRESH_SECONDS
        time.sleep(t)
    print("Finished")


if __name__ == '__main__':
    main()

