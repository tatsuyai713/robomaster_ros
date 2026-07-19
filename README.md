Robomaster-ROS
==============

This repository contains a ROS2 driver for the DJI Robomaster family of robots (EP and S1) based on the [official Python client library](https://github.com/dji-sdk/RoboMaster-SDK).

Full documentation available at https://jeguzzi.github.io/robomaster_ros.

## RoboMaster S1 LAB-SDK backend

This copy can use the LAB-SDK bundled with the parent
`RoboMaster-S1-WiFi-SDK` repository. Install the selected backend explicitly;
the ROS package does not install another `robomaster` package implicitly.

```bash
cd /path/to/RoboMaster-S1-WiFi-SDK
python3 -m pip uninstall -y robomaster
python3 -m pip install ./SDK
python3 -m pip install --no-deps ./LAB-SDK

cd <ros2_ws>
colcon build --packages-select robomaster_msgs robomaster_description robomaster_ros
source install/setup.bash
RM_ROBOT_IP=192.168.23.149 RM_APPID=b6359877 \
  ros2 launch robomaster_ros s1_lab.launch
```

The LAB launch uses the 50 Hz S1 Lab DSP bridge, selects the supported 720p
video path, and disables modules that require EP hardware or official-SDK
private transports. Existing launch files continue to default to the official
backend.

### ROS 2における公式SDK backendとの比較

ここでいう「公式SDK」は、このdriverが通常使用するDJI公式SDK互換backendを指します。
LAB-SDKはROS interfaceを可能な限り維持しますが、通信経路とS1 Lab runtimeで取得できる情報が異なります。

| 項目 | 公式SDK backend | LAB-SDK backend |
|---|---|---|
| 選択方法 | `sdk_backend:=official`。既存launchのdefault | `sdk_backend:=lab`。`s1_lab.launch`で設定済み |
| 対象robot | S1 / EP | S1のみ |
| Python実行場所 | Host上の公式SDK | Host SDK + S1機体内Python 3.6 DSP |
| 接続 | 公式connection discovery、SDK transport、private client | Windows App互換Wi-Fi/AppID接続、FTPによるDSP upload、UDP `40923`/`40924` |
| `cmd_vel` | 公式`chassis.drive_speed()`へ変換 | Lab `chassis_ctrl.move_with_speed()`へ変換。移動中は最新stateを50 Hz更新 |
| command送信 | 通常commandはsocketへ即時送信。Actionは実行中targetを管理し、同一targetの重複を拒否 | motionはcapacity 1のlatest-only、独立stopはcapacity 8のpriority FIFO、単発commandはcapacity 32の有界FIFO |
| 通信断時停止 | 公式SDKとdriver heartbeat/disconnection処理 | Host更新停止後に機体側watchdogが速度を減衰して停止 |
| Position | 公式SDK内部telemetry配信層の`sub_position()` | `get_position_based_power_on()`による実測X/Y |
| Velocity | 公式SDK内部telemetry配信層の`sub_velocity()` | `get_speed()`による実測forward/translation速度 |
| Attitude | 公式SDK内部telemetry配信層のattitude | `get_attitude(chassis_yaw)`によるyawのみ。pitch/rollは`None` |
| IMU / ESC / status | 公式SDK内部telemetry配信層で購読 | stock S1 Lab commandにgetterがないため購読しない |
| Telemetry rate | 公式SDK購読APIの対応frequency | 購読fieldだけを1/5/10/20/50 Hzでgetter取得。未購読getterは停止 |
| Gimbal angle | 公式SDK内部telemetry配信層 | `get_axis_angle()`によるpitch/yaw。ground angleは`None` |
| Gimbal/Chassis Action | 公式Action progress、完了push、abort/cancel | Lab command投入結果をAction互換objectで返す。実動作progress/cancel通知は非対応 |
| Video | 公式LiveView、launchで解像度/protocol選択 | 親projectのApp互換raw streamをLiveView facadeへ接続。LAB launchは720p |
| Audio受信 | 公式LiveView | 親projectのApp互換audio受信経路 |
| Speaker再生 | 公式speaker module | stock S1 Lab制約のため`S1 Lab` launchでは無効 |
| Heartbeat | 公式private `_client` heartbeat | private APIを呼ばず、LAB bridge watchdogを使用 |
| Reconnect | 公式clientのdisconnection/heartbeatを利用 | private client再接続とは非互換。bridge/DSP再起動が必要になる場合がある |

公式SDKのmodule名`robomaster.dds`は、機体から購読したtelemetryをcallbackへ配るSDK内部層です。
ROS 2の通信middlewareであるDDSそのものではなく、別SDKを意味しません。
その受信telemetry queueは制御command queueではありません。公式SDKの通常commandは即時socket送信であり、
LAB-SDKのlatest-only motionは追加のprocess間・UDP bridgeで古い速度を後から再生しないための差です。

#### ROS module対応表

| `robomaster_ros` module | 公式SDK | LAB-SDK | LAB-SDKでの扱い |
|---|---:|---:|---|
| `chassis` | 有効 | 有効 | position/velocity/yawと速度・距離・回転command。IMU/ESC/status/engageは無効 |
| `gimbal` | 有効 | 有効 | 公開`move()`/`moveto()`/`drive_speed()`経路を使用 |
| `camera` | 有効 | 有効 | App互換video/audio raw stream |
| `battery` | 有効 | 有効 | percentは実測。他の公式battery tuple要素は取得不能のため0 |
| `armor` | 有効 | 有効 | 基礎Wi-Fi/DUSS経路のhit event |
| `blaster` | 有効 | 有効 | S1 Labで利用可能なIR/physical fire mapping |
| `led` | 有効 | 有効 | Lab公開`set_led()`へ変換。mask/effectの一部は近似mapping |
| `speaker` | 有効 | 無効 | `s1_lab.launch`で無効 |
| `arm` / `gripper` | EPで有効 | 無効 | EP hardwareかつstock S1 Lab対象外 |
| `servo` / `tof` / `uart` / `sensor_adapter` | 構成により有効 | 無効 | stock S1 Lab commandだけではROS data sourceを満たせない |
| `pwm` / `sbus` / `vision` | 構成により有効 | 無効 | LAB backendのROS module allowlist外 |

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
