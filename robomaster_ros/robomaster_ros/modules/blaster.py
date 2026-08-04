"""ROS interfaces for the RoboMaster blaster."""

from typing import TYPE_CHECKING

import robomaster.blaster
import robomaster.robot

import robomaster_msgs.msg

import std_msgs.msg

if TYPE_CHECKING:
    from ..client import RoboMasterROS

from .. import Module


class Blaster(Module):
    """Control blaster LEDs and safe infrared firing."""

    def __init__(
        self, robot: robomaster.robot.Robot, node: 'RoboMasterROS'
    ) -> None:
        """Create blaster subscriptions and switch its LED off."""
        self.api = robot.blaster
        self.node = node
        node.create_subscription(robomaster_msgs.msg.BlasterLED, 'blaster_led',
                                 self.has_received_blaster_led, 1)
        node.create_subscription(
            std_msgs.msg.Empty, 'blaster/fire_ir',
            self.has_received_fire_ir, 1)
        robot.blaster.set_led(effect=robomaster.blaster.LED_OFF)

    def stop(self) -> None:
        """Stop the module."""
        pass

    def abort(self) -> None:
        """Abort the module."""
        pass

    def has_received_blaster_led(
        self, msg: robomaster_msgs.msg.BlasterLED
    ) -> None:
        """Set the blaster LED from a ROS message."""
        if msg.brightness:
            self.api.set_led(brightness=min(255, max(0, msg.brightness * 255)),
                             effect=robomaster.blaster.LED_ON)
        else:
            self.api.set_led(effect=robomaster.blaster.LED_OFF)

    def has_received_fire_ir(self, _msg: std_msgs.msg.Empty) -> None:
        """Fire one infrared beam; never select the physical gel blaster."""
        self.api.fire(fire_type=robomaster.blaster.INFRARED_FIRE, times=1)
