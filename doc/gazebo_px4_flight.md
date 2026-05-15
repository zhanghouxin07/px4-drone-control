# PX4 + Gazebo 仿真飞行调试记录

## 环境

- PX4-Autopilot: `/home/zhanghouxin/PX4-Autopilot`
- 控制脚本: `/home/zhanghouxin/claudeWork/px4-drone-control/`
- 场景世界: `worlds/scene.sdf`（带建筑和树）
- Gazebo: Harmonic (8.11.0)
- MAVSDK-Python: v3.15.0

---

## 快速启动

### 1. 启动 Gazebo + PX4 SITL

```bash
cd ~/PX4-Autopilot

# 默认世界（空地）
make px4_sitl gz_x500

# 带建筑和树的场景世界
PX4_GZ_WORLD=scene make px4_sitl gz_x500

# baylands 地形世界
PX4_GZ_WORLD=baylands make px4_sitl gz_x500
```

首次启动需等待 Gazebo 加载世界和模型（约 30s-2min）。

### 2. 运行控制脚本（新终端）

```bash
cd ~/claudeWork/px4-drone-control

# 位置模式 Offboard 飞行（推荐）
python3 drone_control_offboard.py

# 原始 takeoff 方式
python3 drone_control.py

# 5x5x5 小范围移动
python3 drone_control_small.py
```

### 3. 关闭

```bash
pkill -9 px4
pkill -9 "gz sim"
```

---

## 控制脚本说明

| 脚本 | 方式 | 说明 |
|------|------|------|
| `drone_control.py` | `action.takeoff()` | 原始脚本，起飞后可能卡在 2.5m |
| `drone_control_offboard.py` | Offboard PositionNedYaw | **推荐**，逐步爬升，稳定 |
| `drone_control_robust.py` | `action.takeoff()` + wait armable | 等待 is_armable 再解锁 |
| `drone_control_small.py` | Offboard PositionNedYaw | 5x5x5 小范围移动 |
| `drone_keyboard.py` | 键盘控制 | 支持 W/S/A/D/Q/E/Space 等 |

---

## 关键调试记录

### 无人机解锁失败（COMMAND_DENIED）

原因: `is_armable=False`

解决:
1. 设置 `COM_RCL_EXCEPT=4`（允许无 RC 解锁）
2. 设置 `CBRK_IO_SAFETY=22027`（跳过安全开关）
3. 设置 `CBRK_SUPPLY_CHK=22027`（跳过电源检查）
4. 脚本中等待 `is_armable=True` 后再 arm

### 无人机螺旋桨转但不起飞

原因: `MPC_THR_HOVER` 参数值不对

解决: x500 模型的悬停推力是 **0.60**，不是默认的 0.5
```python
await drone.param.set_param_float("MPC_THR_HOVER", 0.60)
```

### `action.takeoff()` 卡在 2.5m

原因: `MIS_TAKEOFF_ALT` 默认值 2.5m

解决: 设置起飞最低高度
```python
await drone.param.set_param_float("MIS_TAKEOFF_ALT", 10.0)
```

推荐改用 Offboard 位置模式（`drone_control_offboard.py`），更可控。

### 停机坪碰撞导致无法起飞

`scene.sdf` 中停机坪在原点有碰撞体，与无人机生成位置重叠。

解决: 移除停机坪碰撞（仅保留 visual），或把停机坪移到远处。

### 每次重启 Gazebo 后再飞

PX4 状态会累积，多次飞行后可能出现解锁失败等问题。

推荐每次飞行前重启：
```bash
pkill -9 px4; pkill -9 "gz sim"
PX4_GZ_WORLD=scene make px4_sitl gz_x500
```

### 网络 DNS 问题（WSL2）

WSL2 下偶尔 github.com DNS 解析失败，可用 `gh` CLI 推送：
```bash
git remote set-url origin https://github.com/zhanghouxin07/px4-drone-control.git
git config --global credential.helper /usr/bin/gh
git push origin main
```

---

## 场景世界构成

`worlds/scene.sdf` 包含：

| 元素 | 数量 | 说明 |
|------|------|------|
| 建筑 | 6 | 不同尺寸的 box，分布在原点周围 |
| 树 | 5 | 树干(box) + 树冠(sphere) |
| 停机坪 | 0 | 已移除（碰撞干扰） |
| 道路线 | 1 | 视觉参考线 |

使用: 将 `worlds/scene.sdf` 复制到 `~/PX4-Autopilot/Tools/simulation/gz/worlds/`，然后 `PX4_GZ_WORLD=scene make px4_sitl gz_x500`

---

## Git 仓库

```bash
cd ~/claudeWork/px4-drone-control
git remote -v
# origin  https://github.com/zhanghouxin07/px4-drone-control.git
```
