# 任务列表 (Tasks)

- [x] 任务 1: 创建项目目录结构和基础文件
  - [x] 子任务 1.1: 创建目录: `app/api`, `app/core`, `app/models`, `app/services`, `tests`
  - [x] 子任务 1.2: 创建 `__init__.py` 文件
  - [x] 子任务 1.3: 创建 `requirements.txt` 并添加依赖: `fastapi`, `uvicorn`, `sqlalchemy`, `asyncpg`, `alembic`, `pydantic-settings`, `ccxt`, `redis`

- [x] 任务 2: 实现配置管理 (支持外部服务)
  - [x] 子任务 2.1: 创建 `.env.example` 模板，包含连接阿里云 PG 和 Redis 所需的变量 (HOST, PORT, USER, PASSWORD 等)
  - [x] 子任务 2.2: 使用 `pydantic-settings` 创建 `app/core/config.py` 以加载 `.env` 变量
  - [x] 子任务 2.3: 定义 `Settings` 类，构建完整的 Database URL 和 Redis URL

- [x] 任务 3: 实现数据库连接
  - [x] 子任务 3.1: 使用 `sqlalchemy.ext.asyncio` 创建 `app/core/database.py`，配置连接池以适应云数据库环境
  - [x] 子任务 3.2: 为 FastAPI 创建 `get_db` 依赖项

- [x] 任务 4: 实现 Redis 连接
  - [x] 子任务 4.1: 创建 `app/core/redis.py` (或在 `database.py` 中) 初始化 Redis 客户端连接池

- [x] 任务 5: 实现 CCXT 服务桩 (Stub)
  - [x] 子任务 5.1: 创建 `app/services/exchange.py` 以处理 CCXT 交易所初始化 (简单的工厂模式或单例模式)

- [x] 任务 6: 创建主应用程序入口点
  - [x] 子任务 6.1: 创建包含 FastAPI 应用实例的 `app/main.py`
  - [x] 子任务 6.2: 添加 `/health` 端点，检查并返回 DB 和 Redis 的连接状态
  - [x] 子任务 6.3: 添加数据库和 Redis 连接的启动/关闭事件处理 (Lifespan events)

# 任务依赖 (Task Dependencies)
- 任务 2 依赖于 任务 1
- 任务 3 依赖于 任务 2
- 任务 4 依赖于 任务 2
- 任务 6 依赖于 任务 3, 任务 4, 任务 5
