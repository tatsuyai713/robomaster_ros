# RoboMaster ROS 2

DJI RoboMaster S1／EP用のROS 2ドライバです。このforkは親リポジトリ
`RoboMaster-S1-WiFi-SDK`に含まれるS1用SOLO SDKとLAB-SDKに対応し、
PS5 DualSenseおよびキーボード用テレオペレーションノードを提供します。

> [!WARNING]
> 本プロジェクトはDJI公式ソフトウェアではありません。初回は車輪を床から浮かせ、
> 物理弾を抜き、停止指令が動作することを確認してください。

親リポジトリから導入する場合は、colconワークスペース作成から実機接続までを説明した
[ルートREADME](../README.md)も参照してください。

## パッケージ

| Package | 内容 |
|---|---|
| `robomaster_ros` | ドライバ、各機能module、launch、teleop |
| `robomaster_msgs` | 独自message、service、action |
| `robomaster_description` | S1／EPのURDF、mesh、model launch |

## 対応backend

| Backend | Launch | 制御経路 | 主な用途 |
|---|---|---|---|
| SOLO | `s1_solo.launch` | PCからS1へApp互換UDPを直接送信 | PS5、キーボード、速度制御、映像・音声 |
| LAB | `s1_lab.launch` | PCから機体内Lab bridgeを経由 | Lab API、距離・角度command |
| Official | `s1.launch` / `ep.launch` | DJI公式Python SDK | EPまたは公式SDK対応機 |

SOLO SDKとLAB-SDKはどちらも`robomaster`というPython packageを提供するため、
同じPython環境へ同時にインストールできません。

現在のドライバはbackendごとのlifecycleを処理します。

- SOLO: `initialize()`後に`enter_solo()`を実行
- LAB: Lab modeへ入り、bridgeを転送・起動
- LAB終了時: bridgeと機体programを停止してから接続を終了

## 対応機能

| 機能 | Official | SOLO | LAB |
|---|---:|---:|---:|
| シャーシ速度 | 対応 | 対応 | 対応 |
| 車輪速度 | 対応 | 対応 | 対応 |
| シャーシ距離・角度action | 対応 | 非対応 | 部分対応 |
| ジンバル速度 | 対応 | 対応 | 対応 |
| ジンバル角度action | 対応 | 非対応 | 部分対応 |
| バッテリー | 対応 | 対応 | 対応 |
| Armor、Blaster、LED | 対応 | 部分対応 | 部分対応 |
| H.264映像、Opus／PCM音声 | 対応 | 対応 | 対応 |
| IMU、ESC、Chassis status | 対応 | 非対応 | 非対応 |
| EP Arm、Gripper、Servo | 対応 | 対象外 | 対象外 |

SOLO／LABでは、取得元がないtelemetryを推定値で補完しません。該当moduleまたは
subscriptionは無効になります。

## 必要環境

- Ubuntu 22.04 + ROS 2 Humble、またはUbuntu 24.04 + ROS 2 Jazzy
- Python 3.10以降
- `colcon`
- S1と相互通信できるWi-Fi
- PS5を使う場合はROS 2 `joy` package

ROS 2をsourceします。

```bash
source /opt/ros/humble/setup.bash
```

Ubuntu 24.04では`humble`を`jazzy`へ変更してください。

依存パッケージをインストールします。

```bash
sudo apt update
sudo apt install -y \
  python3-colcon-common-extensions \
  python3-full \
  python3-venv \
  python3-pip \
  python3-evdev \
  python3-rosdep \
  libopus-dev \
  "ros-${ROS_DISTRO}-xacro" \
  "ros-${ROS_DISTRO}-launch-xml" \
  "ros-${ROS_DISTRO}-cv-bridge" \
  "ros-${ROS_DISTRO}-robot-state-publisher" \
  "ros-${ROS_DISTRO}-joint-state-publisher" \
  "ros-${ROS_DISTRO}-joy"
```

## 現在のcloneをcolcon workspaceとして使用

親リポジトリを別のworkspaceへ移動する必要はありません。以下では現在のclone先
`~/repos/RoboMaster-S1-WiFi-SDK`をそのまま使用します。

```bash
cd ~/repos/RoboMaster-S1-WiFi-SDK
git submodule update --init --recursive
```

別の場所へcloneしている場合は、パスを実際のclone先へ置き換えてください。

## SOLO用venvを作成してビルド

ROS 2 packageを参照できるvenvを作り、SOLO SDKとcolconをその中へインストールします。

```bash
cd ~/repos/RoboMaster-S1-WiFi-SDK
source "/opt/ros/${ROS_DISTRO}/setup.bash"
python3 -m venv --system-site-packages .venv-ros-solo
source .venv-ros-solo/bin/activate
python -m pip install --upgrade pip wheel
python -m pip install "setuptools<80"
python -m pip install ./SDK numpy-quaternion pyyaml
```

この方法ではシステムPythonへpip installしないため、Ubuntu 24.04のPEP 668エラーを
回避できます。

> [!IMPORTANT]
> `colcon build`を直接実行するとapt版colconのシステムPythonが使われます。
> 生成されたROS executableからvenv内の`robomaster`をimportできなくなるため、
> 必ず`python /usr/bin/colcon build ...`でvenvのPythonを明示します。

backendを確認します。

```bash
python -c \
  "import robomaster; print(robomaster.__file__); print(robomaster.IS_S1_WIFI_SDK)"
```

最後に`True`と表示されればSOLO backendです。

依存解決とSOLO専用directoryへのビルドを行います。

```bash
cd ~/repos/RoboMaster-S1-WiFi-SDK
rosdep install --from-paths robomaster_ros --ignore-src -r -y
python /usr/bin/colcon build --symlink-install \
  --build-base build-solo \
  --install-base install-solo \
  --packages-select robomaster_msgs robomaster_description robomaster_ros
source install-solo/setup.bash
```

packageを確認します。

```bash
ros2 pkg prefix robomaster_ros
ros2 pkg executables robomaster_ros
```

## LAB用venvを作成してビルド

LABはSOLOとは別のvenvとbuild/install directoryを使います。SOLOをuninstallする
必要はありません。

```bash
cd ~/repos/RoboMaster-S1-WiFi-SDK
deactivate 2>/dev/null || true
source "/opt/ros/${ROS_DISTRO}/setup.bash"
python3 -m venv --system-site-packages .venv-ros-lab
source .venv-ros-lab/bin/activate
python -m pip install --upgrade pip wheel
python -m pip install "setuptools<80"
python -m pip install ./LAB-SDK numpy-quaternion pyyaml
python -c \
  "import robomaster; print(robomaster.__file__); print(robomaster.IS_LAB_SDK)"
python /usr/bin/colcon build --symlink-install \
  --build-base build-lab \
  --install-base install-lab \
  --packages-select robomaster_msgs robomaster_description robomaster_ros
source install-lab/setup.bash
```

## S1 SOLOドライバを起動

S1とPCを同じWi-Fiへ接続し、S1のIPとAppIDを指定します。純正RoboMasterアプリは
制御セッションが競合しないよう終了してください。

```bash
source "/opt/ros/${ROS_DISTRO}/setup.bash"
source ~/repos/RoboMaster-S1-WiFi-SDK/.venv-ros-solo/bin/activate
source ~/repos/RoboMaster-S1-WiFi-SDK/install-solo/setup.bash

export RM_ROBOT_IP=192.168.23.149
export RM_APPID=b6359877
ros2 launch robomaster_ros s1_solo.launch
```

接続状態を別端末から確認します。

```bash
ros2 topic echo /connected --once
```

`data: true`なら接続済みです。

## S1 LABドライバを起動

LABはLAB用venvとinstall directoryをsourceして起動します。

```bash
source "/opt/ros/${ROS_DISTRO}/setup.bash"
source ~/repos/RoboMaster-S1-WiFi-SDK/.venv-ros-lab/bin/activate
source ~/repos/RoboMaster-S1-WiFi-SDK/install-lab/setup.bash
RM_ROBOT_IP=192.168.23.149 RM_APPID=b6359877 \
  ros2 launch robomaster_ros s1_lab.launch
```

機体側bridgeの転送と起動にはFTP `21`、Host bridgeにはUDP `40923`と`40924`も
使用します。

LABのシャーシ／ジンバル速度は最新状態だけを適用します。未処理の古いmotion packet
は破棄され、停止指令がキューの後ろへ滞留しません。LEDや発射などの単発commandは
従来どおり順序を保持します。同一速度の再送は除去し、telemetry getterは制御との
競合を避けるため10Hzで実行します。

## PS5 DualSenseで操作

### 割り当て

| DualSense | S1 |
|---|---|
| 左スティック上下 | 前進・後退 |
| 左スティック左右 | 左右平行移動 |
| 右スティック | ジンバルYaw・Pitch |
| L2 | 左旋回（アナログ） |
| R2 | 右旋回（アナログ） |
| L1 | ブラスターLEDの点灯・消灯を切り替え |
| R1 | 赤外線ブラスターを1回発射 |

`game_controller_node`を使用するため、USBとBluetoothのどちらでもSDL標準の軸順に
正規化されます。

デバイス番号を確認します。

```bash
ros2 run joy joy_enumerate_devices
```

テレオペレーションを起動します。

```bash
ros2 launch robomaster_ros s1_joy.launch device_id:=0
```

Joy入力を確認できます。

```bash
ros2 topic echo /joy
```

既定の軸順は次のとおりです。

| Axis | 入力 |
|---:|---|
| `0` | 左スティックX |
| `1` | 左スティックY |
| `2` | 右スティックX |
| `3` | 右スティックY |
| `4` | L2 |
| `5` | R2 |

Joy messageが`joy_timeout`秒以上途絶えると、シャーシとジンバルへゼロ速度を
送信します。

## キーボードで操作

キーボード入力にはインタラクティブな端末が必要です。`ros2 launch`経由ではなく、
次のように直接実行する方法を推奨します。

```bash
ros2 run robomaster_ros s1_teleop --ros-args \
  -p use_joy:=false \
  -p use_keyboard:=true
```

| キー | 動作 |
|---|---|
| `W / A / S / D` | 前進・左移動・後退・右移動 |
| `Shift + W/A/S/D` | 加速 |
| `Space` | 加速モード切替 |
| 矢印キー | ジンバル |
| `Q / E` | 左旋回・右旋回 |
| `L` | ブラスターLEDの点灯・消灯を切り替え |
| `F` | 赤外線ブラスターを1回発射 |
| `X` | 即時停止 |

Linux inputを使用できる場合は押下・解放状態を直接取得するため、`W`と矢印キーなどを
同時に使用できます。端末入力へフォールバックした場合は、キーリピートが止まると
`key_timeout`後にゼロ速度へ戻ります。

## Teleop parameter

| Parameter | Type | Default | 内容 |
|---|---|---:|---|
| `use_joy` | bool | `true` | `/joy`を購読 |
| `use_keyboard` | bool | `false` | 端末キー入力を使用 |
| `linear_speed` | double | `1.5` | 最大並進速度 m/s |
| `angular_speed` | double | `2.0` | 最大旋回速度 rad/s |
| `gimbal_speed` | double | `3.0` | 最大ジンバル速度 rad/s |
| `boost_multiplier` | double | `1.5` | キーボード加速倍率 |
| `deadzone` | double | `0.08` | スティックdeadzone |
| `joy_timeout` | double | `0.3` | Joy watchdog秒数 |
| `key_timeout` | double | `0.10` | キーを離したとみなすまでの秒数 |
| `fire_cooldown` | double | `0.25` | 赤外線ブラスターの誤連射防止時間（秒） |
| `keyboard_device` | string | 空 | `/dev/input/eventN`の明示指定（空なら自動検出） |
| `trigger_released_value` | double | `-1.0` | 離したtriggerの軸値 |

実行中の速度を変更する例:

```bash
ros2 param set /s1_teleop linear_speed 0.3
ros2 param set /s1_teleop angular_speed 0.8
ros2 param set /s1_teleop gimbal_speed 1.0
```

## 主なROS interface

namespaceを指定しない場合の代表的なinterfaceです。

| Interface | Type | 内容 |
|---|---|---|
| `/connected` | `std_msgs/msg/Bool` | S1接続状態 |
| `/cmd_vel` | `geometry_msgs/msg/Twist` | シャーシ速度指令 |
| `/cmd_gimbal` | `robomaster_msgs/msg/GimbalCommand` | ジンバル速度指令 |
| `/odom` | `nav_msgs/msg/Odometry` | Odometry |
| `/imu` | `sensor_msgs/msg/Imu` | IMU。SOLO／LABでは実測元なし |
| `/joint_states` | `sensor_msgs/msg/JointState` | 集約joint state |
| `/battery` | `sensor_msgs/msg/BatteryState` | バッテリー |
| `/camera/image_raw` | `sensor_msgs/msg/Image` | Decode済み映像 |
| `/camera/image_h264` | `robomaster_msgs/msg/H264Packet` | H.264 packet |
| `/camera/audio_opus` | `robomaster_msgs/msg/AudioOpus` | Opus音声 |

実際に有効なinterfaceはbackendとlaunch argumentにより変わります。

```bash
ros2 topic list
ros2 action list
ros2 service list
ros2 param list /robomaster
```

## Namespaceを使う

ドライバとteleopで同じ`name`を指定します。

```bash
RM_ROBOT_IP=192.168.23.149 \
  ros2 launch robomaster_ros s1_solo.launch name:=s1
```

```bash
ros2 launch robomaster_ros s1_joy.launch name:=s1 device_id:=0
```

topicは`/s1/cmd_vel`、`/s1/cmd_gimbal`などになります。

## 映像・音声

S1用launchは720pを選択します。映像・音声の既定modeはon-demandで、対応topicに
subscriberが接続されたときにstreamを開始します。

```bash
ros2 topic hz /camera/image_raw
ros2 topic echo /camera/audio_level
```

起動時から有効にする場合:

```bash
RM_ROBOT_IP=192.168.23.149 \
  ros2 launch robomaster_ros s1_solo.launch audio:=1
```

無効にする場合:

```bash
RM_ROBOT_IP=192.168.23.149 \
  ros2 launch robomaster_ros s1_solo.launch audio:=-1
```

## 終了

1. Teleop側で`X`を押す
2. Teleop端末で`Ctrl+C`
3. ドライバ端末で`Ctrl+C`

Teleopは終了時にゼロ速度をpublishします。ドライバはmoduleを停止し、LAB backendでは
bridgeと機体programも停止してから接続を閉じます。

## トラブルシューティング

### `Package 'robomaster_ros' not found`

```bash
source "/opt/ros/${ROS_DISTRO}/setup.bash"
source ~/repos/RoboMaster-S1-WiFi-SDK/.venv-ros-solo/bin/activate
source ~/repos/RoboMaster-S1-WiFi-SDK/install-solo/setup.bash
```

### SOLO backendが見つからない

```bash
source ~/repos/RoboMaster-S1-WiFi-SDK/.venv-ros-solo/bin/activate
python -c \
  "import robomaster; print(robomaster.__file__); print(robomaster.IS_S1_WIFI_SDK)"
```

`False`またはimport errorの場合は、親リポジトリの`SDK/`をROS 2と同じPythonへ
インストールしてください。

### `ModuleNotFoundError: No module named 'robomaster'`

apt版の`colcon`を直接起動して生成されたROS executableはシステムPythonを使用します。
SOLO venvのPythonから再ビルドしてください。

```bash
cd ~/repos/RoboMaster-S1-WiFi-SDK
source /opt/ros/jazzy/setup.bash
source .venv-ros-solo/bin/activate
python /usr/bin/colcon build --symlink-install \
  --build-base build-solo \
  --install-base install-solo \
  --packages-select robomaster_msgs robomaster_description robomaster_ros
head -1 install-solo/robomaster_ros/lib/robomaster_ros/robomaster_driver
```

先頭行が`.venv-ros-solo/bin/python`を指していることを確認します。

### DualSenseが見つからない

```bash
ros2 run joy joy_enumerate_devices
ls -l /dev/input/js* /dev/input/event*
groups
```

権限がない場合:

```bash
sudo usermod -aG input "$USER"
```

ログアウト・ログイン後に再確認してください。

### `/joy`は変化するがS1が動かない

```bash
ros2 topic echo /cmd_vel
ros2 topic echo /cmd_gimbal
ros2 topic echo /connected --once
```

- `/joy`だけ変化する: `s1_teleop`とnamespaceを確認
- `/cmd_vel`も変化する: ドライバ、S1接続、backendを確認
- `/connected`がfalseまたは存在しない: IP、AppID、Firewallを確認

## 開発・テスト

```bash
cd ~/repos/RoboMaster-S1-WiFi-SDK
source .venv-ros-solo/bin/activate
python /usr/bin/colcon build --symlink-install \
  --build-base build-solo \
  --install-base install-solo \
  --packages-select robomaster_msgs robomaster_description robomaster_ros
python /usr/bin/colcon test \
  --build-base build-solo \
  --install-base install-solo \
  --packages-select robomaster_msgs robomaster_description robomaster_ros
python /usr/bin/colcon test-result --test-result-base build-solo --verbose
```

Pythonファイルだけを確認する場合:

```bash
python -m py_compile robomaster_ros/robomaster_ros/robomaster_ros/*.py
```

## ライセンス

[LICENSE](LICENSE)を参照してください。RoboMaster、DJIおよび各製品名はそれぞれの
権利者に帰属します。
