# Kurisu - Deep Agent Architecture Design

This document details the core architecture design of the AI Agent in the **Kurisu** project, aiming to help developers understand the design philosophy and provide theoretical guidance for subsequent development.

---

## Deep Dive into Agent Architecture

Kurisu's Agent is not just a chatbot, but a **financial intelligent agent capable of autonomous decision-making**. We adopt the **Cognitive Architecture** design philosophy.

### 1. Core Cognitive Architecture (The Brain)
The Agent's brain consists of the following key modules:

```mermaid
graph TD
    User[User Instruction] --> Perception[Perception Module]
    Market[Market Data] --> Perception
    News[News Info] --> Perception
    
    Perception --> Memory[Memory Module (RAG)]
    Memory --> Planning[Planning Module (Planner)]
    
    subgraph "Reasoning Loop"
        Planning --> Thought[Reasoning/Thought]
        Thought --> ToolSelect[Tool Selection]
        ToolSelect --> Execution[Tool Execution]
        Execution --> Observation[Observation]
        Observation --> Thought
    end
    
    Thought --> Action[Final Action (Trade/Reply)]
    Action --> Reflection[Reflection & Learning]
    Reflection --> Memory
```

### 2. Module Details

#### 2.1 Perception Module
*   **Multi-modal Input**: Receives user text instructions, real-time candlestick data (numerical), news headlines (text).
*   **Preprocessing**: Converts unstructured data (news) into structured summaries; aggregates high-frequency Tick data into OHLCV candlesticks.

#### 2.2 Memory Module - "The Agent's Experience"
*   **Short-term Memory**:
    *   **Context Window**: Saves current conversation history, current market state (e.g., trend over the last hour).
*   **Long-term Memory**:
    *   **Semantic Memory**: Stores financial knowledge, trading rules, strategy templates. Retrieved via Vector DB.
    *   **Episodic Memory**: Stores past trade records, success/failure cases. Before making a decision, the Agent retrieves "how we handled similar market situations in the past and what the outcome was."

#### 2.3 Planning Module - "Decision Center"
*   **ReAct Pattern (Reason + Act)**:
    *   The Agent follows the "Thought -> Action -> Observation" pattern.
    *   *Example*: "User wants to buy BTC -> Thought: I need to check the current price and trend first -> Action: Call `get_price('BTC')` -> Observation: Price is 65000, trend is down -> Thought: Trend is bad, I should wait or confirm via technical indicators -> Action: Call `calculate_rsi('BTC')`..."
*   **Self-Reflection**:
    *   After executing a trade, the Agent generates a "trade journal," analyzing whether the decision was correct, and stores it in long-term memory to correct future behavior.

#### 2.4 Toolset - "The Agent's Hands and Feet"
The Agent does not directly operate the database or exchange but interacts with the outside world via **Tools**.
*   **Data Tools**:
    *   `get_market_price(symbol)`: Get current price.
    *   `get_historical_data(symbol, timeframe, limit)`: Get historical candlesticks.
    *   `get_news_sentiment(symbol)`: Get news sentiment score.
*   **Analysis Tools**:
    *   `calculate_indicator(data, indicator_name, params)`: Calculate technical indicators (RSI, MACD).
    *   `run_backtest(strategy_code, data)`: Run backtest and return performance report.
*   **Trading Tools** (Requires Permission Control):
    *   `place_order(symbol, side, type, amount)`: Place order.
    *   `get_account_balance()`: Query balance.
    *   `close_position(symbol)`: Close position.

### 3. Agent Workflow Example: Writing and Validating a Strategy

1.  **User Instruction**: "Help me write a Bitcoin moving average breakout strategy. If the backtest results are good, run it live."
2.  **Perception**: Identify intent -> Task Breakdown (Write Strategy -> Backtest -> Evaluate -> (Optional) Live Trade).
3.  **Planning & Execution**:
    *   **Step 1 (Write)**: Agent uses LLM coding capability to generate a Python strategy code snippet (inheriting from BaseStrategy), logic is "Buy when price crosses above MA20".
    *   **Step 2 (Backtest)**: Agent calls `run_backtest` tool, passing the generated code and BTC data from the last month.
    *   **Step 3 (Observe)**: Backtest tool returns results: Sharpe Ratio 0.5, Max Drawdown 20%.
    *   **Step 4 (Reflect)**: Agent thinks "Sharpe Ratio is too low, risk is too high, does not meet 'good results' criteria".
    *   **Step 5 (Optimize)**: Agent modifies code, adding "RSI < 70" as a filter condition, calls `run_backtest` again.
    *   **Step 6 (Observe Again)**: New results: Sharpe Ratio 1.8, Drawdown 10%.
    *   **Step 7 (Decision)**: Agent deems it qualified, reports to user: "Strategy optimized, Sharpe Ratio improved to 1.8. Start paper trading?"
4.  **Action**: After user confirmation, calls `start_paper_trading(strategy_id)`.

---

## Project Structure Mapping

To support the above architecture, our codebase will be organized as follows:

```
kurisu/
├── backend/
│   ├── app/
│   │   ├── agents/           # Agent Core Logic
│   │   │   ├── core.py       # Agent Init & Main Loop (LangGraph)
│   │   │   ├── tools/        # Tool Definitions
│   │   │   ├── memory/       # Vector DB Interaction (RAG)
│   │   │   └── prompts/      # Prompt Template Management
│   │   ├── strategies/       # Quant Strategy Base Classes & Implementations
│   │   ├── services/         # Business Services (Data, Trading)
│   │   └── api/              # FastAPI Routes
│   └── ...
├── frontend/                 # Next.js Frontend
└── ...
```

With this architecture, we are not just building a trading bot, but building a **digital quantitative expert capable of self-evolution and possessing professional knowledge**.
