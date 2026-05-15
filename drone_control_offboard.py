#!/usr/bin/env python3
"""
drone_control_offboard.py - 使用 Offboard 模式控制 PX4 SITL 无人机起降
用法:
  1. 先启动仿真: cd ~/PX4-Autopilot && make px4_sitl gz_x500
  2. 新终端运行本脚本: python3 drone_control_offboard.py
"""

import asyncio
import logging

from mavsdk import System
from mavsdk.action import ActionError
from mavsdk.offboard import OffboardError, PositionNedYaw, VelocityNedYaw
from mavsdk.param import ParamError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SITL_ADDRESS = "udpin://0.0.0.0:14540"
TAKEOFF_ALTITUDE = 10.0


async def connect_drone() -> System:
    drone = System()
    await drone.connect(system_address=SITL_ADDRESS)

    logger.info("等待连接无人机...")
    async for state in drone.core.connection_state():
        if state.is_connected:
            logger.info("无人机已连接")
            break
    return drone


async def wait_for_gps(drone: System):
    logger.info("等待 GPS 定位...")
    async for health in drone.telemetry.health():
        if health.is_global_position_ok and health.is_home_position_ok:
            logger.info("GPS 定位完成")
            break


async def set_params(drone: System):
    logger.info("设置 SITL 仿真参数...")
    params = {
        "COM_RCL_EXCEPT":   (4,      "允许无 RC 解锁 (ALTCTL)"),
        "CBRK_IO_SAFETY":   (22027,  "跳过 IO 安全开关"),
        "CBRK_SUPPLY_CHK":  (22027,  "跳过供电/电池检查"),
        "CAL_GYRO0_ID":     (1310988,"陀螺仪校准 ID"),
        "CAL_ACC0_ID":      (1310988,"加速度计校准 ID"),
        "MIS_TAKEOFF_ALT":  (10.0,   "起飞最低高度"),
        "MPC_THR_HOVER":    (0.60,   "悬停推力"),
    }
    for name, (val, desc) in params.items():
        try:
            if isinstance(val, float):
                await drone.param.set_param_float(name, val)
            else:
                await drone.param.set_param_int(name, val)
            logger.info(f"  {name}={val}（{desc}）")
        except ParamError as e:
            logger.warning(f"  {name} 设置失败: {e}")
    await asyncio.sleep(1)


async def run():
    drone = await connect_drone()
    await wait_for_gps(drone)
    await set_params(drone)

    # === 获取起飞位置（home） ===
    async for terrain in drone.telemetry.home():
        home_lat = terrain.latitude_deg
        home_lon = terrain.longitude_deg
        home_alt = terrain.absolute_altitude_m
        break
    logger.info(f"Home: lat={home_lat:.6f}, lon={home_lon:.6f}, alt={home_alt:.1f}m")

    # === 解锁 ===
    logger.info("解锁 (Arm)...")
    try:
        await drone.action.arm()
    except ActionError as e:
        logger.error(f"解锁失败: {e}")
        return
    await asyncio.sleep(2)

    # === 切换到 Offboard 模式，发送位置设定点 ===
    logger.info("切换到 Offboard 模式并起飞...")
    try:
        await drone.offboard.set_position_ned(PositionNedYaw(0.0, 0.0, -1.0, 0.0))
        await drone.offboard.start()
    except OffboardError as e:
        logger.error(f"Offboard 启动失败: {e}")
        return

    # 逐步爬升: 1m -> 2m -> 3m -> ... -> TAKEOFF_ALTITUDE
    for target_alt in range(1, int(TAKEOFF_ALTITUDE) + 1):
        logger.info(f"爬升到 {target_alt}m...")
        await drone.offboard.set_position_ned(
            PositionNedYaw(0.0, 0.0, -float(target_alt), 0.0)
        )
        # 等待到达当前目标高度
        for _ in range(30):
            async for pos in drone.telemetry.position():
                alt = pos.relative_altitude_m
                logger.info(f"  > 实际高度: {alt:.2f}m")
                if alt >= target_alt * 0.85:
                    break
                await asyncio.sleep(0.1)
                break
        await asyncio.sleep(1)

    logger.info(f"已到达 {TAKEOFF_ALTITUDE}m，悬停中")
    await asyncio.sleep(3)

    # === 飞向目标点 1 (向北 50m) ===
    logger.info("飞向目标点1 (向北 50m)...")
    await drone.offboard.set_position_ned(
        PositionNedYaw(-50.0, 0.0, -TAKEOFF_ALTITUDE, 0.0)
    )
    await asyncio.sleep(10)

    # === 飞向目标点 2 (向东北 50m) ===
    logger.info("飞向目标点2 (向东北 70m)...")
    await drone.offboard.set_position_ned(
        PositionNedYaw(-50.0, -70.0, -TAKEOFF_ALTITUDE, -45.0)
    )
    await asyncio.sleep(10)

    # === 返航 ===
    logger.info("返航中...")
    await drone.offboard.set_position_ned(
        PositionNedYaw(0.0, 0.0, -TAKEOFF_ALTITUDE, 0.0)
    )
    await asyncio.sleep(10)

    # === 降落 ===
    logger.info("降落中...")
    await drone.offboard.set_position_ned(PositionNedYaw(0.0, 0.0, -0.5, 0.0))
    await asyncio.sleep(3)
    await drone.offboard.set_position_ned(PositionNedYaw(0.0, 0.0, 0.0, 0.0))
    await asyncio.sleep(2)

    # 停止 Offboard -> 自动切换到 AUTO.LAND
    logger.info("执行 LAND...")
    try:
        await drone.action.land()
    except ActionError as e:
        logger.error(f"降落失败: {e}")

    # 等待降落
    was_in_air = False
    async for is_in_air in drone.telemetry.in_air():
        if is_in_air:
            was_in_air = True
        if was_in_air and not is_in_air:
            logger.info("无人机已降落")
            break

    logger.info("飞行任务完成！")


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("用户中断")
