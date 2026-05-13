#!/usr/bin/env python3
"""
drone_control.py - PX4 无人机自动起降飞行控制脚本
=================================================
使用 MAVSDK-Python 控制 PX4 SITL 仿真中的无人机。

用法:
  1. 先启动仿真: cd ~/PX4-Autopilot && make px4_sitl gz_x500
  2. 新终端运行本脚本: python3 drone_control.py

航线: 起飞 → 飞向目标点1 → 飞向目标点2 → 返航 → 降落
"""

import asyncio
import logging

from mavsdk import System
from mavsdk.action import ActionError
from mavsdk.param import ParamError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 连接地址 (PX4 SITL 默认 UDP 端口)
SITL_ADDRESS = "udpin://0.0.0.0:14540"

# 飞行参数
TAKEOFF_ALTITUDE = 10.0       # 起飞高度 (米)
FLIGHT_SPEED = 5.0            # 飞行速度 (m/s)
SITL_HOME_LAT = 47.397742     # SITL 默认起飞点纬度
SITL_HOME_LON = 8.545594      # SITL 默认起飞点经度


async def connect_drone() -> System:
    """连接到 PX4 SITL 无人机"""
    drone = System()
    await drone.connect(system_address=SITL_ADDRESS)

    logger.info("等待连接无人机...")
    async for state in drone.core.connection_state():
        if state.is_connected:
            logger.info("✓ 无人机已连接")
            break

    return drone


async def wait_for_gps(drone: System):
    """等待 GPS 定位"""
    logger.info("等待 GPS 定位...")
    async for health in drone.telemetry.health():
        if health.is_global_position_ok and health.is_home_position_ok:
            logger.info("✓ GPS 定位完成")
            break


async def print_telemetry(drone: System):
    """后台打印无人机位置和姿态信息"""
    async for position in drone.telemetry.position():
        logger.info(
            f"位置: lat={position.latitude_deg:.6f}, "
            f"lon={position.longitude_deg:.6f}, "
            f"alt(相对)={position.relative_altitude_m:.1f}m"
        )
        break  # 只打一次，后续由主循环控制

    async for attitude in drone.telemetry.attitude_euler():
        logger.info(
            f"姿态: roll={attitude.roll_deg:.1f}°, "
            f"pitch={attitude.pitch_deg:.1f}°, "
            f"yaw={attitude.yaw_deg:.1f}°"
        )
        break


async def observe_is_in_air(drone: System):
    """监控飞行状态，降落后自动退出"""
    was_in_air = False
    async for is_in_air in drone.telemetry.in_air():
        if is_in_air:
            was_in_air = True
        if was_in_air and not is_in_air:
            logger.info("✓ 无人机已降落")
            return


async def run_mission():
    """执行飞行任务"""
    drone = await connect_drone()
    await wait_for_gps(drone)

    # === 设置 SITL 仿真参数 ===
    logger.info("⚙️ 设置 SITL 仿真参数...")

    # 1. 允许无 RC 解锁
    try:
        await drone.param.set_param_int("COM_RCL_EXCEPT", 4)
        logger.info("  ✓ COM_RCL_EXCEPT=4（允许无 RC 解锁）")
    except ParamError as e:
        logger.warning(f"  COM_RCL_EXCEPT 设置失败: {e}")

    # 2. 跳过安全开关（IO 安全开关）
    try:
        await drone.param.set_param_int("CBRK_IO_SAFETY", 22027)
        logger.info("  ✓ CBRK_IO_SAFETY=22027（跳过安全开关）")
    except ParamError as e:
        logger.warning(f"  CBRK_IO_SAFETY 设置失败: {e}")

    await asyncio.sleep(1)  # 等待参数生效

    # === 起飞 ===
    logger.info("🚁 解锁 (Arm)...")
    try:
        await drone.action.arm()
    except ActionError as e:
        logger.error(f"解锁失败: {e}")
        return

    logger.info(f"✈️ 起飞到 {TAKEOFF_ALTITUDE} 米...")
    try:
        await drone.action.takeoff()
        await asyncio.sleep(5)  # 等待离地

        # 爬升到目标高度
        async for position in drone.telemetry.position():
            alt = position.relative_altitude_m
            logger.info(f"当前高度: {alt:.1f}m")
            if alt >= TAKEOFF_ALTITUDE * 0.9:
                break
    except ActionError as e:
        logger.error(f"起飞失败: {e}")
        return

    logger.info(f"✓ 到达目标高度 {TAKEOFF_ALTITUDE}m，悬停中")
    await asyncio.sleep(2)

    # === 飞向目标点 1 (向北 50m) ===
    target1_lat = SITL_HOME_LAT + 0.0005  # ~向北 50m
    target1_lon = SITL_HOME_LON
    logger.info(f"📍 飞向目标点1: ({target1_lat:.6f}, {target1_lon:.6f}) @ {TAKEOFF_ALTITUDE}m")
    await drone.action.goto_location(target1_lat, target1_lon, TAKEOFF_ALTITUDE, 0)
    await asyncio.sleep(10)  # 等待到达

    # === 飞向目标点 2 (向东北方向) ===
    target2_lat = target1_lat + 0.0005
    target2_lon = target1_lon + 0.0005
    logger.info(f"📍 飞向目标点2: ({target2_lat:.6f}, {target2_lon:.6f}) @ {TAKEOFF_ALTITUDE}m")
    await drone.action.goto_location(target2_lat, target2_lon, TAKEOFF_ALTITUDE, 45)
    await asyncio.sleep(10)

    # === 返航 ===
    logger.info("🏠 返航 (Return to Launch)...")
    await drone.action.return_to_launch()

    # 等待降落完成
    await observe_is_in_air(drone)

    logger.info("✅ 飞行任务完成！")


if __name__ == "__main__":
    try:
        asyncio.run(run_mission())
    except KeyboardInterrupt:
        logger.info("用户中断，飞行任务结束")
