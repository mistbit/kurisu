# 项目路线图 (Project Roadmap)

本路线图描述了 Kurisu 的核心发展阶段。

## 第一阶段：基础设施 (Phase 1: Infrastructure) - ✅ 已完成
- 核心后端 FastAPI 框架
- 数据库 TimescaleDB 与 Redis 基础架构
- CCXT 市场数据接入
- WebSocket 实时数据推送
- 同步状态管理与自动回补

## 第二阶段：量化引擎 (Phase 2: Quant Engine) - 🔄 进行中
- ✅ 策略基类 BaseStrategy 定义
- ✅ 事件驱动的回测引擎
- ✅ 性能指标计算 (Sharpe, Sortino, 最大回撤)
- ✅ 示例策略 (MA 交叉, RSI 均值回归)
- ⏳ 技术指标计算库集成
- ⏳ 策略优化功能

## 第二.五阶段：安全与认证 (Phase 2.5: Security & Auth) - ✅ 已完成
- JWT Token 认证
- API Key 认证
- 用户管理服务
- Redis 滑动窗口限流
- 超级用户权限控制

## 第三阶段：AI Agent 深度集成 (Phase 3: AI Agent Integration) - 待开始
- LangGraph 状态流转控制
- Agent 工具集 (MarketDataTool, BacktestTool)
- RAG 记忆系统 (pgvector)

## 第四阶段：实盘交易与风控 (Phase 4: Live Trading & Risk Management) - 待开始
- 订单管理系统 (OMS)
- 风控逻辑与熔断机制
- 交易所实盘 API 接入
