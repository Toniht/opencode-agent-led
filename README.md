# OpenCode Agent Status LED

基于 ESP32-S3 的 OpenCode AI Agent 状态指示灯。通过红绿灯模块实时显示 agent 的工作状态，无需看屏幕即可知道 agent 是否在忙碌、提问或出错。

## 灯效

| 状态 | LED 效果 | 含义 |
|------|----------|------|
| IDLE | 🟢 绿灯呼吸（2s 正弦波） | agent 空闲，等待输入 |
| EXECUTING | 🟡 黄灯常亮 | agent 正在执行任务（thinking、输出、子任务） |
| QUESTION | 🟢🟡 交替闪烁（1Hz） | agent 向用户提问，需要用户决策 |
| ERROR | 🔴 红灯慢闪（~0.625Hz，约 1.6s 周期） | agent 出错（连续 3 次后锁定，需发 RESET 解锁） |
| DISCONNECTED | 🔴 红灯快闪（2Hz） | 监控程序未运行或 USB 断开 |
| SILENT | 全灭 | 静默覆盖模式，保留底层状态 |

> 状态优先级（高 → 低）：`ERROR > QUESTION > EXECUTING > IDLE > DISCONNECTED`。
> SILENT 为特殊覆盖层，可叠加在任何状态之上，退出时恢复原状。

## 硬件接线

```
ESP32-S3          LED 模块
  GPIO4  ───────── G（绿灯）
  GPIO5  ───────── Y（黄灯）
  GPIO6  ───────── R（红灯）
  GND    ───────── GND
```

- 开发板：ESP32-S3-R16N8（原生 USB CDC，非 CH340）
- LED 模块：共阴三色交通灯模块，每路串 220Ω 限流电阻
- 供电：USB 总线供电，无需外部电源

## 使用教程

### 一行命令安装

```powershell
# Windows
scripts\install.bat

# Linux / macOS
bash scripts/install.sh
```

> 自动完成：Python 依赖 → ESP32 检测 → 固件烧录 → 用户级插件注册。
> 已有 ESP32 固件可跳过烧录：`scripts\install.bat --plugin-only`

### 日常使用

1. 插上 ESP32 USB
2. 打开 OpenCode → 插件自动加载 → 绿灯呼吸 = 就绪
3. 正常使用，灯自动随 agent 状态变化

### 独立测试（不启动 OpenCode）

```powershell
node scripts\test-publisher.mjs                    # 完整序列
node scripts\test-publisher.mjs --sequence quick   # 快速测试
node scripts\test-publisher.mjs --dry-run          # 仅日志
```

### 管理命令

| 操作 | 命令 |
|------|------|
| 一键安装 | `scripts\install.bat` |
| 固件更新 | `scripts\flash.bat` |
| 安全停止 | `scripts\stop_monitor.bat` |
| 独立测试 | `node scripts\test-publisher.mjs` |
| 查看日志 | `.omo\monitor\agent_events.log` |

> ⚠️ **不要使用 `taskkill /IM python.exe`**，会误杀所有 Python 进程。始终用 `stop_monitor.bat`。

## 工作原理

```
OpenCode 内部事件流
  ↓ session.status / session.error / question.asked …（12+ 事件类型）
agent-led-plugin.mjs（Node.js 插件，运行在 OpenCode 进程内）
  ↓ 300ms 防抖 → 直接 stdin 写入命令字符串
agent_relay.py（Python 串口中继，由插件自动 spawn）
  ↓ USB 串口 115200 baud
ESP32 固件（Arduino C++ 优先级状态机）
  ↓ GPIO 4/5/6
🟢🟡🔴 LED
```

**v7 改进**：插件直接通过 stdin 管道向中继发送命令，中间无文件轮询延迟。
独立运行（无需 OpenCode）的场景仍保留 `agent_bridge.py` + `start_monitor.bat` 的管道模式。

## 项目结构

```
├── platformio.ini              # PlatformIO 构建配置
├── opencode.json               # OpenCode 插件注册
├── src/                        # ESP32 固件（Arduino C++）
│   ├── main.cpp                # 主循环 + 优先级状态机 + 心跳看门狗
│   ├── led_controller.h/cpp    # 非阻塞 millis() LED 控制（呼吸/闪烁）
│   ├── serial_protocol.h/cpp   # 8 命令串口解析器 + CRC 校验
│   └── pin_config.h            # GPIO 引脚定义（G=4, Y=5, R=6）
├── scripts/                    # PC 端
│   ├── agent-led-plugin.mjs    # OpenCode v7 事件插件（自动检测 + stdin 直控）
│   ├── agent_relay.py          # 串口命令中继 + 心跳（5s 超时看门狗）
│   ├── agent_bridge.py         # 状态文件监听桥接（独立运行模式）
│   ├── test-publisher.mjs      # 测试序列发生器（完整/快速/模拟运行）
│   ├── install.bat / .sh       # 一键安装：Python 依赖 → 烧录 → 插件注册
│   ├── flash.bat               # 固件烧录快捷命令
│   ├── start_monitor.bat       # 启动监控（bridge → relay 管道）
│   ├── stop_monitor.bat / .ps1 # 安全停止监控程序
│   ├── requirements.txt        # Python 依赖清单
│   └── setup.bat               # Python 依赖安装
├── specs/                      # 设计文档（spec / plan / data-model / contracts）
└── test/                       # 单元测试（Unity 框架）
```

## 故障排除

| 问题 | 原因 | 解决 |
|------|------|------|
| 红灯快闪 | 监控程序未运行或 COM 端口不对 | 运行 `start_monitor.bat`，检查 COM 端口 |
| 启动后一直是黄灯 | 状态文件残留 | 重新运行 `start_monitor.bat`（已自动修复） |
| 黄灯不切回绿灯 | 插件版本过旧 | 更新 `agent-led-plugin.mjs` 并重启 OpenCode |
| 烧录失败 | COM 端口被监控程序占用 | 先 Ctrl+C 停止监控，再烧录 |
| 灯不亮 | 接线错误或 GPIO 配置不对 | 检查 G→4、Y→5、R→6，确认共阴模块 |
| 串口无响应 | 波特率不匹配 | 确认 115200，固件和脚本保持一致 |

## 许可

MIT
