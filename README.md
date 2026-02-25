# Kurisu

<div align="center">

<img src="kurisu.png" alt="Kurisu Logo" width="200" />

**An AI-Native Quantitative Trading Agent & Research Platform**

[![Status](https://img.shields.io/badge/Status-Work%20in%20Progress-yellow)]()
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10+-green.svg)]()
[![TypeScript](https://img.shields.io/badge/TypeScript-5.0+-blue.svg)]()

[Features](#features) • [Architecture](#architecture) • [Getting Started](#getting-started) • [Documentation](#documentation) • [Roadmap](#roadmap) • [Contributing](#contributing)

[中文 README](README_zh.md)

</div>

---

## 🚀 Vision

**Kurisu** is an open-source project designed to bridge the gap between **Quantitative Finance** and **Modern AI Agents**. It serves as:
1.  A **Trading Bot**: Capable of automating strategies with risk management.
2.  A **Research Lab**: For experimenting with LLM-based agents (ReAct, Plan-and-Solve) in financial markets.
3.  A **Learning Platform**: Helping developers and traders understand the math and code behind strategies.

> **Note:** This project is currently in the initial design and development phase. The codebase is being actively developed.

## ✨ Key Features

- **🧠 Cognitive AI Agent**: Built on **LangGraph**, the agent can plan, use tools, and "think" before trading. It explains *why* it made a decision.
- **📊 Modular Strategy Engine**: Write strategies in Python or let the AI generate them. Supports event-driven backtesting.
- **📈 Modern Dashboard**: A beautiful, responsive UI built with **Next.js** and **ShadcnUI** for real-time monitoring and backtest visualization.
- **⚡ High Performance**: Powered by **FastAPI** (Async Python) and **TimescaleDB** for efficient time-series data handling.
- **🛡️ Risk Management**: Built-in paper trading mode, hard stops, and position limits.

## 🏗️ Architecture

Kurisu follows a **Microservices-ready Monolith** architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (Next.js)                      │
│  Dashboard │ Agent Chat │ Backtest Lab │ Strategy Editor    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Backend (FastAPI)                         │
├─────────────────────────────────────────────────────────────┤
│  API Gateway │ Auth │ WebSocket Server                       │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ Quant Engine│  │ AI Agent    │  │ Execution Service   │  │
│  │ - Strategies│  │ - LangGraph │  │ - Paper Trading     │  │
│  │ - Backtest  │  │ - Memory    │  │ - Live Trading      │  │
│  │ - Indicators│  │ - Tools     │  │ - Risk Management   │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Data Layer                                │
│  PostgreSQL + TimescaleDB │ Redis │ Vector DB (pgvector)    │
└─────────────────────────────────────────────────────────────┘
```

### Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Frontend** | Next.js, TypeScript, Tailwind CSS, ShadcnUI | Modern responsive UI |
| **Backend** | FastAPI (Python 3.10+), Celery | Async API & task processing |
| **AI Framework** | LangChain, LangGraph | Agent orchestration |
| **Database** | PostgreSQL + TimescaleDB | Time-series market data |
| **Vector Store** | pgvector / ChromaDB | AI memory (RAG) |
| **Cache** | Redis | Real-time data & task queue |
| **Exchange API** | CCXT | Multi-exchange support |

See [Architecture Design](docs/02-architecture/overview.md) for details.

## 📚 Documentation

- [Requirements Document](docs/00-product/requirements.md) - Project goals and feature specifications
- [Architecture Design](docs/02-architecture/overview.md) - System architecture and module design
- [Tech Stack Rationale](docs/04-technical-spec/tech-stack.md) - Technology choices and rationale
- [Agent Architecture](docs/02-architecture/agent-logic.md) - Deep dive into AI agent design

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- Docker & Docker Compose
- Poetry (Python package manager)
- Bun or npm (JavaScript package manager)

### Quick Start

```bash
# Clone the repository
git clone https://github.com/yourusername/kurisu.git
cd kurisu

# Start infrastructure services (PostgreSQL, TimescaleDB, Redis)
docker-compose up -d

# Backend setup
cd backend
poetry install
poetry run python -m app.main

# Frontend setup (in a new terminal)
cd frontend
npm install
npm run dev
```

### Environment Variables

Create a `.env` file in the backend directory:

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/kurisu

# Redis
REDIS_URL=redis://localhost:6379

# LLM API Keys (choose one or more)
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key

# Exchange API Keys (for live trading)
BINANCE_API_KEY=your_binance_key
BINANCE_API_SECRET=your_binance_secret
```

### Development Mode

```bash
# Run backend in development mode with hot reload
cd backend
poetry run uvicorn app.main:app --reload

# Run frontend in development mode
cd frontend
npm run dev

# Run tests
cd backend
poetry run pytest

cd frontend
npm run test
```

## 🗺️ Roadmap

### Phase 1: Foundation (Current)
- [ ] Project structure setup
- [ ] Database schema design
- [ ] Basic data ingestion (CCXT integration)
- [ ] Simple backtesting engine
- [ ] Basic UI dashboard

### Phase 2: AI Integration
- [ ] LLM integration (OpenAI/Anthropic/Ollama)
- [ ] Agent chat interface
- [ ] Market sentiment analysis
- [ ] Strategy code generation

### Phase 3: Live Execution
- [ ] Paper trading system
- [ ] Exchange API integration
- [ ] Risk management module
- [ ] Real-time monitoring

### Phase 4: Advanced Agent
- [ ] Long-term memory (RAG)
- [ ] Multi-agent collaboration
- [ ] Autonomous strategy optimization
- [ ] Self-reflection and learning

## 🤝 Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for details.

### Development Guidelines

- Follow the code style guidelines (Black for Python, Prettier for TypeScript)
- Write meaningful commit messages following [Conventional Commits](https://www.conventionalcommits.org/)
- Add tests for new features
- Update documentation for API changes

## 📁 Project Structure

> **Note:** The project is currently in the design phase. The following structure will be implemented during development.

```
kurisu/
├── frontend/                 # Next.js Application
│   ├── app/                  # App router pages
│   ├── components/           # React components
│   ├── lib/                  # Utilities and hooks
│   └── public/               # Static assets
├── backend/                  # FastAPI Application
│   ├── app/
│   │   ├── api/              # API Routes (v1)
│   │   ├── core/             # Config, Security, DB Connections
│   │   ├── services/         # Business Logic (MarketData, TradeExec)
│   │   ├── agents/           # AI Agent Logic (Prompts, Tools, Memory)
│   │   ├── strategies/       # Strategy Implementations
│   │   └── models/           # Pydantic & SQL Models
│   └── tests/
├── docs/                     # Documentation
├── docker-compose.yml        # Container orchestration
└── README.md
```

## ⚠️ Disclaimer

**This software is for educational and research purposes only.** Do not use it for live trading unless you fully understand the risks. The authors are not responsible for any financial losses incurred.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<div align="center">

**[⬆ Back to Top](#kurisu)**

Made with ❤️ by the Kurisu Team

</div>
