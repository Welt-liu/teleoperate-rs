# teleoperate-rs

B601-RS 最简 demo：双臂遥操作、单臂录制、单臂循环回放。不依赖 Isaac Sim。

RS 臂走 **motorbridge**；录制时 RS leader 额外用 **reBotArm_control_py demo 9** 的 MIT + Pinocchio `g(q)`。只有 **102 leader** 仍用 PyPI。URDF / MeshCat 网格来自同级仓库 `Rebot_Arm_description`。

| 角色 | 实现 | 类型名 |
| --- | --- | --- |
| B601-RS leader（遥操） | motorbridge（MIT kp=0 拖动读编码器） | `seeed_b601_rs_leader` |
| B601-RS leader（录制） | demo 9 `GravityCompensation` + MeshCat | `seeed_b601_rs_leader` |
| reBot Arm 102 leader | `lerobot-teleoperator-rebot-arm-102` | `rebot_arm_102_leader` |
| B601-RS follower | motorbridge（YAML MIT + 夹爪阻抗） | `seeed_b601_rs_follower` |

默认组合：**RS leader `can0` + RS follower `can1`，夹爪比例 3**。

本仓库按 **macOS + Linux** 写端口探测。串口名字会随 USB 口变化，不要写死 Linux 的 `/dev/ttyUSB0`。

## 1. 新建 conda 环境

Python 3.10+，推荐 3.12。

```bash
cd ~/teleoperate-rs   # 或本仓库实际路径

conda env create -f environment.yml
conda activate teleoperate-rs
pip install -e .

# macOS + PEAK PCAN：补 PCBUSB 裸名符号链接，并写入 conda 激活脚本
./scripts/setup_macos_pcan.sh
conda deactivate && conda activate teleoperate-rs
```

检查依赖是否可见：

```bash
python -c "import motorbridge, lerobot_teleoperator_rebot_arm_102, pinocchio, meshcat; print('ok')"
python -m teleoperate_rs --help
python -m teleoperate_rs ports
```

录制 / 回放的 MeshCat 还需要同级的 `reBotArm_control_py` 和 `Rebot_Arm_description`（或设置 `REBOTARM_CONTROL_PY` / `REBOT_ARM_DESCRIPTION`）。已有环境补 Pinocchio 和 meshcat：

```bash
conda install -n teleoperate-rs -c conda-forge pinocchio
pip install meshcat pyyaml
```


已有环境若还装着旧的 Seeed PyPI 包，卸掉再重装本仓库：

```bash
pip uninstall -y lerobot-robot-seeed-b601 lerobot-teleoperator-seeed-b601
pip install -e .
```

## 2. 端口（macOS 必看）

先插硬件，再列设备：

```bash
python -m teleoperate_rs ports
ls /dev/cu.usb* /dev/tty.usb*
```

| 用途 | Linux | macOS |
| --- | --- | --- |
| B601-RS CAN（PCAN） | `can0` / `can1`，需 `ip link` | 仍写 `can0` / `can1`（motorbridge → `PCAN_USBBUS1/2`），**不要** `ip link`；需 MacCAN PCBUSB（裸名 `PCBUSB`） |
| 102 UART | `/dev/ttyUSB0` | `/dev/cu.usbserial-*` 或 `/dev/cu.usbmodem*`（优先 `cu`，不要用 `ttyUSB0`） |

102 未指定 `--leader-port` 时：只有一个 USB 串口就自动用；多个则列出并要求手动指定。口换了就再跑一次 `ports`。

### Linux CAN

```bash
sudo ip link set can0 up type can bitrate 1000000
sudo ip link set can1 up type can bitrate 1000000
```

### macOS CAN（PCBUSB）

`libPCBUSB.dylib` 无法加载时，请先安装 PCBUSB：

```bash
curl -L -o macOS_Library_for_PCANUSB_v0.13.tar.gz \
  https://raw.githubusercontent.com/tianrking/motorbridge/main/third_party/pcan/macos/macOS_Library_for_PCANUSB_v0.13.tar.gz
tar -xzf macOS_Library_for_PCANUSB_v0.13.tar.gz
cd PCBUSB
sudo ./install.sh
```

`install.sh` 只会安装 `libPCBUSB.dylib`。motorbridge 的原生加载器 dlopen 的是裸名 `PCBUSB`，因此需要补这个符号链接。否则即使 `libPCBUSB.dylib` 的 ctypes 检查能通过，连接机械臂仍会报 `load PCBUSB failed`：

```bash
sudo ln -sf /usr/local/lib/libPCBUSB.dylib /usr/local/lib/PCBUSB
```

配置 `DYLD_FALLBACK_LIBRARY_PATH`，确保 motorbridge 运行时能找到 PCBUSB。请优先使用 FALLBACK，不要用 `DYLD_LIBRARY_PATH`：后者会覆盖整个进程的 dyld 默认搜索顺序，可能影响其他软件。在 conda 环境中创建激活脚本，每次 `conda activate teleoperate-rs` 自动生效：

```bash
mkdir -p "$CONDA_PREFIX/etc/conda/activate.d"
cat > "$CONDA_PREFIX/etc/conda/activate.d/pcbusb_dyld.sh" << 'EOF'
export DYLD_FALLBACK_LIBRARY_PATH="/usr/local/lib${DYLD_FALLBACK_LIBRARY_PATH:+:$DYLD_FALLBACK_LIBRARY_PATH}"
EOF

conda deactivate && conda activate teleoperate-rs
echo $DYLD_FALLBACK_LIBRARY_PATH
```

可选、无需 sudo（适合共用开发机）：安装到 `~/.local/lib`。若本地已有 motorbridge 源码树：

```bash
./scripts/setup_pcbusb_macos.sh --user-local
ln -sf "$HOME/.local/lib/libPCBUSB.dylib" "$HOME/.local/lib/PCBUSB"
```

本仓库也可以一键做符号链接 + conda 激活脚本（库已装时不必再 sudo）：

```bash
./scripts/setup_macos_pcan.sh
# 还没装库: ./scripts/setup_macos_pcan.sh --install
# 无 sudo:   ./scripts/setup_macos_pcan.sh --user-local
```

用户目录安装时，把上面 conda 激活脚本中的路径改成 `$HOME/.local/lib`，而不是 `/usr/local/lib`。

检查是否就绪。请先插入 PCAN 适配器。`ctypes.CDLL('libPCBUSB.dylib')` 不能作为运行时检查，motorbridge 实际不会加载这个名字：

```bash
python -m teleoperate_rs ports
python - <<'PY'
import ctypes
ctypes.CDLL("PCBUSB")
print("PCBUSB load OK")
PY
```

插上 PEAK PCAN 后直接用 `can0` / `can1`。不要同时跑其它占用同一适配器的进程。

## 3. 启动前的零点核对

连接后、开始跟随时，程序会读 leader / follower 全部关节角。任一关节绝对值超过 **±10 deg**（`--zero-tolerance-deg`）：

- **teleop**：打日志列出超差关节，**不退出**。follower 先保持当前姿态；**按回车**（或空格）后做 **3 秒**余弦过渡到当前 leader，和遥操里再按空格恢复相同。
- **record / play**：直接退出，避免带着错误零位开力矩。

启动前请尽量把臂放到机械零位、夹爪闭合。调试才允许 `--skip-zero-check`。

## 4. 双臂遥操作

```bash
conda activate teleoperate-rs
cd ~/teleoperate-rs

python -m teleoperate_rs teleop --gripper-scale 3
# 或: ./scripts/teleop.sh --gripper-scale 3
```

默认：

- leader: `seeed_b601_rs_leader` @ `can0`
- follower: `seeed_b601_rs_follower` @ `can1`

操作：

| 键 | 作用 |
| --- | --- |
| 空格 | 暂停：follower 保持当前姿态 |
| 再按空格 | 恢复：follower **3 秒**余弦过渡到当前 leader，不跳变 |
| 回车 | 仅当启动时角度超差（或已暂停）：与「再按空格」相同，3 秒过渡后继续 |
| Ctrl+C | 退出；follower 余弦回编码器零点（约 5s） |

用 102 当 leader、RS 当 follower（先 `python -m teleoperate_rs ports` 看串口）：

```bash
# macOS：把端口换成 ports 列出来的 cu.usb*
python -m teleoperate_rs teleop \
  --leader-type rebot_arm_102_leader \
  --leader-port /dev/cu.usbserial-1140 \
  --follower-type seeed_b601_rs_follower \
  --follower-port can0 \
  --gripper-scale 3
```

只有一个 USB 串口时可以省略 `--leader-port`。102 或 RS 启动时不在零点附近，会先打超差日志，按回车后再 3 秒对齐，不会直接退出。

## 5. 单臂录制 / 回放

同一条臂：先当 leader 手拖录制（默认 **demo 9 重力补偿** + **MeshCat**），再当 follower 循环播放（同样开 MeshCat）。夹爪比例默认 3。需要同级 `reBotArm_control_py` 和 `Rebot_Arm_description`。周期日志只有 `t=` / `frames=` 或 `loop=` / `frame=`，关节角看浏览器，不打到终端。

- **record** `Ctrl+C`：保存 `datasets/rs_motions/motion_*.npz`，然后和 play 一样余弦回编码器零点（约 5s）再断开。
- **play** `Ctrl+C`：follower 余弦回到编码器零点（约 5s）。

```bash
conda activate teleoperate-rs
cd ~/teleoperate-rs
# Linux 还需: sudo ip link set can0 up type can bitrate 1000000

python -m teleoperate_rs record --gripper-scale 3
python -m teleoperate_rs record --name pick
python -m teleoperate_rs record --no-meshcat          # 不要浏览器窗口
python -m teleoperate_rs record --no-gravity-compensation  # 只要拖动读编码器

python -m teleoperate_rs play --gripper-scale 3
python -m teleoperate_rs play --motion datasets/rs_motions/motion_20260820_121305.npz
python -m teleoperate_rs play --no-meshcat
```

`--rate 0`（回放默认）表示使用文件里记录的频率。

## 6. 常用参数

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `--leader-type` | `seeed_b601_rs_leader` | RS 走 motorbridge；102 用 `rebot_arm_102_leader`（PyPI） |
| `--follower-type` | `seeed_b601_rs_follower` | motorbridge RS follower |
| `--leader-port` / `--follower-port` | `can0` / `can1` | 102 未指定时自动探测 USB 串口 |
| `--gripper-scale` | `3` | 相对连接姿态的夹爪比例 |
| `--gravity-compensation` | 开（仅 record / RS） | demo 9 MIT + Pinocchio `g(q)`；`--no-gravity-compensation` 关掉 |
| `--meshcat` | 开（record / play） | 浏览器显示 `Rebot_Arm_description` URDF；`--no-meshcat` 关掉 |
| `--zero-tolerance-deg` | `10` | 零点核对容差 |
| `--resume-duration` | `3` | 遥操恢复过渡时间（秒） |
| `--approach-duration` | `2` | 回放每圈贴近起点的时间（秒） |

## 7. 模块划分（方便后续改 demo）

```
teleoperate_rs/
  constants.py          默认值、关节名、设备类型白名单
  exceptions.py         业务异常
  pose.py               关节 dict / LeRobot action 互转
  devices/factory.py    按类型构造 RS motorbridge / demo9 重力 leader / 102 PyPI
  devices/rs_arm.py     motorbridge RS 臂（遥操 leader MIT kp=0 / follower MIT）
  devices/gravity_leader.py  record 用的 demo 9 GravityCompensation
  devices/control_py.py 查找同级 reBotArm_control_py
  viz.py                MeshCat URDF 显示
  devices/can.py        Linux SocketCAN / macOS PCAN（检查裸名 PCBUSB）
  devices/serial.py     USB 串口探测（macOS cu.usb*）
  devices/lifecycle.py  connect(calibrate=False) / disconnect
  safety/zero_check.py  启动前零点核对
  control/mapper.py     夹爪相对比例
  control/blender.py    余弦插值
  control/pause.py      空格暂停 / 3s 恢复状态机
  control/keyboard.py   空格监听
  motion/store.py       npz 读写
  motion/picker.py      方向键选文件
  motion/player.py      循环回放 + 起点过渡
  apps/teleop.py        双臂遥操
  apps/record.py        单臂录制
  apps/play.py          单臂回放
  apps/ports.py         列出本机串口 / CAN
```

后续若要改暂停逻辑、夹爪映射或加新 leader，只动对应模块，不要把控制律写进 CLI。
