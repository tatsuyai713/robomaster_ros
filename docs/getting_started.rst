===============
Getting Started
===============

.. ros:currentnode:: RoboMasterROS
.. ros:currentpackage:: robomaster_ros

Switch on your Robomaster and connect your PC through
:doc:`one of three available interfaces <rm:python_sdk/connection>`:

USB
  connect using a USB cable to the intelligent controller (:ros:param:`conn_type` = ``"rndis"``)

Wi-Fi Access point
  move the slider on the intelligent controller to the back (:ros:param:`conn_type` = ``"ap"``)
  to make it starts its own access point.
  Connect your PC to it using the SSID and password printed on the top of the intelligent controller.

Wi-Fi Router
  move the slider on the intelligent controller to the front (:ros:param:`conn_type` = ``"sta"``)
  and connect your PC to a Wi-Fi router. To communicate the network SSID and password to the robot,
  you can use the Robomaster app or run :ros:exec:`connect`:

  .. code-block:: console

    $ ros2 run robomaster_ros connect <SSID> <PASSWORD>

  Point the robot's camera towards the QR code and press the small button near the intelligent controller slider.
  The robot will read the code and connect to the network.


You can check that a robot is available and ready to be connected by running :ros:exec:`discover`:

.. code-block:: console

  $ ros2 run robomaster_ros discover
  [INFO] [1658231475.202434272] [discover]: Discovered 1 robots
  [INFO] [1658231476.378546964] [discover]: Connected to robot XXXXXXXXXXXXXX at 192.168.1.136: version 01.01.1131, battery 20%

The command will list the robots, which will beep and blink their LEDs.


You are ready to start controlling the robot through ROS:

.. code-block:: console

  $ ros2 launch robomaster_ros main.launch model:=<ep|s1>

Pick your robot type in ``model:=<ep|s1>`` to publish the correct URDF model and enable the appropriate modules.

S1 teleoperation
----------------

Build and source the workspace, start the S1 driver as usual, and then start one
of the teleoperation nodes below. Both publish ``cmd_vel`` and
``cmd_gimbal`` in the selected namespace.

For a PS5 DualSense controller (USB or Bluetooth)::

  ros2 launch robomaster_ros s1_joy.launch device_id:=0

The DualSense uses SDL's standard mapping: the left stick translates the
chassis, the right stick controls gimbal yaw and pitch, L2 turns left, and R2
turns right. L2/R2 remain analog rather than becoming on/off buttons. To inspect
the controller and find its ``device_id`` use
``ros2 run joy joy_enumerate_devices``. This mapping is the same over USB and
Bluetooth.

For keyboard control, run the node directly in an interactive terminal::

  ros2 run robomaster_ros s1_teleop --ros-args \
    -p use_joy:=false -p use_keyboard:=true

The keys follow the RoboMaster app's keyboard layout: W/A/S/D move
forward/left/back/right and Shift plus a movement key accelerates. Because a
terminal cannot report a standalone Shift key, Space toggles boost as a
convenience. Arrow keys control the gimbal, Q/E rotate the chassis, and X stops
immediately. Commands stop automatically when key repeats or joystick messages
cease.

Useful parameters are ``linear_speed`` (m/s), ``angular_speed`` (rad/s),
``gimbal_speed`` (rad/s), ``deadzone``, and ``boost_multiplier``. Most SDL
controllers report an unpressed trigger as -1; set
``trigger_released_value:=1.0`` if yours reports +1.
