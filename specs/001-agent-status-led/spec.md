# Feature Specification: Agent Status LED Indicator

**Feature Branch**: `001-agent-status-led`

**Created**: 2026-05-31

**Status**: Draft

**Input**: User description: "帮我创建一个用于监控opencode中agent状态的程序，我希望当agent正在执行时亮黄灯，允许人类输入时亮绿灯，当agent问出问题时绿灯和黄灯闪烁，当agent出错时亮红灯，或推荐什么情况亮红灯"

## Clarifications

### Session 2026-05-31

- Q: "等待输入"与"空闲"是否是同一状态？提问的含义是什么？ → A: 等待输入即空闲状态（灯灭），提问是 agent 主动要求用户输入（绿灯+黄灯闪烁）
- Q: 空闲状态是否亮灯？ → A: 空闲亮绿灯（常亮），表示系统就绪、可接收输入

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Agent Executing Indicator (Priority: P1)

用户坐在电脑前使用 OpenCode，希望在不看屏幕的情况下就能知道 AI agent 是否正在忙碌执行任务。系统空闲时绿灯常亮表示就绪，开始执行时切换为黄灯，让用户一目了然。

**Why this priority**: 这是最基础的"正在工作"信号，即使在最小可行产品中也必须提供。用户需要知道 agent 是否在工作，这是所有其他状态的基础对比参照。

**Independent Test**: 通过 OpenCode 触发一个需要 agent 执行的任务（如代码搜索），观察 LED 是否亮起黄灯。可完全独立测试——仅需点亮黄灯即可交付价值。

**Acceptance Scenarios**:

1. **Given** agent 处于空闲状态（绿灯亮），**When** 用户发送任务让 agent 开始执行，**Then** 绿灯熄灭，黄色 LED 立即亮起
2. **Given** agent 正在执行任务（黄灯亮），**When** agent 完成执行，**Then** 黄色 LED 熄灭，绿色 LED 亮起（回到空闲）
3. **Given** 监控设备刚接通电源，**When** 尚未收到任何 agent 状态信号，**Then** 绿色 LED 亮起（默认空闲状态）

---

### User Story 2 - Agent Question Indicator (Priority: P2)

用户希望被突出提醒 agent 主动提出了需要回答的问题。与 agent 在空闲状态（绿灯常亮）下被动等待用户随时输入不同，agent 的主动提问意味着它遇到了困惑、需要用户立即决策，是必须关注的紧急信号。

**Why this priority**: 主动提问是 agent 执行流程中的关键决策点——闪烁信号比常亮更具视觉冲击力，能有效减少用户错过关键决策的几率。区别于空闲状态（绿灯常亮），此信号明确表示"agent 在等你回答问题"。

**Independent Test**: 触发 agent 发出一个明确的问题（如选项确认），观察绿色和黄色 LED 是否同时闪烁。可独立测试——即使没有其他 LED 状态，只要闪烁模式正确即可交付价值。

**Acceptance Scenarios**:

1. **Given** agent 完成执行后发现需要用户决策，**When** agent 主动向用户提出问题，**Then** 绿色和黄色 LED 以 1Hz 同步闪烁（占空比 50%）
2. **Given** 绿灯和黄灯正在闪烁（agent 提问中），**When** 用户回答后 agent 继续执行，**Then** 闪烁停止，黄色 LED 常亮（回到执行状态）
3. **Given** 绿灯和黄灯正在闪烁，**When** 用户尚未回答但 agent 超时自动取消提问，**Then** 闪烁停止，绿色 LED 常亮（回到空闲状态）

---

### User Story 3 - Agent Error Indicator (Priority: P1)

用户需要立即感知 agent 出现错误，以便及时干预。错误可能包括代码执行失败、工具调用异常、连续失败等。

**Why this priority**: 与 P1 同为最高优先级。错误是用户必须立即关注的事件——agent 不会自动从错误中恢复，延误响应意味着浪费时间。

**Independent Test**: 触发 agent 产生一个错误（如不存在的文件路径），观察红色 LED 是否亮起。可独立测试，仅需亮红灯即可交付价值。

**Acceptance Scenarios**:

1. **Given** agent 正在执行任务，**When** agent 执行过程中发生错误（工具调用失败、异常），**Then** 红色 LED 立即亮起，其他 LED 熄灭
2. **Given** 红灯亮起（agent 出错），**When** 用户查看错误并手动重置/继续，**Then** 红灯熄灭，系统回到当前状态对应的 LED 指示
3. **Given** agent 连续发生多次错误，**When** 累计错误次数超过阈值（建议 3 次），**Then** 红色 LED 保持常亮不自动恢复

---

### User Story 4 - Connection Loss / System Fault Indicator (Priority: P2)

用户需要知道监控系统本身是否正常工作。当 PC 端与 ESP32 的连接断开，或 ESP32 硬件出现异常时，应有明确警告。

**Why this priority**: 如果监控系统本身故障，用户可能误以为 agent 状态正常而错过关键事件。连接状态是监控系统可靠性的基础保障。

**Independent Test**: 物理断开 ESP32 的 USB 连接，观察红灯是否以特定模式闪烁。可独立测试。

**Acceptance Scenarios**:

1. **Given** ESP32 通过 USB 正常连接，**When** USB 线缆被拔出或 PC 端监控程序停止发送心跳，**Then** 红色 LED 以 2Hz 快速闪烁（区别于常亮红灯的错误状态）
2. **Given** 红灯快速闪烁（连接丢失），**When** USB 重新连接且心跳恢复，**Then** 红灯停止闪烁，恢复到当前 agent 状态对应的 LED 指示
3. **Given** ESP32 上电运行中，**When** ESP32 自身出现硬件异常（看门狗复位、电压异常），**Then** 红灯常亮

---

### Edge Cases

- 多个状态信号几乎同时到达时，系统如何确定优先级？（Error > Question > Executing > Idle）
- ESP32 上电启动到接收到第一个状态信号之间的过渡期如何处理？（建议：绿灯常亮，视为空闲状态等待首次信号）
- 用户希望暂停监控时如何处理？（建议：支持通过串口发送静音命令关闭所有 LED）
- LED 长时间点亮（数小时 agent 执行中）是否有烧毁风险？（建议：LED 为低功耗设计，不存在此问题）
- 串口通信出现数据帧损坏或乱码时如何容错？（建议：校验和校验，无效帧丢弃，连续 N 帧无效则触发连接丢失警告）

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: 系统 MUST 在空闲状态时点亮绿色 LED（常亮），表示系统就绪
- **FR-002**: 系统 MUST 在 agent 开始执行任务时熄灭绿色 LED，立即点亮黄色 LED
- **FR-003**: 系统 MUST 在 agent 完成执行（非错误退出）时熄灭黄色 LED，点亮绿色 LED（回到空闲）
- **FR-004**: 系统 MUST 在 agent 主动向用户提出问题时使绿色和黄色 LED 同时闪烁（闪烁频率约 1Hz，占空比 50%）
- **FR-005**: 系统 MUST 在 agent 发生错误时点亮红色 LED（常亮模式）
- **FR-006**: 系统 MUST 在累计连续错误达到 3 次时保持红色 LED 常亮且不自动恢复
- **FR-007**: 系统 MUST 在 PC 端心跳信号超时（建议 5 秒无信号）时以快速闪烁模式（2Hz）点亮红色 LED
- **FR-008**: 系统 MUST 支持状态优先级机制：错误 > 提问 > 执行中 > 空闲
- **FR-009**: 系统 MUST 在重置/恢复后自动回到当前实际 agent 状态对应的 LED 指示
- **FR-010**: 系统 MUST 通过 USB 串口接收 PC 端的状态指令（遵守项目 USB-only 约束）
- **FR-011**: 系统 MUST 对无效或损坏的串口数据帧进行校验并丢弃，连续 10 帧无效视为连接丢失
- **FR-012**: 系统 SHOULD 支持通过串口发送静音命令以临时关闭所有 LED 指示

### Key Entities

- **AgentState**: agent 的当前状态，包括：Idle（空闲/等待输入 — 绿灯常亮）、Executing（执行中 — 黄灯常亮）、Questioning（提问中 — agent 主动要求用户输入，绿灯+黄灯闪烁）、Error（错误 — 红灯常亮）、Disconnected（断开连接 — 红灯快闪）
- **LEDSignal**: 物理 LED 的输出信号，定义每个 LED 的颜色和闪烁模式。包含 Green、Yellow、Red 三个通道，每个通道有 Off、On、SlowBlink（1Hz）、FastBlink（2Hz）四种模式
- **StatusCommand**: PC 端通过串口发送的状态指令，包含状态类型和可选参数

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 用户在不看屏幕的情况下，仅通过 LED 指示灯即可判断 agent 是否在忙碌，准确率达到 100%
- **SC-002**: 从 agent 状态变化到 LED 指示变化的总延迟不超过 500 毫秒
- **SC-003**: 在连续 10 分钟高强度状态切换测试中，LED 指示与实际 agent 状态的一致性达到 99.9% 以上（即不失帧、不错位）
- **SC-004**: 用户能在 3 秒内注意到 agent 错误信号（红灯），并在 1 秒内注意到 agent 提问信号（闪烁），从而缩短平均响应时间
- **SC-005**: USB 断开后，红灯快闪警报在 6 秒内（5 秒超时 + 1 秒容错）触发
- **SC-006**: 串口通信在 115200 波特率下数据帧错误率低于 0.01%，错误帧全部被正确丢弃不影响 LED 状态

## Assumptions

- ESP32 开发板通过 USB 线缆与运行 OpenCode 的 PC 始终保持有线连接（符合项目宪法 Hardware Constraints）
- 使用三颗独立 LED（绿、黄、红）或一个 RGB LED 模块，所有 LED 为共阴或共阳配置
- PC 端存在 OpenCode 的 hook/plugin 机制或事件流，能够实时获取 agent 状态变化事件
- 串口通信波特率默认 115200，使用简单的文本协议或二进制帧协议
- 用户处于同一物理空间，能看到 LED 指示灯（典型桌面距离 0.5-2 米）
- 监控设备仅用于状态指示，不参与 agent 的实际执行逻辑
- 监控设备不需要独立供电（从 USB 接口取电）
