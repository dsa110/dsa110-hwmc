"""An application to plot selected monitor points from a given DSA-110 antenna."""

import argparse
import json
import math

import etcd3 as etcd
import get_yaml_config
import matplotlib
import plot_items as pi

matplotlib.use('TkAgg')
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib import style


class MpPlotter:
    """Class to plot DSA-110 analog hardware monitor points in real time."""

    MINUTES_PER_DAY = 24 * 60

    def __init__(self, n_plots, plot_list, axis_sets):
        """Set up the plot parameters.

        Args:
            n_plots (int): Total number of plot areas to show.
            plot_list (:obj:'list'): List of names of monitor points to plot.
            axis_sets
        """
        self.num_plots = n_plots
        self.plot_list = plot_list
        self.xs = {}
        self.ys = {}
        self.mjd_start = None
        self.ax = axis_sets
        self.ant = None
        self.new_data = False
        self.mp_data = ''

    def update(self, _):
        """Update the plot(s).

        Check to see if new values are available for the monitor point values and add them to
        the plot.
        """
        mp_points = self.get_mps()
        if mp_points:
            mjd = float(mp_points['time'])
            for mp in mp_points:
                if mp in mp_plot_list:
                    val = mp_points[mp]
                    if isinstance(val, bool):
                        if val is True:
                            val = 1
                        else:
                            val = 0
                    # Times will be referenced to initial MJD, so store start MJD here.
                    if not self.mjd_start:
                        self.mjd_start = mjd
                    # The first time a monitor point is seen, create its own storage array.
                    if mp not in self.xs:
                        self.xs[mp] = [(mjd - self.mjd_start) * self.MINUTES_PER_DAY]
                        self.ys[mp] = [val]
                    else:
                        self.xs[mp].append((mjd - self.mjd_start) * self.MINUTES_PER_DAY)
                        self.ys[mp].append(val)
                    # Treat single plot (possibly with multiple monitor points) differently from
                    # multiple plots.
                    if num_plots == 1:
                        self.ax['1'].clear()
                        self.ax['1'].set(xlabel='time (min)', ylabel='value')
                        title = ''
                        for m in self.xs:
                            title = '{}{}, '.format(title, m)
                            self.ax['1'].set(title=title)
                        self.ax['1'].legend(['A simple line'])
                        for m in self.xs:
                            self.ax['1'].plot(self.xs[m], self.ys[m])
                    # Multiple plots display only a single monitor point each.
                    else:
                        for m in self.xs:
                            self.ax[m].clear()
                            self.ax[m].set(xlabel="time (min)", ylabel="value",
                                           title="{}".format(m))
                            self.ax[m].plot(self.xs[m], self.ys[m])

    def get_mps(self):
        if self.new_data is False:
            return ''
        else:
            self.new_data = False
            return self.mp_data

    def mp_callback(self, event):
        """Etcd watch callback function is called when values of watched monitor key is updated.

        When the monitor key is updated this function reads the new key values and converts them to
        a JSON formatted string.

        Args:
            event (:obj:): Etcd event containing the key and value.
        """
        value = event.events[0].value.decode('utf-8')
        self.mp_data = json.loads(value)
        self.new_data = True


if __name__ == '__main__':
    NUM_ANTS = 110
    plt_config = {'etcd_endpoint': '192.168.1.132:2379'
                  }

    parser = argparse.ArgumentParser(description="Run the DSA-110 monitor point plotter")
    parser.add_argument('-c', '--config-file', metavar='CONFIG_FILE_NAME', type=str, required=False,
                        help="Fully qualified name of YAML configuration file. "
                        "If used, other arguments are ignored, except for '-s', '--s'")
    parser.add_argument('-i', '--etcd_ip', metavar='ETCD_IP', type=str, required=False,
                        default=plt_config['etcd_endpoint'], help="Etcd server IP address and port."
                        " Default: {}".format(plt_config['etcd_endpoint']))

    args = parser.parse_args()
    if args.config_file is not None:
        yaml_fn = args.config_file
        yaml_config = get_yaml_config.read_yaml(yaml_fn)
        for item in yaml_config:
            if item == 'etcd_endpoint':
                plt_config[item] = yaml_config[item].split(':')
            else:
                plt_config[item] = yaml_config[item]
    else:
        plt_config = {'etcd_endpoint': args.etcd_ip.split(':')}

    MPS = ['sim',
           'ant_num',
           'time',
           'ant_el',
           'ant_cmd_el',
           'ant_el_err',
           'drv_cmd',
           'drv_act',
           'drv_state',
           'north_lim',
           'south_lim',
           'brake_engage',
           'motor_temp',
           'focus_temp',
           'lna_current_a',
           'lna_current_b',
           'noise_a',
           'noise_b',
           'rf_pwr_a',
           'rf_pwr_b',
           'feb_current_a',
           'feb_current_b',
           'laser_volts_a',
           'laser_volts_b',
           'feb_temp_a',
           'feb_temp_b',
           'psu_volt',
           'lj_temp',
           'fan_err',
           'emergency_off',
           ]

    plot_items = pi.PlotItems(NUM_ANTS + 1, MPS)
    mp_plot_list = plot_items.mp_list
    ant = plot_items.selected_ant
    if plot_items.separate_plots:
        num_plots = len(mp_plot_list)
    else:
        num_plots = 1

    style.use('classic')
    fig = plt.figure("DSA-110 monitor point display: antenna  {}".format(ant),
                     facecolor='white')
    ax = {}
    if num_plots == 1:
        ax['1'] = fig.add_subplot(1, 1, 1)

    else:
        plot_rows = int(math.sqrt(num_plots) + 0.9999)
        plot_cols = int(num_plots / plot_rows + 0.9999)
        num_pos = plot_rows * plot_cols
        for i in range(num_plots):
            ax[mp_plot_list[i]] = fig.add_subplot(plot_rows, plot_cols, i + 1)
        fig.subplots_adjust(hspace=0.35)

    if mp_plot_list:
        connected = False
        etcd_mon_key = '/mon/ant/{0:d}'.format(plot_items.selected_ant)
        try:
            etcd_client = etcd.client(host=plt_config['etcd_endpoint'][0],
                                      port=plt_config['etcd_endpoint'][1])
            connected = True
        except ValueError:
            etcd_client = None
            connected = False
        if connected:
            print("Connected to 'ant-{}'".format(ant))
        mp = ''
        if connected:
            mp_plotter = MpPlotter(num_plots, mp_plot_list, ax)
            etcd_client.add_watch_callback(etcd_mon_key, mp_plotter.mp_callback)
            ani = animation.FuncAnimation(fig, mp_plotter.update, interval=100)
            mp_points = mp_plotter.get_mps()
            plt.show()
    print("Finished")
