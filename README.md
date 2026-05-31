# OpenCode Agent Status LED

基于 ESP32-S3 的 OpenCode AI Agent 状态指示灯。通过红绿灯模块实时显示 agent 的工作状态，无需看屏幕即可知道 agent 是否在忙碌、提问或出错。

## 灯效

| 状态 | LED | 含义 |
|------|-----|------|
| IDLE | 🟢 绿灯常亮 | agent 空闲，等待输入 |
| EXECUTING | 🟡 黄灯常亮 | agent 正在执行任务（thinking、输出、等待子任务） |
| QUESTION | 🟢🟡 交替闪烁 | agent 向用户提问，需要用户决策 |
| ERROR | 🔴 红灯常亮 | agent 出错（连续 3 次错误后锁定，需 RESET） |
| DISCONNECTED | 🔴 红灯快闪 | 监控程序未运行或 USB 断开 |

## 硬件接线

```
ESP32-S3          LED 模块
  GPIO4  ───────── G（绿灯）
  GPIO5  ───────── Y（黄灯）
  GPIO6  ───────── R（红灯）
  GND    ───────── GND
```

- 开发板：ESP32-S3（CH340 USB-UART）
- LED 模块：共阴三色交通灯模块，每路串 220Ω 限流电阻
- 供电：USB 接口取电，无需外部电源

## 使用教程

### 环境要求

- Windows 10/11
- Python 3.11+
- PlatformIO CLI（`pip install platformio`）
- Node.js（OpenCode 自带）

### 第一步：安装依赖

```powershell
scripts\setup.bat
```

### 第二步：烧录固件

> ⚠️ **仅首次或固件更新时需要**。固件写入 Flash，拔电不丢失，换电脑无需重烧。

```powershell
# 查看 ESP32 对应的 COM 端口
pio device list

# 烧录（替换 COMx 为实际端口，如 COM3、COM9）
pio run -t upload --upload-port COMx
```

烧录成功后，ESP32 自动重启，绿灯亮起表示就绪。

### 第三步：配置 OpenCode 插件

插件已配置在 `opencode.json` 中：

```json
{
  "plugin": ["./scripts/agent-led-plugin.mjs"]
}
```

**重启 OpenCode** 即可自动加载插件。插件会实时监听 agent 状态变化并写入状态文件。

### 第四步：启动监控

```powershell
scripts\start_monitor.bat
```

启动后：
- 绿灯常亮 = 系统就绪
- agent 工作时自动切换黄灯
- 提问时绿黄交替闪烁
- 出错时红灯

按 `Ctrl+C` 停止监控。

> 💡 **提示**：如果 COM 端口不是 COM9，修改 `scripts\start_monitor.bat` 中的端口号，或使用：
> ```powershell
> python scripts\agent_bridge.py | python scripts\agent_relay.py --port COMx -v
> ```

### 日常使用流程

```
1. 插上 ESP32 USB
2. 打开 OpenCode
3. 运行 scripts\start_monitor.bat
4. 正常使用 OpenCode，灯会自动变化
```

## 工作原理

```
OpenCode 内部事件流
  ↓ session.status (busy/idle)、session.error、question.asked
agent-led-plugin.mjs（Node.js 插件，自动检测）
  ↓ 写入文件
.omo/agent_state
  ↓ 0.3s 轮询
agent_bridge.py（Python 桥接）
  ↓ stdout 管道
agent_relay.py（Python 串口中继）
  ↓ USB 串口 115200 baud
ESP32 固件（Arduino C++ 状态机）
  ↓ GPIO 4/5/6
🟢🟡🔴 LED
```

## 项目结构

```
├── platformio.ini              # PlatformIO 构建配置
├── opencode.json               # OpenCode 插件注册
├── src/                        # ESP32 固件（Arduino C++）
│   ├── main.cpp                # 主循环 + 优先级状态机 + 心跳看门狗
│   ├── led_controller.h/cpp    # 非阻塞 millis() LED 控制
│   ├── serial_protocol.h/cpp   # 8 命令串口解析器
│   └── pin_config.h            # GPIO 引脚定义
├── scripts/                    # PC 端
│   ├── agent-led-plugin.mjs    # OpenCode 事件插件（自动状态检测）
│   ├── agent_bridge.py         # 状态文件监听桥接
│   ├── agent_relay.py          # 串口命令中继 + 心跳
│   ├── start_monitor.bat       # 一键启动监控
│   └── setup.bat               # 依赖安装脚本
├── specs/                      # 设计文档
└── test/                       # 单元测试
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
