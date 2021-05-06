import logging
import pprint

from mobly import asserts
from mobly import base_test
from mobly import test_runner
from mobly.controllers import android_device

# Number of seconds for the target to stay discoverable on Bluetooth.
DISCOVERABLE_TIME = 60


class HelloWorldTest(base_test.BaseTestClass):
    def setup_class(self):
        self.pdb('setup_class')
        # Registering android_device controller module, and declaring that the test
        # requires at least two Android devices.
        self.ads = self.register_controller(android_device)
        
        # The device used to discover Bluetooth devices.
        self.dut = android_device.get_device(self.ads, label='dut')
        # Sets the tag that represents this device in logs.
        self.dut.debug_tag = 'dut'

        self.dut.load_snippet(
            'mbs',
            'com.google.android.mobly.snippet.bundled'
        )

    def setup_test(self):
        self.pdb('setup_test')
        # Make sure bluetooth is on.
        self.dut.mbs.btEnable()

        # Set Bluetooth name on target device.
        self.dut.mbs.btSetName('IamDUT')

    def test_bluetooth_discovery(self):
        self.dut.log.debug('force exception to occur!')
        self.target.test()
        target_name = self.user_params['search_bluetooth_name'].strip()
        # self.target.mbs.btBecomeDiscoverable(DISCOVERABLE_TIME)
        self.dut.log.info('Looking for Bluetooth devices.')
        discovered_devices = self.dut.mbs.btDiscoverAndGetResults()
        self.dut.log.debug(
            'Found Bluetooth devices: %s',
            pprint.pformat(discovered_devices, indent=2)
        )
        discovered_names = [device['Name'] for device in discovered_devices]
        logging.info('Verifying the target is discovered by the discoverer.')
        asserts.assert_true(
            target_name in discovered_names,
            'Failed to discover the target device %s over Bluetooth.' %
            target_name)

    def teardown_test(self):
        # Turn Bluetooth off on both devices after test finishes.
        self.dut.mbs.btDisable()


if __name__ == '__main__':
    test_runner.main()
