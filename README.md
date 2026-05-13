# PX4 Drone Control

Python scripts for controlling PX4 drones in Gazebo simulation via MAVSDK.

## Requirements

- Python 3.6+
- [MAVSDK-Python](https://mavsdk.mavlink.io/main/en/python/)
- PX4 SITL + Gazebo (for simulation)

```bash
pip3 install mavsdk
```

## Scripts

### 1. Auto Flight Mission (`drone_control.py`)
Autonomous takeoff → waypoint flight → return → land.

```bash
python3 drone_control.py
```

### 2. Keyboard Control (`drone_keyboard.py`)
Real-time keyboard control with velocity commands.

```bash
python3 drone_keyboard.py
```

| Key | Action |
|-----|--------|
| W/↑ | Fly forward |
| S/↓ | Fly backward |
| A/← | Move left |
| D/→ | Move right |
| Q | Ascend |
| E | Descend |
| Space | Takeoff |
| L | Land |
| R | Return to launch |
| H | Hover |
| T | Arm |
| ESC | Exit |

## Usage

1. Start PX4 Gazebo simulation:
   ```bash
   cd ~/PX4-Autopilot && make px4_sitl gz_x500
   ```

2. In another terminal, run a control script:
   ```bash
   python3 drone_control.py
   ```

The script connects to PX4 SITL via UDP (`udpin://0.0.0.0:14540`).

## License

MIT
