from typing import Dict, Type

from .. import Module

ALL_MODULE_NAMES = {
    "arm",
    "armor",
    "battery",
    "blaster",
    "camera",
    "chassis",
    "gimbal",
    "gripper",
    "led",
    "pwm",
    "sbus",
    "sensor_adapter",
    "servo",
    "speaker",
    "tof",
    "uart",
    "vision",
}


def get_modules(constrained_s1: bool = False) -> Dict[str, Type[Module]]:
    """Load only modules supported by the selected SDK transport.

    LAB-SDK and the direct SOLO SDK intentionally do not provide the private
    EP protocol classes needed merely to import unsupported ROS modules.
    """
    from .armor import Armor
    from .battery import Battery
    from .blaster import Blaster
    from .camera import Camera
    from .chassis import Chassis
    from .gimbal import Gimbal
    from .led import LED

    result: Dict[str, Type[Module]] = {
        "armor": Armor,
        "battery": Battery,
        "blaster": Blaster,
        "camera": Camera,
        "chassis": Chassis,
        "gimbal": Gimbal,
        "led": LED,
    }
    if constrained_s1:
        return result

    from .arm import Arm
    from .gripper import Gripper
    from .pwm import PWM
    from .sbus import SBus
    from .sensor_adapter import SensorAdapter
    from .servo import Servo
    from .speaker import Speaker
    from .tof import ToF
    from .uart import Uart
    from .vision import Vision

    result.update(
        {
            "arm": Arm,
            "gripper": Gripper,
            "pwm": PWM,
            "sbus": SBus,
            "sensor_adapter": SensorAdapter,
            "servo": Servo,
            "speaker": Speaker,
            "tof": ToF,
            "uart": Uart,
            "vision": Vision,
        }
    )
    return result
