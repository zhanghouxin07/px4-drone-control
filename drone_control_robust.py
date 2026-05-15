#!/usr/bin/env python3
"""
drone_control_robust.py - 健壮的 PX4 无人机自动飞行脚本
先等待 is_armable=True，再解锁起飞
"""
import asyncio
import logging

from mavsdk import System
from mavsdk.action import ActionError
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


async def wait_for_gps_and_health(drone: System):
    logger.info("等待 GPS 定位...")
    async for health in drone.telemetry.health():
        if health.is_global_position_ok and health.is_home_position_ok:
            logger.info("GPS 定位完成")
            break

    logger.info("等待 is_armable=True...")
    async for health in drone.telemetry.health():
        if health.is_armable:
            logger.info("飞机已可解锁 (is_armable=True)")
            break
        await asyncio.sleep(0.5)


async def set_params(drone: System):
    logger.info("设置 SITL 仿真参数...")
    params_int = {
        "COM_RCL_EXCEPT": 4,
        "CBRK_IO_SAFETY": 22027,
        "CBRK_SUPPLY_CHK": 22027,
    }
    params_float = {
        "MIS_TAKEOFF_ALT": TAKEOFF_ALTITUDE,
        "MPC_THR_HOVER": 0.60,
    }
    for name, val in params_int.items():
        try:
            await drone.param.set_param_int(name, val)
            logger.info(f"  {name}={val}")
        except ParamError as e:
            logger.warning(f"  {name} 设置失败: {e}")
    for name, val in params_float.items():
        try:
            await drone.param.set_param_float(name, val)
            logger.info(f"  {name}={val}")
        except ParamError as e:
            logger.warning(f"  {name} 设置失败: {e}")
    await asyncio.sleep(2)


async def run():
    drone = await connect_drone()
    await set_params(drone)
    await wait_for_gps_and_health(drone)

    logger.info("解锁 (Arm)...")
    try:
        await drone.action.arm()
    except ActionError as e:
        logger.error(f"解锁失败: {e}")
        return

    logger.info(f"起飞到 {TAKEOFF_ALTITUDE}m...")
    try:
        await drone.action.takeoff()
    except ActionError as e:
        logger.error(f"起飞失败: {e}")
        return

    await asyncio.sleep(5)
    async for pos in drone.telemetry.position():
        alt = pos.relative_altitude_m
        logger.info(f"高度: {alt:.1f}m")
        if alt >= TAKEOFF_ALTITUDE * 0.85:
            break

    logger.info(f"到达 {TAKEOFF_ALTITUDE}m，悬停中")
    await asyncio.sleep(2)

    # 飞向目标点 1
    t1_lat = 47.397742 + 0.0005
    t1_lon = 8.545594
    logger.info(f"飞向目标点1: ({t1_lat:.6f}, {t1_lon:.6f})")
    await drone.action.goto_location(t1_lat, t1_lon, TAKEOFF_ALTITUDE, 0)
    await asyncio.sleep(10)

    # 飞向目标点 2
    t2_lat = t1_lat + 0.0005
    t2_lon = t1_lon + 0.0005
    logger.info(f"飞向目标点2: ({t2_lat:.6f}, {t2_lon:.6f})")
    await drone.action.goto_location(t2_lat, t2_lon, TAKEOFF_ALTITUDE, 45)
    await asyncio.sleep(10)

    logger.info("返航")
    await drone.action.return_to_launch()

    was_in_air = False
    async for is_in_air in drone.telemetry.in_air():
        if is_in_air:
            was_in_air = True
        if was_in_air and not is_in_air:
            logger.info("已降落")
            break

    logger.info("飞行任务完成！")


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("用户中断")
