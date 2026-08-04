# flake8: noqa: E402
import logging
import random
import time


import rclpy.logging
import rclpy.executors

# Disabled because it too expensive
# robomaster.logger = rclpy.logging.get_logger('sdk')

import robomaster
import robomaster.robot
import robomaster.protocol
import robomaster.conn
import robomaster.client


from robomaster_ros.modules import ALL_MODULE_NAMES, get_modules
from robomaster_ros.ftp import FtpConnection

import rclpy
import rclpy.node
import rclpy.action
import rclpy.task
import rclpy.duration

import std_msgs.msg
import sensor_msgs.msg

import tf2_ros.transform_broadcaster

from typing import Any, Optional


SERIAL_NUMBER_LENGTH = 14

def pad_serial(value: str) -> str:
  value = value[:SERIAL_NUMBER_LENGTH]
  value += '*' * (SERIAL_NUMBER_LENGTH - len(value))
  return value


def add_unknown_protocol(cmdset: int, cmdid: int, hint: str = '?') -> None:
    def unpack_resp(self: Any, buf: bytes, offset: int = 0) -> None:
        logging.debug(
            f'[{hint}] Received unknown response with cmd set {cmdset:#x} and id {cmdid:#x}, '
            f'with buffer {buf!r} ({len(buf)})')

    def unpack_req(self: Any, buf: bytes, offset: int = 0) -> None:
        logging.debug(
            f'[{hint}] Received unknown request with cmd set {cmdset:#x} and id {cmdid:#x}, '
            f'with buffer {buf!r} ({len(buf)})')

    _ = type(f'UnknownProtocol_{cmdset}_{cmdid}',
             (robomaster.protocol.ProtoData, ),
             {'_cmdset': cmdset,
              '_cmdid': cmdid,
              'unpack_resp': unpack_resp,
              'unpack_req': unpack_req})


def add_unknown_protocols() -> None:
    # state change
    add_unknown_protocol(0x3f, 0x29, 'CHASSIS STATE')
    # related to uart
    add_unknown_protocol(0x3f, 0xf4, 'SENSOR ADC')
    # related to tof
    add_unknown_protocol(0x24, 0x21, 'TOF')


add_unknown_protocols()

# add_unknown_protocol(0x3f, 0xb3)


def wait_for_robot(serial_number: Optional[str]) -> None:
    found = False
    while not found:
        try:
            found = robomaster.conn.scan_robot_ip(user_sn=serial_number)
        except OSError:
            pass
        if not found:
            time.sleep(random.uniform(1.0, 2.0))


class RoboMasterROS(rclpy.node.Node):  # type: ignore

    initialized: bool = False

    def __init__(self, executor: Optional[rclpy.executors.Executor] = None) -> None:
        super(RoboMasterROS, self).__init__("robomaster_ros", start_parameter_services=True)
        # Keep shutdown safe when an import or module constructor fails partway
        # through initialization.
        self.modules = {}
        # robomaster.logger.set_level(logging.ERROR)
        lib_log_level : str = self.declare_parameter("lib_log_level", "ERROR").value.upper()
        robomaster.logger.setLevel(lib_log_level)
        requested_backend: str = self.declare_parameter(
            "sdk_backend", "official").value.lower()
        if requested_backend not in {"official", "lab", "solo"}:
            raise RuntimeError(
                "sdk_backend must be one of: official, lab, solo"
            )
        self.lab_sdk = bool(getattr(robomaster, "IS_LAB_SDK", False))
        self.solo_sdk = bool(getattr(robomaster, "IS_S1_WIFI_SDK", False))
        if requested_backend == "lab" and not self.lab_sdk:
            raise RuntimeError(
                "sdk_backend=lab requires LAB-SDK to be available on PYTHONPATH"
            )
        if requested_backend == "solo" and not self.solo_sdk:
            raise RuntimeError(
                "sdk_backend=solo requires SDK/ to be available on PYTHONPATH"
            )
        if self.lab_sdk and requested_backend != "lab":
            self.get_logger().warning(
                "LAB-SDK is imported; selecting the lab backend"
            )
            requested_backend = "lab"
        if self.solo_sdk and requested_backend != "solo":
            self.get_logger().warning(
                "S1 Wi-Fi SDK is imported; selecting the solo backend"
            )
            requested_backend = "solo"
        self.constrained_s1_sdk = self.lab_sdk or self.solo_sdk
        self.sdk_backend = requested_backend
        conn_type: str = self.declare_parameter("conn_type", "sta").value[:]
        robot_ip: str = self.declare_parameter("robot_ip", "").value
        appid: str = self.declare_parameter("appid", "b6359877").value
        self.reconnect: bool = self.declare_parameter("reconnect", True).value
        sn: Optional[str] = self.declare_parameter("serial_number", "").value
        if sn:
            pass
            # if len(sn) != SERIAL_NUMBER_LENGTH:
            #     sn = pad_serial(sn)
            #     self.get_logger().warning(
            #         f"Serial number must have length {SERIAL_NUMBER_LENGTH}: "
            #         f"trasformed to {sn}")
        else:
            sn = None
        self.heartbeat_check_timer: Optional[rclpy.timer.Timer] = None
        self.connected = False
        if conn_type == 'sta' and not self.constrained_s1_sdk:
            self.get_logger().info("Waiting for a robot")
            wait_for_robot(sn)
            self.get_logger().info("Found a robot")
        if not self.constrained_s1_sdk:
            robomaster.conn.FtpConnection = FtpConnection
        # robomaster.conn.FtpConnection = FakeFtpConnection
        if self.constrained_s1_sdk:
            self.ep_robot = robomaster.robot.Robot(
                robot_ip=robot_ip,
                appid=appid,
            )
        else:
            self.ep_robot = robomaster.robot.Robot()
        self.disconnection = rclpy.task.Future(executor=executor or rclpy.get_global_executor())
        # For now, to handle simulations without FTP
        self.get_logger().info(f"Try to connect via {conn_type} to robot with sn {sn}")
        self.lab_bridge_started = False
        try:
            # The public robomaster.robot.Robot facade only exposes
            # initialize(conn_type, proto_type, sn): mode entry is a separate,
            # explicit step for both backends.
            self.ep_robot.initialize(conn_type=conn_type, sn=sn)
            if self.solo_sdk:
                self.ep_robot.enter_solo()
            elif self.lab_sdk:
                self.ep_robot.enter_lab()
                digest = self.ep_robot.upload_lab_bridge()
                self.ep_robot.start_lab_program(digest)
                self.ep_robot.start_lab_bridge()
                self.lab_bridge_started = True
        except Exception as exc:
            self.get_logger().error(f"Could not connect: {exc}")
            self.disconnection.set_result(False)
            return
        self.get_logger().info("Connected")
        qos = rclpy.qos.QoSProfile(
            depth=1,
            history=rclpy.qos.QoSHistoryPolicy.KEEP_LAST,
            durability=rclpy.qos.QoSDurabilityPolicy.TRANSIENT_LOCAL)
        self.connected_pub = self.create_publisher(std_msgs.msg.Bool, 'connected', qos)
        self.connected = True
        self._tf_name = self.declare_parameter('tf_prefix', '').value
        self.initialized = True
        self.joint_state_pub = self.create_publisher(
            sensor_msgs.msg.JointState, 'joint_states_p', 1)
        self.tf_broadcaster = tf2_ros.transform_broadcaster.TransformBroadcaster(self)
        available_modules = get_modules(self.constrained_s1_sdk)
        requested_modules = {
            name for name in ALL_MODULE_NAMES if self.enabled(name)
        }
        enabled_modules = {
            name: module
            for name, module in available_modules.items()
            if name in requested_modules
        }
        if self.constrained_s1_sdk:
            skipped = sorted(requested_modules - set(available_modules))
            for name in skipped:
                self.get_logger().warning(
                    f"Disabling {name}: not available from {self.sdk_backend} backend"
                )
        self.modules = {
            name: module(self.ep_robot, self)
            for name, module in enabled_modules.items()
        }
        module_string = ', '.join(type(module).__name__ for module in self.modules.values())
        self.get_logger().info(f"Enabled modules: {module_string}")
        self.connected_pub.publish(std_msgs.msg.Bool(data=True))
        self.start_heartbeat_check()

    def __del__(self) -> None:
        self.stop()

    def start_heartbeat_check(self) -> None:
        if self.constrained_s1_sdk:
            # These backends own their direct connection/watchdog and do not
            # expose the official private _client heartbeat.
            return
        self.heartbeat_check_timer = self.create_timer(5, self.heartbeat_check)
        self.heartbeat_handler = robomaster.client.MsgHandler(
            proto_data=robomaster.protocol.ProtoSdkHeartBeat(),
            ack_cb=lambda _, msg: self.got_heart_beat(msg))
        self.ep_robot._client.add_msg_handler(self.heartbeat_handler)

    def stop_heartbeat_check(self) -> None:
        if self.heartbeat_check_timer:
            self.heartbeat_check_timer.cancel()

    def abort(self) -> None:
        if self.initialized:
            self.get_logger().info("Will abort any action")
            for _, module in self.modules.items():
                module.abort()

    def stop(self) -> None:
        if self.initialized:
            self.get_logger().info("Will stop client")
            self.stop_heartbeat_check()
            for _, module in self.modules.items():
                # self.get_logger().info(f"Will stop module {module}")
                module.stop()
                # self.get_logger().info(f"Stopped module {module}")
            time.sleep(0.5)
            if not self.connected and not self.constrained_s1_sdk:
                self.ep_robot._client.stop()
            if self.lab_sdk and self.lab_bridge_started:
                # close() tears down the bridge and lab mode but not the
                # in-robot program; stop it explicitly first.
                try:
                    self.ep_robot.stop_lab_bridge()
                    self.ep_robot.stop_lab_program()
                except Exception as exc:
                    self.get_logger().warning(f"Error while stopping lab program: {exc}")
                self.lab_bridge_started = False
            self.ep_robot.close()
            self.connected = False
            self.connected_pub.publish(std_msgs.msg.Bool(data=False))
            self.initialized = False
            self.get_logger().info("Has stopped client")

    def tf_frame(self, name: str) -> str:
        if self._tf_name:
            return f'{self._tf_name}/{name}'
        return name

    def enabled(self, name: str) -> bool:
        return self.declare_parameter(f"{name}.enabled", False).value

    def heartbeat_check(self) -> None:
        self.connected = False
        self.disconnection.set_result(False)
        self.get_logger().warning("Disconnected")

    def got_heart_beat(self, msg: Any) -> None:
        self.heartbeat_check_timer.reset()
