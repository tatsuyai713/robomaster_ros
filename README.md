# RoboMaster ROS 2

DJI RoboMaster S1／EP用のROS 2ドライバです。このforkはsubmoduleとして含まれる
S1用SOLO SDKとLAB-SDKに対応し、PS5 DualSenseおよびキーボード用
テレオペレーションノードを提供します。

> [!WARNING]
> 本プロジェクトはDJI公式ソフトウェアではありません。初回は車輪を床から浮かせ、
> 物理弾を抜き、停止指令が動作することを確認してください。

SOLO SDKとLAB-SDKは`robomaster_s1_wifi_sdk` submoduleに含まれます。

```bash
git submodule update --init --recursive
```

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

SOLO SDKとLAB-SDKはどちらも`robomaster`というPython packageを提供します。
このプロジェクトではSDKをPython環境へインストールせず、`s1_solo.launch`と
`s1_lab.launch`が対応するソースディレクトリをdriverへ渡します。`main.launch`は
driverプロセスの`PYTHONPATH`を設定し、driverは`client.py`をimportする前に同じ
ディレクトリを`sys.path`へ追加します。ROS packageのbuild/install directoryは
backend間で共通です。

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

ROS 2をsourceします。Ubuntu 24.04では`humble`を`jazzy`へ置き換えてください。

```bash
source /opt/ros/humble/setup.bash
```

依存パッケージをインストールします。

```bash
sudo apt update
sudo apt install -y \
  git \
  python3-colcon-common-extensions \
  python3-full \
  python3-pip \
  python3-av \
  python3-evdev \
  python3-numpy \
  python3-pil \
  python3-qrcode \
  python3-rosdep \
  python3-yaml \
  libopus-dev \
  "ros-${ROS_DISTRO}-xacro" \
  "ros-${ROS_DISTRO}-launch-xml" \
  "ros-${ROS_DISTRO}-cv-bridge" \
  "ros-${ROS_DISTRO}-robot-state-publisher" \
  "ros-${ROS_DISTRO}-joint-state-publisher" \
  "ros-${ROS_DISTRO}-joy"
```

`numpy-quaternion`がない場合は、使用中のPython環境へ追加してください。Ubuntu 24.04の
システムPythonへユーザー単位で追加する例です。

```bash
python3 -m pip install --user --break-system-packages numpy-quaternion
```

## Workspaceを準備

標準の配置は`~/ros2_ws/src/robomaster_ros`です。

```bash
mkdir -p ~/ros2_ws/src
cd ~/ros2_ws/src
git clone --recurse-submodules \
  https://github.com/tatsuyai713/robomaster_ros.git
cd robomaster_ros
git submodule update --init --recursive
```

すでにclone済みなら、submodule内に両backendがあることを確認します。

```bash
test -d robomaster_s1_wifi_sdk/SDK/robomaster
test -d robomaster_s1_wifi_sdk/LAB-SDK/robomaster
```

## 共通ROS packageをビルド

SDK backendは起動時に選ぶため、colcon buildは1回だけです。

```bash
cd ~/ros2_ws
source "/opt/ros/${ROS_DISTRO}/setup.bash"
rosdep install --from-paths src/robomaster_ros \
  --ignore-src -r -y
colcon build --symlink-install \
  --packages-select robomaster_msgs robomaster_description robomaster_ros
source install/setup.bash
ros2 pkg prefix robomaster_ros
```

## S1へ接続

S1とPCを同じWi-Fiへ接続し、S1のIPとAppIDを指定します。純正RoboMasterアプリは
制御セッションが競合しないよう終了してください。

```bash
export RM_ROBOT_IP=192.168.23.149
export RM_APPID=b6359877
```

LAB backendを起動します。

```bash
cd ~/ros2_ws
source /opt/ros/jazzy/setup.bash
source install/setup.bash
ros2 launch robomaster_ros s1_lab.launch
```

`s1_lab.launch`は既定で次のソースをdriverの`PYTHONPATH`へ追加します。LAB SDKを
pip installする必要はありません。

```text
~/ros2_ws/src/robomaster_ros/robomaster_s1_wifi_sdk/LAB-SDK
```

SOLO backendも同じbuildから起動できます。

```bash
ros2 launch robomaster_ros s1_solo.launch
```

標準以外の場所へcloneした場合は、launch引数でソースディレクトリを指定します。

```bash
ros2 launch robomaster_ros s1_lab.launch \
  backend_path:=/absolute/path/to/robomaster_ros/robomaster_s1_wifi_sdk/LAB-SDK
```

接続状態を別端末から確認します。

```bash
ros2 topic echo /connected --once
```

`data: true`なら接続済みです。

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
cd ~/ros2_ws
source "/opt/ros/${ROS_DISTRO}/setup.bash"
source install/setup.bash
ros2 pkg prefix robomaster_ros
```

見つからない場合は、workspaceを再ビルドします。

```bash
cd ~/ros2_ws
colcon build --symlink-install \
  --packages-select robomaster_msgs robomaster_description robomaster_ros
source install/setup.bash
```

### `ModuleNotFoundError: No module named 'robomaster'`

古いinstall directory内のlaunchには`backend_path`設定がありません。また、
`robomaster_driver.py`にも起動時のSDKパス追加処理が必要です。両方をinstall
directoryへ反映してから起動します。

```bash
cd ~/ros2_ws
source /opt/ros/jazzy/setup.bash
colcon build --symlink-install \
  --packages-select robomaster_ros
source install/setup.bash
ros2 launch robomaster_ros s1_lab.launch --show-args
grep -n "ROBOMASTER_SDK_PATH" \
  install/robomaster_ros/share/robomaster_ros/launch/main.launch
ros2 launch robomaster_ros s1_lab.launch
```

`--show-args`に`backend_path`が表示され、`grep`でも設定が見つかることを確認します。
起動時に指定先が存在しない場合は、driverが`RoboMaster SDK source not found`と実際の
確認対象パスを表示します。

```bash
test -d \
  ~/ros2_ws/src/robomaster_ros/robomaster_s1_wifi_sdk/LAB-SDK/robomaster
```

clone場所が違う場合:

```bash
ros2 launch robomaster_ros s1_lab.launch \
  backend_path:=/absolute/path/to/robomaster_ros/robomaster_s1_wifi_sdk/LAB-SDK
```

submoduleが空の場合は初期化します。

```bash
cd ~/ros2_ws/src/robomaster_ros
git submodule update --init --recursive
```

### backendの依存packageが見つからない

SDKソースはlaunchが追加しますが、共通のPython依存packageはシステムPythonから
importできる必要があります。

```bash
python3 -c "import av, numpy, qrcode, quaternion, yaml; print('OK')"
```

不足しているpackageは「必要環境」の手順で追加してください。

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
cd ~/ros2_ws
source "/opt/ros/${ROS_DISTRO}/setup.bash"
colcon build --symlink-install \
  --packages-select robomaster_msgs robomaster_description robomaster_ros
colcon test \
  --packages-select robomaster_msgs robomaster_description robomaster_ros
colcon test-result --verbose
```

Pythonファイルだけを確認する場合:

```bash
python3 -m compileall -q \
  src/robomaster_ros/robomaster_ros/robomaster_ros
```

## ライセンス

[LICENSE](LICENSE)を参照してください。RoboMaster、DJIおよび各製品名はそれぞれの
権利者に帰属します。
