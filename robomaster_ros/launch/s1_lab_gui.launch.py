from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, ExecuteProcess
from launch.substitutions import (
    EnvironmentVariable,
    FindExecutable,
    LaunchConfiguration,
    PathJoinSubstitution,
)


def generate_launch_description() -> LaunchDescription:
    app_root = LaunchConfiguration("app_root")
    robot_ip = LaunchConfiguration("robot_ip")
    appid = LaunchConfiguration("appid")
    local_ip = LaunchConfiguration("local_ip")
    control_port = LaunchConfiguration("control_port")
    telemetry_port = LaunchConfiguration("telemetry_port")
    script = PathJoinSubstitution([app_root, "robomaster_s1_lab_app.py"])

    return LaunchDescription([
        DeclareLaunchArgument(
            "app_root",
            default_value=PathJoinSubstitution([
                EnvironmentVariable("HOME"),
                "ros2_ws",
                "src",
                "robomaster_ros",
                "robomaster_s1_wifi_sdk",
            ]),
            description="Directory containing the RoboMaster GUI scripts",
        ),
        DeclareLaunchArgument(
            "robot_ip",
            default_value=EnvironmentVariable("RM_ROBOT_IP", default_value=""),
        ),
        DeclareLaunchArgument(
            "appid",
            default_value=EnvironmentVariable(
                "RM_APPID",
                default_value="b6359877",
            ),
        ),
        DeclareLaunchArgument("local_ip", default_value="0.0.0.0"),
        DeclareLaunchArgument("control_port", default_value="40923"),
        DeclareLaunchArgument("telemetry_port", default_value="40924"),
        ExecuteProcess(
            cmd=[
                FindExecutable(name="python3"),
                script,
                "--robot-ip",
                robot_ip,
                "--appid",
                appid,
                "--local-ip",
                local_ip,
                "--control-port",
                control_port,
                "--telemetry-port",
                telemetry_port,
            ],
            output="screen",
        ),
    ])
