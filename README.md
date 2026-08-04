Robomaster-ROS
==============

This repository contains a ROS2 driver for the DJI Robomaster family of robots (EP and S1) based on the [official Python client library](https://github.com/dji-sdk/RoboMaster-SDK).

Full documentation available at https://jeguzzi.github.io/robomaster_ros.

## RoboMaster S1 SOLO / LAB backends

This repository includes the SOLO SDK and LAB-SDK as the
`robomaster_s1_wifi_sdk` submodule. Clone recursively or initialize it before
installing a backend. Install the selected backend explicitly; the ROS package
does not install another `robomaster` package implicitly. Use separate virtual
environments: SOLO installs `SDK/` only; LAB installs its independent
`LAB-SDK/` package only. The SDK packages do not import or depend on each
other.

```bash
git submodule update --init --recursive
```

SOLO backend:

```bash
cd <ros2_ws>/src/robomaster_ros/robomaster_s1_wifi_sdk
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
cd <ros2_ws>/src/robomaster_ros/robomaster_s1_wifi_sdk
python3 -m pip uninstall -y robomaster robomaster-s1-wifi-sdk
python3 -m pip install ./LAB-SDK

cd <ros2_ws>
colcon build --packages-select robomaster_msgs robomaster_description robomaster_ros
source install/setup.bash
RM_ROBOT_IP=192.168.23.149 RM_APPID=b6359877 \
  ros2 launch robomaster_ros s1_lab.launch
```

The S1-specific launch files select the LAB or SOLO backend, request the
supported 720p video path, and disable modules that require EP hardware or
official-SDK private transports. Existing launch files continue to default to
the official backend. The lifecycle limitation below must be resolved before
using either S1-specific launch path.

> [!CAUTION]
> The current driver client is not yet aligned with the public lifecycle of
> either bundled S1 SDK. It passes an unsupported `enter_solo` keyword to the
> official-shaped `Robot.initialize()` method, and it does not call the LAB
> SDK's explicit enter/upload/program/bridge sequence. Consequently,
> `s1_solo.launch` and `s1_lab.launch` are not currently verified launch
> paths. SOLO integration must call `initialize()` and then `enter_solo()`;
> LAB integration must implement the lifecycle documented in the SDK
> submodule's `docs/lab-lifecycle.md`.

Both S1 launch files expose `audio`, `audio_raw`, `audio_opus`, and
`audio_level`. Their default is `2` (on demand), so subscribing to
`camera/audio_opus`, `camera/audio_raw`, or `camera/audio_level` starts the S1
audio request automatically. Use `audio:=1` to keep all audio topics active or
`audio:=-1` to disable them.

LAB-SDKの`Robot.initialize()`は接続だけを行います。Lab mode遷移、DSPのFTP
upload、MD5付きStart、Host bridge開始はそれぞれ明示的なAPIです。ROS clientを
対応させる際は、telemetry確認までをnode初期化の成功条件にし、終了時にbridge、
program、Lab mode、基礎接続を安全な順序で閉じる必要があります。

### ROS 2 backendの比較

ここでいう「公式SDK」は、このdriverが通常使用するDJI公式SDK互換backendを指します。
SOLO SDKとLAB-SDKはROS interfaceを可能な限り維持しますが、通信経路と取得元が異なります。

| 項目 | 公式SDK | SOLO `SDK/` | LAB-SDK |
|---|---|---|---|
| 選択 | `sdk_backend:=official` | `sdk_backend:=solo` | `sdk_backend:=lab` |
| Launch | `s1.launch` / `ep.launch` | `s1_solo.launch` | `s1_lab.launch` |
| 実行場所 | Host | Host | Host + S1 Python 3.6 DSP |
| 接続 | 公式SDK transport/private client | AppID claim + App互換SOLO/DUSS | AppID claim → Lab切替 → FTP/DSP → Start → telemetry応答確認 + UDP `40923/40924` |
| `cmd_vel` | 公式`drive_speed()` | 直接control payloadを50 Hz保持 | ROS messageごとにLab `move_with_speed()`を1回設定し、次の指令まで保持 |
| telemetry | 公式SDK内部配信層 | App/DUSS packetの実測decode | Lab controller getterの実測値 |
| IMU / ESC / status | 対応 | 未解析のため無効 | getterがないため無効 |
| Action | progress/完了push/cancel | 距離・角度Action未対応 | command投入互換。progress/cancel非対応 |
| Video/audio | 公式LiveView | raw H.264、Opus、48 kHz mono PCM | raw H.264、Opus、48 kHz mono PCM |
| Heartbeat | 公式private `_client` | 直接SDK receive loop/SOLO keepalive | Host bridge sessionと明示stop |
| 対応module | 機体構成に応じる | armor、battery、blaster、camera、chassis、gimbal、LED | 同左 |

公式SDKのmodule名`robomaster.dds`は、機体から購読したtelemetryをcallbackへ配るSDK内部層です。
ROS 2の通信middlewareであるDDSそのものではなく、別SDKを意味しません。
その受信telemetry queueは制御command queueではありません。公式SDKの通常commandは即時socket送信です。
LAB-SDKは各commandを有界queueへ順番に1回投入し、機体側Lab controllerが次の速度指令またはstopまで速度を保持します。

#### ROS module対応表

| module | 公式SDK | SOLO | LAB-SDK | 制約 |
|---|---:|---:|---:|---|
| chassis | 有効 | 有効 | 有効 | SOLOは速度/wheelのみ。LABは距離commandも部分対応。両方IMU/ESC/status無効 |
| gimbal | 有効 | 有効 | 有効 | SOLOは速度のみ。LABは角度commandも部分対応 |
| camera | 有効 | 有効 | 有効 | SOLO/LABはraw H.264、Opus topic、48 kHz mono PCM/audio level |
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
