"""Unit test for the analog hardware monitor and control subsystem 'hwmc'"""
from unittest import mock, TestCase, main

import hwmc.lj_startup as su
import labjack.ljm as ljm
import labjack.ljm.errorcodes as lje

IO_CONFIG_CHECK_FOR_FACTORY = False
PRODUCT_ID = 7
HARDWARE_VERSION = 1.350
FIRMWARE_VERSION = 1.0287
BOOTLOADER_VERSION = 0.96
SERIAL_NUMBER = 470019710
LUA_RUN = False
DEVICE_NAME_DEFAULT = 'DSA Ant-1'


class TestLjStartup(TestCase):
    """Test the LabJack startup class"""

    def eReadName_side_effect(*args, **kwargs):
        """Function to define responses to eReadName mock function"""
        if not isinstance(args[1], int):
            error = lje.DEVICE_NOT_FOUND
            raise ljm.LJMError(error)

        if args[2] == 'IO_CONFIG_CHECK_FOR_FACTORY':
            return IO_CONFIG_CHECK_FOR_FACTORY
        elif args[2] == 'PRODUCT_ID':
            return PRODUCT_ID
        elif args[2] == 'HARDWARE_VERSION':
            return HARDWARE_VERSION
        elif args[2] == 'FIRMWARE_VERSION':
            return FIRMWARE_VERSION
        elif args[2] == 'BOOTLOADER_VERSION':
            return BOOTLOADER_VERSION
        elif args[2] == 'SERIAL_NUMBER':
            return int(SERIAL_NUMBER)
        elif args[2] == 'LUA_RUN':
            return LUA_RUN
        elif args[2] == 'DEVICE_NAME_DEFAULT':
            return DEVICE_NAME_DEFAULT
        else:
            return None

    def eReadNameByteArray_side_effect(*args, **kwargs):
        """mock function to simulate reading a byte array from a LabJack module"""
        if args[2] == 'DEVICE_NAME_DEFAULT':
            return DEVICE_NAME_DEFAULT.encode('ascii')

    def setUp(self) -> None:
        """Set up patches to mock out LabJack functions"""
        self.patcher1 = mock.patch('labjack.ljm.eReadName',
                                   side_effect=self.eReadName_side_effect)
        self.patcher2 = mock.patch('labjack.ljm.eReadNameByteArray',
                                   side_effect=self.eReadNameByteArray_side_effect)
        self.patcher3 = mock.patch('labjack.ljm.eReadAddress', return_value=126)
        self.patcher4 = mock.patch('labjack.ljm.eWriteName', return_value=None)
        self.patcher1.start()
        self.patcher2.start()
        self.patcher3.start()
        self.patcher4.start()

    def test_ljstartup(self, *args):
        """Test the LabJack startup function with mock interfaces"""
        lj_handle = 1
        lua_required = True
        ant_num=7
        start_up_state = su.t7_startup_check(lj_handle, lua_required=lua_required, ant_num=ant_num)
        print(f"start_up_state['factory']: {start_up_state['factory']}")
        self.assertEqual(start_up_state['factory'], IO_CONFIG_CHECK_FOR_FACTORY)
        self.assertEqual(start_up_state['prod_id'], PRODUCT_ID)
        self.assertEqual(start_up_state['hw_ver'], HARDWARE_VERSION)
        self.assertEqual(start_up_state['fw_ver'], FIRMWARE_VERSION)
        self.assertEqual(start_up_state['ser_no'], SERIAL_NUMBER)
        self.assertEqual(start_up_state['dev_name'], DEVICE_NAME_DEFAULT)
        self.assertEqual(start_up_state['lua_running'], LUA_RUN)
        self.assertEqual(start_up_state['factory'], IO_CONFIG_CHECK_FOR_FACTORY)
        self.assertEqual(start_up_state['config_valid'], IO_CONFIG_CHECK_FOR_FACTORY)
        lj_handle = 'foo'
        start_up_state = su.t7_startup_check(lj_handle, lua_required=lua_required, ant_num=ant_num)
        error = lje.DEVICE_NOT_FOUND
        self.assertRaises(ljm.LJMError(error), lambda: su.lj_startup)


    def tearDown(self) -> None:
        """Tidy up after testing"""
        self.patcher1.stop()
        self.patcher2.stop()
        self.patcher3.stop()
        self.patcher4.stop()


if __name__ == '__main__':
    main()
    """Main entry point for testing the LabJack startup function"""
