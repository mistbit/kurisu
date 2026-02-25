# 任务列表 (Tasks)

- [ ] 任务 1: 创建项目目录结构和基础文件
  - [ ] 子任务 1.1: 创建目录: `app/api`, `app/core`, `app/models`, `app/services`, `tests`
  - [ ] 子任务 1.2: 创建 `__init__.py` 文件
  - [ ] 子任务 1.3: 创建 `requirements.txt` 并添加依赖: `fastapi`, `uvicorn`, `sqlalchemy`, `asyncpg`, `alembic`, `pydantic-settings`, `ccxt`, `redis`

- [ ] 任务 2: 使用 Docker Compose 搭建数据库基础设施
  - [ ] 子任务 2.1: 创建 `docker-compose.yml`，包含 `timescale/timescaledb:latest-pg18` 和 `redis:latest`
  - [ ] 子任务 2.2: 在 `.env.example` 中配置数据库凭据的环境变量

- [ ] 任务 3: 实现配置管理
  - [ ] 子任务 3.1: 使用 `pydantic-settings` 创建 `app/core/config.py` 以加载 `.env` 变量
  - [ ] 子任务 3.2: 定义 `Settings` 类，包含数据库 URL、Redis URL 和其他配置

- [ ] 任务 4: 实现数据库连接
  - [ ] 子任务 4.1: 使用 `sqlalchemy.ext.asyncio` 创建 `app/core/database.py`
  - [ ] 子任务 4.2: 为 FastAPI 创建 `get_db` 依赖项

- [ ] 任务 5: 实现 CCXT 服务桩 (Stub)
  - [ ] 子任务 5.1: 创建 `app/services/exchange.py` 以处理 CCXT 交易所初始化 (简单的工厂模式或单例模式)

- [ ] 任务 6: 创建主应用程序入口点
  - [ ] 子任务 6.1: 创建包含 FastAPI 应用实例的 `app/main.py`
  - [ ] 子任务 6.2: 添加 `/health` 端点
  - [ ] 子任务 6.3: 添加数据库连接的启动/关闭事件

# 任务依赖 (Task Dependencies)
- 任务 3 依赖于 任务 1
- 任务 4 依赖于 任务 3 和 任务 2
- 任务 6 依赖于 任务 4 和 任务 5
