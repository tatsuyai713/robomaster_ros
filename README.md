Robomaster-ROS
==============

This repository contains a ROS2 driver for the DJI Robomaster family of robots (EP and S1) based on the [official Python client library](https://github.com/dji-sdk/RoboMaster-SDK).

Full documentation available at https://jeguzzi.github.io/robomaster_ros.

## RoboMaster S1 SOLO / LAB backends

This copy can use the SOLO SDK or LAB-SDK bundled with the parent
`RoboMaster-S1-WiFi-SDK` repository. Install the selected backend explicitly;
the ROS package does not install another `robomaster` package implicitly. Use
separate virtual environments: SOLO installs `SDK/` only; LAB installs its
base transport dependency `SDK/` first and the LAB facade last.

SOLO backend:

```bash
cd /path/to/RoboMaster-S1-WiFi-SDK
python3 -m pip uninstall -y robomaster robomaster-s1-lab-sdk
python3 -m pip install ./SDK

cd <ros2_ws>
colcon build --packages-select robomaster_msgs robomaster_description robomaster_ros
source install/setup.bash
RM_ROBOT_IP=192.168.23.149 RM_APPID=b6359877 \
  ros2 launch robomaster_ros s1_solo.launch
```

LAB backend:

```bash
cd /path/to/RoboMaster-S1-WiFi-SDK
python3 -m pip uninstall -y robomaster robomaster-s1-wifi-sdk
python3 -m pip install ./SDK
python3 -m pip install --no-deps ./LAB-SDK

cd <ros2_ws>
colcon build --packages-select robomaster_msgs robomaster_description robomaster_ros
source install/setup.bash
RM_ROBOT_IP=192.168.23.149 RM_APPID=b6359877 \
  ros2 launch robomaster_ros s1_lab.launch
```

The LAB launch uses the 50 Hz S1 Lab DSP bridge. The SOLO launch uses the
host-side S1 Windows App-compatible SDK and enters SOLO mode without a DSP.
Both select the supported 720p video path and disable modules that require EP
hardware or official-SDK private transports. Existing launch files continue to
default to the official backend.

### ROS 2 backendの比較

ここでいう「公式SDK」は、このdriverが通常使用するDJI公式SDK互換backendを指します。
SOLO SDKとLAB-SDKはROS interfaceを可能な限り維持しますが、通信経路と取得元が異なります。

| 項目 | 公式SDK | SOLO `SDK/` | LAB-SDK |
|---|---|---|---|
| 選択 | `sdk_backend:=official` | `sdk_backend:=solo` | `sdk_backend:=lab` |
| Launch | `s1.launch` / `ep.launch` | `s1_solo.launch` | `s1_lab.launch` |
| 実行場所 | Host | Host | Host + S1 Python 3.6 DSP |
| 接続 | 公式SDK transport/private client | AppID claim + App互換SOLO/DUSS | AppID claim + FTP/DSP + UDP `40923/40924` |
| `cmd_vel` | 公式`drive_speed()` | 直接control payloadを50 Hz保持 | Lab `move_with_speed()`を50 Hz更新 |
| telemetry | 公式SDK内部配信層 | App/DUSS packetの実測decode | Lab controller getterの実測値 |
| IMU / ESC / status | 対応 | 未解析のため無効 | getterがないため無効 |
| Action | progress/完了push/cancel | 距離・角度Action未対応 | command投入互換。progress/cancel非対応 |
| Video/audio | 公式LiveView | App互換raw stream | App互換raw stream |
| Heartbeat | 公式private `_client` | 直接SDK receive loop/SOLO keepalive | bridge watchdog |
| 対応module | 機体構成に応じる | armor、battery、blaster、camera、chassis、gimbal、LED | 同左 |

公式SDKのmodule名`robomaster.dds`は、機体から購読したtelemetryをcallbackへ配るSDK内部層です。
ROS 2の通信middlewareであるDDSそのものではなく、別SDKを意味しません。
その受信telemetry queueは制御command queueではありません。公式SDKの通常commandは即時socket送信であり、
LAB-SDKのlatest-only motionは追加のprocess間・UDP bridgeで古い速度を後から再生しないための差です。

#### ROS module対応表

| module | 公式SDK | SOLO | LAB-SDK | 制約 |
|---|---:|---:|---:|---|
| chassis | 有効 | 有効 | 有効 | SOLOは速度/wheelのみ。LABは距離commandも部分対応。両方IMU/ESC/status無効 |
| gimbal | 有効 | 有効 | 有効 | SOLOは速度のみ。LABは角度commandも部分対応 |
| camera | 有効 | 有効 | 有効 | SOLO/LABはApp互換raw video/audio |
| battery | 有効 | 有効 | 有効 | percent実測、未取得tuple要素は0 |
| armor | 有効 | 有効 | 有効 | SOLOでは感度設定未対応 |
| blaster / LED | 有効 | 有効 | 有効 | component/effectの一部を近似mapping |
| speaker / EP拡張 | 構成依存 | 無効 | 無効 | 対応するhardware/解析済みcommandがない |

対応moduleでは既存ROS topic/action名を維持します。取得元が存在しないaxisや状態を0・積分・推定値で
補完せず、購読しないか`None`として扱います。そのため、公式SDK backendを前提としたnodeが
IMU、ESC、status、Action progressを必須とする場合は、そのままLAB-SDKへ切り替えられません。


## Installation

### Pre-requisites

#### ROS2

Install a currently supported version of ROS2 (foxy -- lyrical), following the [official instructions](https://docs.ros.org/en/galactic/Installation.html).
and then install colcon
```bash
sudo apt install python3-colcon-common-extensions
```

If you just install ROS2-base, add also the following packages:
```
xacro, launch-xml, cv-bridge, launch-testing-ament-cmake, robot-state-publisher, joint-state-publisher-gui, joy, joy-teleop
```
```bash
sudo apt install \
  ros-<ROS_DISTRO>-xacro \
  ros-<ROS_DISTRO>-launch-xml \
  ros-<ROS_DISTRO>-cv-bridge \
  ros-<ROS_DISTRO>-launch-testing-ament-cmake \
  ros-<ROS_DISTRO>-robot-state-publisher \
  ros-<ROS_DISTRO>-joint-state-publisher \
  ros-<ROS_DISTRO>-joint-state-publisher-gui \
  ros-<ROS_DISTRO>-joy \
  ros-<ROS_DISTRO>-joy-teleop \
  ros-<ROS_DISTRO>-joy-linux
```

#### Robomaster SDK

Install [this fork](https://github.com/jeguzzi/RoboMaster-SDK) of the official RoboMaster-SDK, which fixes some issues of  the upstream repo.

First install its dependencies `libopus-dev`
```bash
sudo apt install libopus-dev python3-pip
```
and
```bash
python3 -m pip install -U numpy numpy-quaternion pyyaml
```
then install the RoboMaster-SDK

- For Python < 3.11:

  ```bash
  python3 -m pip install git+https://github.com/jeguzzi/  RoboMaster-SDK.git
  python3 -m pip install git+https://github.com/jeguzzi/RoboMaster-SDK.git#"egg=rm_libmedia_codec&subdirectory=lib/libmedia_codec"
  ```

- For Python >= 3.11:

  ```bash
  python3 -m pip install git+https://github.com/jeguzzi/  RoboMaster-SDK.git
  python3 -m pip install -i https://test.pypi.org/simple/   rm-libmedia-codec
  ```

### ROS2 package

Create a `colcon` package where you want to build the packages, clone this repository, and built the packages.
```
mkdir -p <ros2_ws>/src
git clone https://github.com/jeguzzi/robomaster_ros.git
cd <ros2_ws>
source /opt/ros/<ROS_DISTRO>/setup.bash
colcon build
```

## Usage

Use one of the two launch files `{s1|ep}.launch` to launch the driver and the robot model.
```bash
cd <ros2_ws>
source install/setup.bash
ros2 launch robomaster_ros {s1|ep}.launch
```

We also provide docker images. Check [the documentation](docker.md) for their usage.

### Arguments

The launch files accept a list of arguments
```bash
ros2 launch robomaster_ros {s1|ep}.launch <key_1>:=<value_1> <key_2>:=<value_2> ...
```


#### Common Configurations

The two different robot models share some configuration.

| key              | type    | valid values              | default | description                                                                                           |
| ---------------- | ------- | ------------------------- | ------- | ----------------------------------------------------------------------------------------------------- |
| name             | string  | valid ROS names           | ''      | a name used as ROS namespace                                                                          |
| serial_number    | string  | 8 character ascii strings | ''      | the serial number of the robot, leave empty to connect to the first robot found                             |
| conn_type        | string  | ap, rndis, sta            | sta     | the connection network type: managed/router (sta); robot's access point (ap); usb (rndis)             |
| lib_log_level    | string  | DEBUG, INFO, WARN, ERROR  | ERROR   | the log-level used by the internal Robomaster API                                                     |
| video_resolution | integer | 360, 540, 720             | 360     | the video [vertical] resolution: 640x360 (360);  960x540 (540);    1280x720 (720)                     |
| video_raw        | bool    |                           | true    | whether to publish the raw [decompressed] images to the topic `<name>/camera/image_raw`               |
| video_h264       | bool    |                           | false   | whether to publish the original h264 video stream to the topic `<name>/camera/image_h264`             |
| video_compressed | bool    |                           | false   | whether to publish the compressed [jpeg] images to the topic `<name>/camera/image_raw/compressed`         |
| audio_raw        | bool    |                           | true    | whether to publish the raw [decompressed] audio to the topic `<name>/camera/audio_raw`                    |
| audio_opus       | bool    | | true                      |          whether to publish the original [compressed] opus audio stream to the topic `<name>/camera/audio_opus` |
| chassis_rate     | int     | 1, 5, 10, 20, 50          | 10      | the rate [Hz] at which to publish the odometry                                                                 |
| joint_state_rate | int     | 1, 5, 10, 20, 50          | 10      | the rate [Hz] at which to publish aggregated joint states                                                      |
| sensor_adapter   | bool    |                           | false   | Whether at least one sensor adapter (IO) is connected and should be published to `<name>/...`         |
| sensor_adapter_rate                 | int        |  1, 5, 10, 20, 50                         |  10       | the rate [Hz] at which to publish the sensor adapter values                                       

#### S1-specific Configurations

Some configurations are specific for the Robomaster S1.

| key         | type    | valid values     | default | description                                       |
| ----------- | ------- | ---------------- | ------- | ------------------------------------------------- |
| gimbal_rate | integer | 1, 5, 10, 20, 50 | 10      | the rate [Hz] at which to gather the gimbal state |
|   display_battery          |  string     |  off, right, left |   off      |   whether and where to display the battery state: do not display (on); display on the right gimbal led (right); display on the left gimbal led (left)                                             |

#### EP-specific Configurations

Some configurations are specific for the Robomaster EP.

| key                   | type | valid values | default | description                                                                                                                |
| --------------------- | ---- | ------------ | ------- | -------------------------------------------------------------------------------------------------------------------------- |
| left_motor_zero       | int  |              | 1242    | the [arm] left servo motor encoder value at zero angle                                                                           |
| right_motor_zero      | int  |              | 1273    | the [arm] right servo motor encoder value at zero angle                                                                          |
| left_motor_direction  | int  | -1, 1        | -1      | the [arm] left servo motor direction: angle increases when encoder increases (+1);  angle decreases when encoder increases (-1)  |
| right_motor_direction | int  | -1, 1        | -1      | the [arm] right servo motor direction: angle increases when encoder increases (+1);  angle decreases when encoder increases (-1) |


### Multiple robots

If you want to control multiple robots through ROS, you need to know their serial numbers and set a different name for each of them (names are used as ROS namespaces and as `tf` prefixes). For physical robots, the serial number is written on top of the intelligent controller. For simulated robots, you set the serial number when you launch the simulation.

For example, we assume that you are using two [simulated] S1 robots with serial numbers `"RM0"` and `"RM1"`, and that you want to use the serial numbers also as names. In two consoles, launch
```bash
cd <ros2_ws>
source install/setup.bash
ros2 launch robomaster_ros s1.launch name:=RM0 serial_number:=RM0
```
and
```bash
cd <ros2_ws>
source install/setup.bash
ros2 launch robomaster_ros s1.launch name:=RM1 serial_number:=RM1
```
Then, for instance, you can make the robots spin in opposite direction by publishing to their respective topics:
```
ros2 topic pub /RM0/cmd_vel geometry_msgs/msg/Twist "{angular: {z: -0.5}}" --once
ros2 topic pub /RM1/cmd_vel geometry_msgs/msg/Twist "{angular: {z: 0.5}}" --once
```


### Thanks

This work has been supported by the European Commission through the Horizon 2020 project [1-SWARM](https://www.1-swarm.eu/), grant ID 871743.
