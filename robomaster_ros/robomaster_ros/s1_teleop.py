# Copyright 2026 RoboMaster ROS contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Joystick and keyboard teleoperation for the RoboMaster S1."""

import math
import os
import select
import sys
import termios
import time
import tty
from typing import Dict, Optional, Sequence, Tuple

from geometry_msgs.msg import Twist

import rclpy
from rclpy.node import Node

from robomaster_msgs.msg import BlasterLED, GimbalCommand

from sensor_msgs.msg import Joy

from std_msgs.msg import Empty

try:
    import evdev
except ImportError:
    evdev = None


def deadzone(value: float, threshold: float) -> float:
    """Remove a deadzone while preserving the full output range."""
    if abs(value) <= threshold:
        return 0.0
    return math.copysign((abs(value) - threshold) / (1.0 - threshold), value)


def trigger(value: float, released_value: float = -1.0) -> float:
    """Convert a trigger axis to 0 (released) .. 1 (pressed)."""
    if released_value < 0.0:
        return min(1.0, max(0.0, (value + 1.0) * 0.5))
    return min(1.0, max(0.0, 1.0 - value))


def joy_commands(
    axes: Sequence[float],
    linear_speed: float,
    angular_speed: float,
    gimbal_speed: float,
    axis_deadzone: float,
    trigger_released_value: float = -1.0,
) -> Tuple[Tuple[float, float, float], Tuple[float, float]]:
    """Map SDL game-controller axes to chassis and gimbal commands."""
    padded = list(axes[:6]) + [0.0] * max(0, 6 - len(axes))
    left_x, left_y, right_x, right_y, left_trigger, right_trigger = padded[:6]
    vx = -deadzone(left_y, axis_deadzone) * linear_speed
    vy = -deadzone(left_x, axis_deadzone) * linear_speed
    turn = (
        trigger(left_trigger, trigger_released_value)
        - trigger(right_trigger, trigger_released_value)
    ) * angular_speed
    yaw = deadzone(right_x, axis_deadzone) * gimbal_speed
    pitch = deadzone(right_y, axis_deadzone) * gimbal_speed
    return (vx, vy, turn), (yaw, pitch)


class TerminalKeyboard:
    """Non-blocking raw terminal reader which restores the terminal on exit."""

    def __init__(self) -> None:
        """Put stdin into non-blocking character mode when it is a terminal."""
        self.fd: Optional[int] = None
        self.settings = None
        if sys.stdin.isatty():
            self.fd = sys.stdin.fileno()
            self.settings = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)

    def read(self) -> str:
        """Return one key name without blocking."""
        if self.fd is None or not select.select([self.fd], [], [], 0.0)[0]:
            return ''
        data = os.read(self.fd, 1).decode(errors='ignore')
        if data == '\x1b':
            # Arrow keys arrive as a three-byte escape sequence. Read only
            # that sequence so repeated arrows cannot be mistaken for WASD.
            deadline = time.monotonic() + 0.02
            while len(data) < 3 and time.monotonic() < deadline:
                if select.select([self.fd], [], [], 0.002)[0]:
                    data += os.read(self.fd, 1).decode(errors='ignore')
        arrows = {
            '\x1b[A': 'UP',
            '\x1b[B': 'DOWN',
            '\x1b[C': 'RIGHT',
            '\x1b[D': 'LEFT',
        }
        return arrows.get(data, data[-1:] if data else '')

    def close(self) -> None:
        """Restore the original terminal settings."""
        if self.fd is not None and self.settings is not None:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.settings)
            self.fd = None


class EvdevKeyboard:
    """Read simultaneous Linux keyboard press and release events."""

    KEY_NAMES = {
        'KEY_W': 'W', 'KEY_A': 'A', 'KEY_S': 'S', 'KEY_D': 'D',
        'KEY_Q': 'Q', 'KEY_E': 'E', 'KEY_UP': 'UP', 'KEY_DOWN': 'DOWN',
        'KEY_LEFT': 'LEFT', 'KEY_RIGHT': 'RIGHT', 'KEY_F': 'F',
        'KEY_L': 'L', 'KEY_X': 'X', 'KEY_SPACE': 'SPACE',
        'KEY_LEFTSHIFT': 'SHIFT', 'KEY_RIGHTSHIFT': 'SHIFT',
    }

    def __init__(self, path: str = '') -> None:
        """Open an explicit keyboard, or find a keyboard automatically."""
        self.device = None
        if evdev is None:
            return
        paths = [path] if path else evdev.list_devices()
        for candidate in paths:
            try:
                device = evdev.InputDevice(candidate)
                keys = device.capabilities().get(evdev.ecodes.EV_KEY, [])
                if path or (evdev.ecodes.KEY_W in keys
                            and evdev.ecodes.KEY_UP in keys):
                    self.device = device
                    break
                device.close()
            except (OSError, PermissionError):
                continue

    @property
    def fd(self) -> Optional[int]:
        """Return the input file descriptor when a keyboard is open."""
        return self.device.fd if self.device is not None else None

    def read_events(self) -> Sequence[Tuple[str, int]]:
        """Return all pending mapped key events as (name, state)."""
        if self.device is None or not select.select(
                [self.device.fd], [], [], 0.0)[0]:
            return ()
        result = []
        try:
            for event in self.device.read():
                if event.type != evdev.ecodes.EV_KEY:
                    continue
                name = evdev.ecodes.KEY.get(event.code, '')
                mapped = self.KEY_NAMES.get(name)
                if mapped:
                    result.append((mapped, event.value))
        except BlockingIOError:
            pass
        return result

    def close(self) -> None:
        """Close the Linux input device."""
        if self.device is not None:
            self.device.close()
            self.device = None


class S1Teleop(Node):
    """Publish S1 chassis and gimbal commands from Joy and/or a terminal."""

    def __init__(self) -> None:
        """Configure input subscriptions, command publishers, and watchdog."""
        super().__init__('s1_teleop')
        self.linear_speed = float(
            self.declare_parameter('linear_speed', 1.5).value)
        self.angular_speed = float(
            self.declare_parameter('angular_speed', 2.0).value)
        self.gimbal_speed = float(
            self.declare_parameter('gimbal_speed', 3.0).value)
        self.boost_multiplier = float(
            self.declare_parameter('boost_multiplier', 1.5).value)
        self.axis_deadzone = float(
            self.declare_parameter('deadzone', 0.08).value)
        self.trigger_released = float(
            self.declare_parameter('trigger_released_value', -1.0).value)
        self.joy_timeout = float(
            self.declare_parameter('joy_timeout', 0.3).value)
        self.key_timeout = float(
            self.declare_parameter('key_timeout', 0.10).value)
        self.fire_cooldown = float(
            self.declare_parameter('fire_cooldown', 0.25).value)
        use_joy = bool(self.declare_parameter('use_joy', True).value)
        use_keyboard = bool(
            self.declare_parameter('use_keyboard', False).value)
        keyboard_device = str(
            self.declare_parameter('keyboard_device', '').value)

        self.cmd_vel_pub = self.create_publisher(Twist, 'cmd_vel', 1)
        self.gimbal_pub = self.create_publisher(GimbalCommand, 'cmd_gimbal', 1)
        self.blaster_led_pub = self.create_publisher(
            BlasterLED, 'blaster_led', 1)
        self.fire_pub = self.create_publisher(Empty, 'blaster/fire_ir', 1)
        self.last_joy = 0.0
        self.joy_chassis = (0.0, 0.0, 0.0)
        self.joy_gimbal = (0.0, 0.0)
        self.keys: Dict[str, float] = {}
        self.evdev_keyboard = (
            EvdevKeyboard(keyboard_device) if use_keyboard else None)
        self.keyboard = None
        if use_keyboard and (
                self.evdev_keyboard is None
                or self.evdev_keyboard.fd is None):
            self.keyboard = TerminalKeyboard()
        self.boost = False
        self.boost_until = 0.0
        self.last_fire = 0.0
        self.last_led_key = 0.0
        self.blaster_led_on = False
        self.l1_pressed = False
        self.r1_pressed = False
        if use_joy:
            self.create_subscription(Joy, 'joy', self.on_joy, 10)
        if use_keyboard and self.evdev_keyboard is not None:
            if self.evdev_keyboard.fd is not None:
                self.get_logger().info(
                    'Using Linux input keyboard with simultaneous key support')
            elif self.keyboard is not None and self.keyboard.fd is None:
                self.get_logger().warning(
                    'No readable keyboard input device or '
                    'interactive terminal')
        elif use_keyboard:
            self.get_logger().warning(
                'Keyboard input is unavailable')
        self.create_timer(0.02, self.update)
        self.get_logger().info(
            'S1 teleop ready: WASD=chassis, arrows=gimbal, '
            'Space=boost, L/L1=blaster LED, F/R1=IR blaster, X=stop')

    def on_joy(self, msg: Joy) -> None:
        """Convert the latest DualSense state into target speeds."""
        self.joy_chassis, self.joy_gimbal = joy_commands(
            msg.axes, self.linear_speed, self.angular_speed, self.gimbal_speed,
            self.axis_deadzone, self.trigger_released)
        self.last_joy = time.monotonic()
        l1_pressed = len(msg.buttons) > 9 and bool(msg.buttons[9])
        if l1_pressed and not self.l1_pressed:
            self.toggle_blaster_led()
        self.l1_pressed = l1_pressed
        r1_pressed = len(msg.buttons) > 10 and bool(msg.buttons[10])
        if r1_pressed and not self.r1_pressed:
            self.fire_ir(self.last_joy)
        self.r1_pressed = r1_pressed

    def fire_ir(self, now: float) -> None:
        """Fire one infrared beam with repeat/debounce protection."""
        if now - self.last_fire < self.fire_cooldown:
            return
        self.fire_pub.publish(Empty())
        self.last_fire = now

    def toggle_blaster_led(self) -> None:
        """Toggle the blaster LED between off and full brightness."""
        self.blaster_led_on = not self.blaster_led_on
        msg = BlasterLED()
        msg.brightness = 1.0 if self.blaster_led_on else 0.0
        self.blaster_led_pub.publish(msg)

    def read_keyboard(self, now: float) -> None:
        """Update active keyboard commands from Linux input or the terminal."""
        if (self.evdev_keyboard is not None
                and self.evdev_keyboard.fd is not None):
            for key, state in self.evdev_keyboard.read_events():
                if key in ('W', 'A', 'S', 'D', 'Q', 'E', 'UP', 'DOWN',
                           'LEFT', 'RIGHT', 'SHIFT'):
                    if state:
                        self.keys[key] = math.inf
                    else:
                        self.keys.pop(key, None)
                elif state == 1:
                    self.handle_action_key(key, now)
            return
        if self.keyboard is None:
            return
        key = self.keyboard.read()
        if not key:
            return
        self.handle_action_key(
            'SPACE' if key == ' ' else key.upper(), now)

    def handle_action_key(self, key: str, now: float) -> None:
        """Handle a terminal key or an evdev key-press action."""
        if key == 'SPACE':
            self.boost = not self.boost
        elif key == 'L':
            if now - self.last_led_key > self.key_timeout:
                self.toggle_blaster_led()
            self.last_led_key = now
        elif key == 'F':
            self.fire_ir(now)
        elif key == 'X':
            self.keys.clear()
            self.last_joy = 0.0
            self.joy_chassis = (0.0, 0.0, 0.0)
            self.joy_gimbal = (0.0, 0.0)
        elif (key in ('UP', 'DOWN', 'LEFT', 'RIGHT')
              or key.lower() in 'wasdqe'):
            self.keys[key] = now
            if key.isupper() and key.lower() in 'wasd':
                self.boost_until = now + self.key_timeout

    def keyboard_commands(
        self, now: float
    ) -> Tuple[Tuple[float, float, float], Tuple[float, float]]:
        """Build chassis and gimbal commands from non-expired keys."""
        active = {key for key, stamp in self.keys.items()
                  if stamp == math.inf or now - stamp <= self.key_timeout}
        self.keys = {
            key: stamp for key, stamp in self.keys.items() if key in active}
        boosted = self.boost or 'SHIFT' in active or now < self.boost_until
        scale = self.boost_multiplier if boosted else 1.0
        vx = (
            ('W' in active) - ('S' in active)) * self.linear_speed * scale
        vy = (
            ('A' in active) - ('D' in active)) * self.linear_speed * scale
        turn = (('Q' in active) - ('E' in active)) * self.angular_speed
        yaw = (('RIGHT' in active) - ('LEFT' in active)) * self.gimbal_speed
        pitch = (('DOWN' in active) - ('UP' in active)) * self.gimbal_speed
        return (vx, vy, turn), (yaw, pitch)

    def publish(
        self, chassis: Tuple[float, float, float], gimbal: Tuple[float, float]
    ) -> None:
        """Publish one chassis and gimbal command pair."""
        twist = Twist()
        twist.linear.x, twist.linear.y, twist.angular.z = chassis
        command = GimbalCommand()
        command.yaw_speed, command.pitch_speed = gimbal
        self.cmd_vel_pub.publish(twist)
        self.gimbal_pub.publish(command)

    def update(self) -> None:
        """Publish active input or a watchdog stop at 50 Hz."""
        now = time.monotonic()
        self.read_keyboard(now)
        keyboard_chassis, keyboard_gimbal = self.keyboard_commands(now)
        if any(keyboard_chassis) or any(keyboard_gimbal):
            self.publish(keyboard_chassis, keyboard_gimbal)
        elif now - self.last_joy <= self.joy_timeout:
            self.publish(self.joy_chassis, self.joy_gimbal)
        else:
            self.publish((0.0, 0.0, 0.0), (0.0, 0.0))

    def destroy_node(self) -> bool:
        """Stop the robot and restore stdin before shutting down."""
        self.publish((0.0, 0.0, 0.0), (0.0, 0.0))
        if self.evdev_keyboard is not None:
            self.evdev_keyboard.close()
        if self.keyboard is not None:
            self.keyboard.close()
        return super().destroy_node()


def main(args=None) -> None:
    """Run the S1 teleoperation node."""
    rclpy.init(args=args)
    node = S1Teleop()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
