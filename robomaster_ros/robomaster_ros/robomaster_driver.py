import os
import signal
import sys
import time
from pathlib import Path
from typing import Any, Optional

import rclpy
import rclpy.executors
import rclpy.logging


def _add_sdk_source() -> None:
    value = os.environ.get("ROBOMASTER_SDK_PATH", "")
    if not value:
        return
    sdk_path = Path(value).expanduser()
    package_path = sdk_path / "robomaster"
    if not package_path.is_dir():
        raise RuntimeError(
            f"RoboMaster SDK source not found: {package_path}. "
            "Set the launch argument backend_path to the SDK or LAB-SDK directory."
        )
    sys.path.insert(0, str(sdk_path))


def main(args: Any = None) -> None:
    _add_sdk_source()
    from robomaster_ros.client import RoboMasterROS

    rclpy.init(args=args)
    executor = rclpy.executors.MultiThreadedExecutor()
    # TODO(Jerome): currently not triggered by ctrl+C
    # rclpy.get_default_context().on_shutdown(...)
    should_reconnect = True
    running = True

    node: Optional[RoboMasterROS] = None

    def shutdown(sig, _):
        nonlocal should_reconnect
        nonlocal running
        running = False
        if not node:
            raise KeyboardInterrupt

    signal.signal(signal.SIGINT, shutdown)

    while should_reconnect and rclpy.ok() and running:
        try:
            node = RoboMasterROS(executor=executor)
        except KeyboardInterrupt:
            break
        should_reconnect = node.reconnect
        if not node.disconnection.done():
            try:
                while rclpy.ok() and not node.disconnection.done() and running:
                    rclpy.spin_until_future_complete(
                        node, node.disconnection, executor=executor, timeout_sec=1.0)
            except KeyboardInterrupt:
                running = False
                break
            except rclpy._rclpy_pybind11.RCLError:
                running = False
                break
        node.stop_heartbeat_check()
        if rclpy.ok():
            node.abort()
            rclpy.spin_once(node, executor=executor, timeout_sec=0.1)
        if rclpy.ok():
            node.stop()
            rclpy.spin_once(node, executor=executor, timeout_sec=0.1)
        node.destroy_node()
        node = None
        time.sleep(0.1)
    rclpy.try_shutdown()
    if node:
        node.destroy_node()
