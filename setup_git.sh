#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "=== 初始化 Git 仓库 ==="
git init
git checkout -b main
git add -A

echo "=== 创建提交 ==="
git commit -m "Initial commit: PX4 drone control scripts

- drone_control.py: autonomous takeoff, waypoint flight, return, land
- drone_keyboard.py: real-time keyboard control via MAVSDK
- README.md: usage documentation"

echo "=== 创建 GitHub 仓库 ==="
gh repo create zhanghouxin07/px4-drone-control --public --source=. --remote=origin --push

echo "=== 完成 ==="
gh repo view zhanghouxin07/px4-drone-control
