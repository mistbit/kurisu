# Kurisu - AI Agent 深度架构设计

本文档详细阐述了 **Kurisu** 项目中 AI Agent 的核心架构设计，旨在帮助开发者理解系统的设计哲学，并为后续的开发提供理论指导。

---

## AI Agent 深度架构设计

Kurisu 的 Agent 不仅仅是一个聊天机器人，而是一个 **具备自主决策能力的金融智能体**。我们采用 **Cognitive Architecture (认知架构)** 的设计理念。

### 1. 核心认知架构 (The Brain)
Agent 的大脑由以下几个关键模块组成：

```mermaid
graph TD
    User[用户指令] --> Perception[感知模块]
    Market[市场数据] --> Perception
    News[新闻资讯] --> Perception
    
    Perception --> Memory[记忆模块 (RAG)]
    Memory --> Planning[规划模块 (Planner)]
    
    subgraph "Reasoning Loop (思考循环)"
        Planning --> Thought[推理/思考]
        Thought --> ToolSelect[工具选择]
        ToolSelect --> Execution[工具执行]
        Execution --> Observation[观察结果]
        Observation --> Thought
    end
    
    Thought --> Action[最终行动 (交易/回答)]
    Action --> Reflection[反思与学习]
    Reflection --> Memory
```

### 2. 模块详解

#### 2.1 感知模块 (Perception)
*   **多模态输入**: 接收用户的文本指令、实时的 K 线数据 (数值)、新闻标题 (文本)。
*   **预处理**: 将非结构化数据 (新闻) 转化为结构化摘要；将高频 Tick 数据聚合为 OHLCV K线。

#### 2.2 记忆模块 (Memory) - "Agent 的经验"
*   **短期记忆 (Short-term Memory)**:
    *   **上下文窗口**: 保存当前对话历史、当前市场状态（如最近 1 小时的趋势）。
*   **长期记忆 (Long-term Memory)**:
    *   **语义记忆 (Semantic Memory)**: 存储金融知识、交易规则、策略模板。通过向量数据库 (Vector DB) 检索。
    *   **情景记忆 (Episodic Memory)**: 存储过去的交易记录、成功/失败的案例。Agent 在做决策前，会检索“历史上类似的市场情况我们是怎么做的，结果如何”。

#### 2.3 规划模块 (Planning) - "决策中心"
*   **ReAct 模式 (Reason + Act)**:
    *   Agent 遵循 "思考 (Thought) -> 行动 (Action) -> 观察 (Observation)" 的模式。
    *   *示例*: "用户想买 BTC -> 思考: 我需要先看现在的价格和趋势 -> 行动: 调用 `get_price('BTC')` -> 观察: 价格是 65000，趋势向下 -> 思考: 趋势不好，我应该先等待或通过技术指标确认 -> 行动: 调用 `calculate_rsi('BTC')`..."
*   **自我反思 (Self-Reflection)**:
    *   在执行交易后，Agent 会生成一份“交易日志”，分析决策是否正确，并将其存入长期记忆，用于修正未来的行为。

#### 2.4 工具集 (Tools) - "Agent 的手和脚"
Agent 不直接操作数据库或交易所，而是通过**工具 (Tools)** 与外部世界交互。
*   **数据类工具**:
    *   `get_market_price(symbol)`: 获取当前价格。
    *   `get_historical_data(symbol, timeframe, limit)`: 获取历史 K 线。
    *   `get_news_sentiment(symbol)`: 获取新闻情绪评分。
*   **分析类工具**:
    *   `calculate_indicator(data, indicator_name, params)`: 计算技术指标 (RSI, MACD)。
    *   `run_backtest(strategy_code, data)`: 运行回测并返回绩效报告。
*   **交易类工具** (需权限控制):
    *   `place_order(symbol, side, type, amount)`: 下单。
    *   `get_account_balance()`: 查询余额。
    *   `close_position(symbol)`: 平仓。

### 3. Agent 工作流示例：编写并验证一个策略

1.  **用户指令**: "帮我写一个比特币的均线突破策略，如果回测效果好就实盘运行。"
2.  **感知**: 识别意图 -> 任务拆分 (编写策略 -> 回测 -> 评估 -> (可选) 实盘)。
3.  **规划 & 执行**:
    *   **Step 1 (编写)**: Agent 利用 LLM 的编码能力，生成一段 Python 策略代码 (继承自 BaseStrategy)，逻辑是 "价格上穿 MA20 买入"。
    *   **Step 2 (回测)**: Agent 调用 `run_backtest` 工具，传入生成的代码和 BTC 过去 1 个月的数据。
    *   **Step 3 (观察)**: 回测工具返回结果：夏普比率 0.5，最大回撤 20%。
    *   **Step 4 (反思)**: Agent 思考 "夏普比率太低，风险太高，不符合‘效果好’的标准"。
    *   **Step 5 (优化)**: Agent 修改代码，增加 "RSI < 70" 作为过滤条件，再次调用 `run_backtest`。
    *   **Step 6 (再次观察)**: 新结果：夏普比率 1.8，回撤 10%。
    *   **Step 7 (决策)**: Agent 判定合格，向用户报告："策略已优化，夏普比率提升至 1.8。是否启动模拟盘运行？"
4.  **行动**: 等待用户确认后，调用 `start_paper_trading(strategy_id)`。

---

## 项目结构映射 (Project Structure Mapping)

为了支撑上述架构，我们的代码库将如此组织：

```
kurisu/
├── backend/
│   ├── app/
│   │   ├── agents/           # Agent 核心逻辑
│   │   │   ├── core.py       # Agent 初始化与主循环 (LangGraph)
│   │   │   ├── tools/        # 工具定义 (Tools)
│   │   │   ├── memory/       # 向量数据库交互 (RAG)
│   │   │   └── prompts/      # Prompt 模板管理
│   │   ├── strategies/       # 量化策略基类与实现
│   │   ├── services/         # 业务服务 (数据, 交易)
│   │   └── api/              # FastAPI 路由
│   └── ...
├── frontend/                 # Next.js 前端
└── ...
```

通过这种架构，我们不仅是在构建一个交易机器人，更是在构建一个**能够自我进化、具备专业知识的数字量化专家**。
