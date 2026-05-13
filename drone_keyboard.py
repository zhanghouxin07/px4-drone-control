#!/usr/bin/env python3
"""
drone_keyboard.py - PX4 无人机键盘实时控制脚本
============================================
使用键盘实时控制 PX4 SITL 仿真中的无人机。

用法:
  1. 先启动仿真: cd ~/PX4-Autopilot && make px4_sitl gz_x500
  2. 新终端运行本脚本: python3 drone_keyboard.py

控制键:
  W/↑  = 向前飞      S/↓  = 向后飞
  A/←  = 向左飞      D/→  = 向右飞
  Q    = 上升        E    = 下降
  Space= 起飞        L    = 降落
  R    = 返航
  H    = 悬停
  T    = 解锁 (Arm)
  ESC  = 退出
"""

import asyncio
import logging
import sys
import threading
import time
from datetime import datetime

from mavsdk import System
from mavsdk.action import ActionError
from mavsdk.offboard import OffboardError, VelocityNedYaw

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SITL_ADDRESS = "udpin://0.0.0.0:14540"
TAKEOFF_ALTITUDE = 10.0
VELOCITY_STEP = 2.0          # 每按一次的速度变化 (m/s)
VELOCITY_MAX = 5.0           # 最大速度 (m/s)

# 全局控制状态
class DroneState:
    def __init__(self):
        self.vx = 0.0   # 北向速度 (m/s)
        self.vy = 0.0   # 东向速度 (m/s)
        self.vz = 0.0   # 垂直速度 (m/s, 负=上升)
        self.yaw = 0.0  # 偏航角 (度)
        self.is_armed = False
        self.is_in_air = False
        self.in_offboard = False
        self.running = True
        self.last_input = ""
        self.altitude = 0.0

state = DroneState()


def get_key() -> str:
    """获取单个按键 (非阻塞, 终端原始模式)"""
    import termios
    import fcntl
    import os

    fd = sys.stdin.fileno()
    oldterm = termios.tcgetattr(fd)
    newattr = termios.tcgetattr(fd)
    newattr[3] = newattr[3] & ~termios.ICANON & ~termios.ECHO
    termios.tcsetattr(fd, termios.TCSANOW, newattr)

    oldflags = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, oldflags | os.O_NONBLOCK)

    try:
        c = sys.stdin.read(1)
        if c:
            # 处理 ESC 序列 (方向键)
            if c == '\x1b':
                more = sys.stdin.read(2)
                if more == '[A':
                    return 'UP'
                elif more == '[B':
                    return 'DOWN'
                elif more == '[C':
                    return 'RIGHT'
                elif more == '[D':
                    return 'LEFT'
                return 'ESC'
            return c
        return ''
    finally:
        termios.tcsetattr(fd, termios.TCSANOW, oldterm)
        fcntl.fcntl(fd, fcntl.F_SETFL, oldflags)


def keyboard_listener():
    """在单独线程中监听键盘输入"""
    logger.info("键盘监听线程已启动")
    while state.running:
        try:
            key = get_key()
            if key:
                state.last_input = key
                handle_key_command(key)
            time.sleep(0.05)
        except Exception:
            break


def handle_key_command(key: str):
    """处理按键命令"""
    # 方向键 / WASD - 水平速度
    if key == 'UP' or key.lower() == 'w':
        state.vx = min(state.vx + VELOCITY_STEP * 0.5, VELOCITY_MAX)
        print(f"\r  ↑ 前进 vx={state.vx:.1f} m/s    ", end='', flush=True)

    elif key == 'DOWN' or key.lower() == 's':
        state.vx = max(state.vx - VELOCITY_STEP * 0.5, -VELOCITY_MAX)
        print(f"\r  ↓ 后退 vx={state.vx:.1f} m/s    ", end='', flush=True)

    elif key == 'RIGHT' or key.lower() == 'd':
        state.vy = min(state.vy + VELOCITY_STEP * 0.5, VELOCITY_MAX)
        print(f"\r  → 右移 vy={state.vy:.1f} m/s    ", end='', flush=True)

    elif key == 'LEFT' or key.lower() == 'a':
        state.vy = max(state.vy - VELOCITY_STEP * 0.5, -VELOCITY_MAX)
        print(f"\r  ← 左移 vy={state.vy:.1f} m/s    ", end='', flush=True)

    # Q/E - 升降
    elif key.lower() == 'q':
        state.vz = -min(abs(state.vz) + VELOCITY_STEP * 0.5, VELOCITY_MAX)
        print(f"\r  ↑ 上升 vz={state.vz:.1f} m/s    ", end='', flush=True)

    elif key.lower() == 'e':
        state.vz = min(abs(state.vz) + VELOCITY_STEP * 0.5, VELOCITY_MAX)
        print(f"\r  ↓ 下降 vz={state.vz:.1f} m/s    ", end='', flush=True)

    # 特殊功能键
    elif key == ' ':
        print("\r  🚁 请求起飞                  ", end='', flush=True)

    elif key.lower() == 'l':
        print("\r  🛬 请求降落                  ", end='', flush=True)

    elif key.lower() == 'r':
        print("\r  🏠 请求返航                  ", end='', flush=True)

    elif key.lower() == 'h':
        state.vx = 0; state.vy = 0; state.vz = 0
        print("\r  ⏸  悬停                      ", end='', flush=True)

    elif key.lower() == 't':
        print("\r  🔓 请求解锁 (Arm)            ", end='', flush=True)

    elif key == '\x1b' or key == 'ESC':
        print("\r  👋 退出                      ", end='', flush=True)
        state.running = False


def print_controls():
    """打印控制键说明"""
    controls = """
╔══════════════════════════════════════════╗
║      PX4 无人机键盘控制                   ║
╠══════════════════════════════════════════╣
║  W/↑ 前进    S/↓ 后退    Q 上升          ║
║  A/← 左移    D/→ 右移    E 下降          ║
║  ════════════════════════════════════════ ║
║  Space = 起飞    L = 降落   R = 返航      ║
║  T = 解锁(arm)   H = 悬停   ESC = 退出    ║
╚══════════════════════════════════════════╝
"""
    print(controls)


async def connect_drone() -> System:
    """连接到 PX4 SITL"""
    drone = System()
    await drone.connect(system_address=SITL_ADDRESS)
    logger.info("等待连接无人机...")
    async for conn in drone.core.connection_state():
        if conn.is_connected:
            logger.info("✓ 无人机已连接")
            break
    return drone


async def wait_for_gps(drone: System):
    """等待 GPS 定位"""
    logger.info("等待 GPS 定位...")
    async for health in drone.telemetry.health():
        if health.is_global_position_ok:
            logger.info("✓ GPS 定位完成")
            break


async def update_telemetry(drone: System):
    """后台更新遥测数据"""
    async for position in drone.telemetry.position():
        state.altitude = position.relative_altitude_m
    async for in_air in drone.telemetry.in_air():
        state.is_in_air = in_air
    async for armed in drone.telemetry.armed():
        state.is_armed = armed
    # 简化: 只取第一个值
    async for position in drone.telemetry.position():
        state.altitude = position.relative_altitude_m
        break
    async for in_air in drone.telemetry.in_air():
        state.is_in_air = in_air
        break
    async for armed in drone.telemetry.armed():
        state.is_armed = armed
        break


async def velocity_control_loop(drone: System):
    """速度控制主循环 (Offboard 模式)"""
    logger.info("启动 Offboard 速度控制循环...")

    # 设置初始速度为零
    await drone.offboard.set_velocity_ned(VelocityNedYaw(0.0, 0.0, 0.0, 0.0))

    logger.info("启动 Offboard 模式...")
    try:
        await drone.offboard.start()
        state.in_offboard = True
        logger.info("✓ Offboard 模式已启动")
    except OffboardError as e:
        logger.error(f"启动 Offboard 模式失败: {e}")
        logger.info("改用 Action API (起飞/降落/返航)")
        return

    while state.running and state.in_offboard:
        if state.last_input == ' ' and not state.is_in_air:
            # 起飞: 切换到动作模式
            await drone.offboard.stop()
            state.in_offboard = False
            await drone.action.arm()
            await drone.action.takeoff()
            await asyncio.sleep(5)
            # 重新进入 Offboard
            await drone.offboard.set_velocity_ned(VelocityNedYaw(0.0, 0.0, 0.0, 0.0))
            try:
                await drone.offboard.start()
                state.in_offboard = True
            except OffboardError:
                pass
        elif state.last_input.lower() == 'l' and state.is_in_air:
            await drone.offboard.stop()
            state.in_offboard = False
            await drone.action.land()
        elif state.last_input.lower() == 'r' and state.is_in_air:
            await drone.offboard.stop()
            state.in_offboard = False
            await drone.action.return_to_launch()
        elif state.last_input.lower() == 'h':
            state.vx = 0; state.vy = 0; state.vz = 0
        elif state.last_input.lower() == 't' and not state.is_armed:
            try:
                await drone.action.arm()
                logger.info("✓ 已解锁 (Armed)")
            except ActionError as e:
                logger.error(f"解锁失败: {e}")
        elif state.last_input == '\x1b':
            state.running = False

        # 发送速度指令 (Offboard 需要 2Hz+ 持续发送)
        if state.in_offboard:
            await drone.offboard.set_velocity_ned(
                VelocityNedYaw(state.vx, state.vy, state.vz, state.yaw)
            )

        await asyncio.sleep(0.2)  # 5Hz 控制频率


async def main():
    """主函数"""
    print_controls()
    time.sleep(0.5)  # 让用户看到控制说明

    drone = await connect_drone()
    await update_telemetry(drone)

    # 启动键盘监听线程
    listener_thread = threading.Thread(target=keyboard_listener, daemon=True)
    listener_thread.start()

    # 启动速度控制
    await velocity_control_loop(drone)

    # 清理
    if state.in_offboard:
        try:
            await drone.offboard.stop()
        except OffboardError:
            pass
    try:
        await drone.action.disarm()
    except ActionError:
        pass

    logger.info("已断开连接, 再见!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("用户中断")
    finally:
        state.running = False
