import socket
import time
from typing import Dict, Any, Union, Tuple

HOST_IP = 'localhost'
MP_SERVER_PORT = 50000
CMD_SERVER_PORT = 50001
SOCKET_TIMEOUT = 5.0
BLOCK_SIZE = 8192


mps: Dict[Union[str, Any], Union[Tuple[str, str, str], Any]] = \
    {'ant_el': ("Elevation", 'analog', "°"),
     'drive_cmd': ("Drive cmd", 'enum', ('stop', 'north', 'south', 'invalid')),
     'drive_act': ("Drive actual", 'enum', ('off', 'north', 'south', 'invalid')),
     'drive_state': ("Drive state", 'enum', ('halt', 'seek', 'acquired', 'timeout', 'fw_lim_n',
                                             'fw_lim_s'))}


class SourceScan:
    def __init__(self, ant):
        self.quit = False
        self.read_socket = None
        self.write_socket = None
        self.connected = False
        self.mp_data = ''
        self.ant_num = ant
        self.ant = 'ant{}'.format(self.ant_num)

    def make_connection(self):
        self.connected = False
        self.read_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.read_socket.settimeout(SOCKET_TIMEOUT)
        self.write_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.write_socket.settimeout(SOCKET_TIMEOUT)
        try:
            self.read_socket.settimeout(10.0)
            self.read_socket.connect((HOST_IP, MP_SERVER_PORT))
            self.read_socket.settimeout(SOCKET_TIMEOUT)
            self.write_socket.connect((HOST_IP, CMD_SERVER_PORT))
            self.write_socket.settimeout(SOCKET_TIMEOUT)
            self.connected = True
        except ConnectionRefusedError:
            self.connected = False
        if self.connected:
            source = self.ant + '\n'
            self.read_socket.sendall(source.encode('ascii'))

    def ant_stop(self):
        if self.ant:
            cmd = "move {} stop\n".format(self.ant_num)
            self.write_socket.sendall(cmd.encode('ascii'))

    def move_el(self, el):
        if self.ant:
            cmd = "move {} {}\n".format(self.ant_num, float(el))
            self.write_socket.sendall(cmd.encode('ascii'))

    def get_mps(self):
        # See if decoded data make sense
        try:
            rev = self.read_socket.recv(BLOCK_SIZE)
            self.mp_data = self.mp_data + rev.decode('ascii')
        except:
            return ''
        mp_points = []
        pos = self.mp_data.find('\n')
        while pos != -1:
            x = self.mp_data[: pos]
            mp_points.append(x)
            self.mp_data = self.mp_data[pos + 1:]
            pos = self.mp_data.find('\n')
        return mp_points


CYCLES = 100
INTERVAL = 30
MIN_ANG = 10.0
MAX_ANG = 140.0
SPAN = MAX_ANG - MIN_ANG


antenna_num = int(input("Antenna number: "))
scan_cen = float(input("Scan elevation center: "))
scan_offset = float(input("Scan offset (deg): "))
dwell_time = float(input("Off source dwell time (s): "))
num_cycles = int(input("Number of cycles: "))

scan = SourceScan(antenna_num)
scan.make_connection()

print("Moving to elevation{: .2f} deg ".format(scan_cen), end='')
scan.move_el(scan_cen)
stop = False
while True:
    time.sleep(1)
    print(".", end="", flush=True)
    mp_points = scan.get_mps()
    for m in mp_points:
        t, a, mpt, v = m.split(',')
        stop = False
        if mpt == 'drive_state':
            st = mps['drive_state'][2][int(v)]
            if st == 'seek':
                stop = True
                break
    if stop is True:
        break
    stop = False
while True:
    time.sleep(1)
    print(".", end="", flush=True)
    mp_points = scan.get_mps()
    for m in mp_points:
        t, a, mpt, v = m.split(',')
        stop = False
        if mpt == 'drive_state':
            st = mps['drive_state'][2][int(v)]
            if st == 'acquired':
                print("\nOn source")
                stop = True
                break
            print("Timed out")
            stop = True
            break
    if stop is True:
        break
stop = False
input("\nPress a key to start: ")

for i in range(num_cycles):
    # Scan south
    angle = scan_cen - scan_offset
    print("Cycle: {}, elevation:{: .1f} ".format(i, angle), end='', flush=True)
    scan.move_el(angle)
    stop = False
    while True:
        time.sleep(1)
        print(".", end="", flush=True)
        mp_points = scan.get_mps()
        for m in mp_points:
            t, a, mpt, v = m.split(',')
            stop = False
            if mpt == 'drive_state':
                st = mps['drive_state'][2][int(v)]
                if st == 'seek':
                    stop = True
                    break
        if stop is True:
            break
    stop = False
    while True:
        time.sleep(1.0)
        mp_points = scan.get_mps()
        print(".", end='', flush=True)
        for m in mp_points:
            t, a, mpt, v = m.split(',')
            if mpt == 'drive_state':
                st = mps['drive_state'][2][int(v)]
                if st in ('acquired', 'timeout'):
                    stop = True
                break
        if stop is True:
            break

    # Spend time off source
    print("\nPause off source for {} s ...".format(dwell_time))
    time.sleep(dwell_time)

    # Scan north
    angle = scan_cen + scan_offset
    print("Cycle: {}, elevation:{: .1f} ".format(i, angle), end='', flush=True)
    scan.move_el(angle)
    stop = False
    while True:
        time.sleep(1)
        print(".", end="", flush=True)
        mp_points = scan.get_mps()
        for m in mp_points:
            t, a, mpt, v = m.split(',')
            stop = False
            if mpt == 'drive_state':
                st = mps['drive_state'][2][int(v)]
                if st == 'seek':
                    stop = True
                    break
        if stop is True:
            break
    stop = False
    while True:
        time.sleep(1.0)
        mp_points = scan.get_mps()
        print(".", end='', flush=True)
        for m in mp_points:
            t, a, mpt, v = m.split(',')
            if mpt == 'drive_state':
                st = mps['drive_state'][2][int(v)]
                if st in ('acquired', 'timeout'):
                    stop = True
                break
        if stop is True:
            break

    # Spend time off source
    print("\nPause off source for {} s ...".format(dwell_time))
    time.sleep(dwell_time)

print("Finished")
