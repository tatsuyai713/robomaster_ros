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
    script = PathJoinSubstitution([app_root, "robomaster_wifi_qr_generator.py"])

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
        ExecuteProcess(
            cmd=[FindExecutable(name="python3"), script],
            output="screen",
        ),
    ])
