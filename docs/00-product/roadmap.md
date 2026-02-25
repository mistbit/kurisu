# 项目路线图 (Project Roadmap)

本路线图描述了 Kurisu 的核心发展阶段。

## 第一阶段：基础设施 (Phase 1: Infrastructure) - 当前阶段
- 核心后端 FastAPI 框架
- 数据库 TimescaleDB 与 Redis 基础架构
- CCXT 市场数据接入

## 第二阶段：量化引擎 (Phase 2: Quant Engine)
- 策略基类 BaseStrategy 定义
- 事件驱动的回测引擎
- 技术指标计算库集成

## 第三阶段：AI Agent 深度集成 (Phase 3: AI Agent Integration)
- LangGraph 状态流转控制
- Agent 工具集 (MarketDataTool, BacktestTool)
- RAG 记忆系统 (pgvector)

## 第四阶段：实盘交易与风控 (Phase 4: Live Trading & Risk Management)
- 订单管理系统 (OMS)
- 风控逻辑与熔断机制
- 交易所实盘 API 接入
