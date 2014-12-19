"""Contain the tests for proxy device server."""

# Imports
from mock import Mock
from PyTango.server import command
from devicetest import DeviceTestCase
from PyTango import DevState

# Proxy imports
from proxydevice import Proxy, ProxyMeta
from proxydevice import device as proxy_module
from proxydevice import proxy_command, proxy_attribute
from proxydevice import proxy, logical_attribute


# Example
class CameraScreen(Proxy):
    __metaclass__ = ProxyMeta

    # Proxy
    PLCDevice = proxy("PLCDevice")

    # Proxy attributes
    StatusIn = proxy_attribute(
        device="OPCDevice",
        attr="InStatusTag",
        dtype=bool)

    StatusOut = proxy_attribute(
        device="OPCDevice",
        attr="OutStatusTag",
        dtype=bool)

    # Logical attributes
    @logical_attribute(dtype=bool)
    def Error(self, data):
        return data["StatusIn"] == data["StatusOut"]

    # Proxy commands
    MoveIn = proxy_command(
        device="OPCDevice",
        attr="InCmdTag",
        value=1)

    MoveOut = proxy_command(
        device="OPCDevice",
        attr="OutCmdTag",
        value=1)

    # Property
    @property
    def connected(self):
        return bool(self.data)

    # State
    def state_from_data(self, data):
        if data['Error']:
            return DevState.FAULT
        return DevState.INSERT if data['StatusIn'] else DevState.EXTRACT

    # Status
    def status_from_data(self, data):
        if data['Error']:
            return "Conflict between IN and OUT informations"
        return "IN" if data['StatusIn'] else "OUT"

    @command
    def Reset(self):
        self.devices["PLCDevice"].Reset()


# Device test case
class ProxyTestCase(DeviceTestCase):
    """Test case for packet generation."""

    device = CameraScreen
    properties = {"InCmdTag":     "tag1",
                  "OutCmdTag":    "tag2",
                  "InStatusTag":  "tag3",
                  "OutStatusTag": "tag4",
                  "OPCDevice":    "a/b/c",
                  "PLCDevice":    "c/d/e"}

    @classmethod
    def mocking(cls):
        # Mock DeviceProxy
        cls.DeviceProxy = proxy_module.DeviceProxy = Mock(name="DeviceProxy")
        cls.proxy = cls.DeviceProxy.return_value
        cls.bool_attr = [Mock(value=False), Mock(value=True)]
        cls.proxy.read_attributes.return_value = [cls.bool_attr[False]]*2

    def test_attributes(self):
        # Expected values
        tags = ['tag3', 'tag4']
        states = [[DevState.FAULT, DevState.EXTRACT],
                  [DevState.INSERT, DevState.FAULT]]
        status = [["Conflict", "OUT"], ["IN", "Conflict"]]
        # InStatus in [False, True]
        for x in range(2):
            # OutStatus in [False, True]
            for y in range(2):
                # Perform tests
                return_value = [self.bool_attr[x], self.bool_attr[y]]
                self.proxy.read_attributes.return_value = return_value
                self.assertEqual(self.device.StatusIn, x)
                self.assertEqual(self.device.StatusOut, y)
                self.assertEqual(self.device.Error, x == y)
                self.assertEqual(self.device.state(), states[x][y])
                self.assertIn(status[x][y], self.device.status())
                self.proxy.read_attributes.assert_called_with(tags)
        # Proxy
        args_list = [x.args for x in self.DeviceProxy.call_args_list]
        self.assertEqual(len(args_list), 2)
        self.assertIn(("a/b/c",), args_list)
        self.assertIn(("c/d/e",), args_list)

    def test_commands(self):
        # MoveIn command
        self.device.MoveIn()
        self.proxy.write_attribute.assert_called_with("tag1", 1)
        # MoveOut command
        self.device.MoveOut()
        self.proxy.write_attribute.assert_called_with("tag2", 1)
        # Rest command
        self.device.Reset()
        self.proxy.Reset.assert_called_once()
