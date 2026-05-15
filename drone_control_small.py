#!/usr/bin/env python3
"""drone_control_small.py - 无人机在 5x5x5 空间内小范围移动"""
import asyncio, logging
from mavsdk import System
from mavsdk.action import ActionError
from mavsdk.offboard import OffboardError, PositionNedYaw
from mavsdk.param import ParamError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
SITL_ADDRESS = "udpin://0.0.0.0:14540"
ALT = 2.5  # 飞行高度

async def run():
    drone = System()
    await drone.connect(system_address=SITL_ADDRESS)
    async for s in drone.core.connection_state():
        if s.is_connected: break
    logger.info("Connected")

    logger.info("GPS...")
    async for h in drone.telemetry.health():
        if h.is_global_position_ok and h.is_home_position_ok: break

    logger.info("Params...")
    for n, v in {"COM_RCL_EXCEPT": 4, "CBRK_IO_SAFETY": 22027, "CBRK_SUPPLY_CHK": 22027}.items():
        try: await drone.param.set_param_int(n, v)
        except: pass
    await drone.param.set_param_float("MPC_THR_HOVER", 0.6)
    await asyncio.sleep(1)

    async for h in drone.telemetry.health():
        if h.is_armable: break

    await drone.action.arm()
    logger.info("Armed")

    # Offboard: climb to 2.5m
    await drone.offboard.set_position_ned(PositionNedYaw(0, 0, -ALT, 0))
    try: await drone.offboard.start()
    except OffboardError as e:
        logger.error(f"Offboard failed: {e}"); return
    logger.info("Offboard started")

    await asyncio.sleep(8)  # 等爬升到位
    logger.info(f"At {ALT}m, start small moves")

    # 5x5x5 空间内小范围移动
    moves = [
        (2.0, 0.0,   "→ 北 2m"),
        (2.0, 2.0,   "→ 东北 2m"),
        (0.0, 2.0,   "→ 东 2m"),
        (-2.0, 0.0,  "→ 南 2m"),
        (0.0, -2.0,  "→ 西 2m"),
        (0.0, 0.0,   "→ 回到中心"),
        (0.0, 0.0,   "悬停"),
    ]

    for nx, ey, label in moves:
        logger.info(label)
        await drone.offboard.set_position_ned(PositionNedYaw(nx, ey, -ALT, 0))
        await asyncio.sleep(5)

    # 降落
    logger.info("Land")
    await drone.action.land()
    was_in_air = False
    async for i in drone.telemetry.in_air():
        if i: was_in_air = True
        if was_in_air and not i:
            logger.info("Landed!"); break

    logger.info("Done!")

if __name__ == "__main__":
    try: asyncio.run(run())
    except KeyboardInterrupt: logger.info("Cancelled")
