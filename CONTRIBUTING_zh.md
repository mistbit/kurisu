# 贡献指南

首先，感谢你考虑为 Kurisu 做贡献！正是因为有你这样的人，Kurisu 才能成为一个优秀的工具。

## 📜 行为准则

本项目及其所有参与者均受我们的行为准则约束。通过参与本项目，你应当遵守该准则。如发现不当行为，请向项目维护者报告。

## 🤔 如何贡献？

### 报告 Bug

在创建 Bug 报告之前，请先检查 issue 列表，你可能发现不需要创建新的。创建 Bug 报告时，请尽可能包含详细信息：

* **使用清晰、描述性的标题**
* **描述重现问题的确切步骤**
* **提供具体示例来演示步骤**
* **描述执行步骤后观察到的行为**
* **解释你期望看到的行为以及原因**
* **如果可能，附上截图和动态 GIF**
* **包含你的环境详情**（操作系统、Python 版本、Node.js 版本等）

### 建议功能增强

功能增强建议通过 GitHub issues 追踪。创建建议时，请包含：

* **使用清晰、描述性的标题**
* **提供逐步描述的建议增强功能**
* **提供具体示例来演示步骤**
* **描述当前行为并解释你期望的行为**
* **解释为什么这个增强功能会有用**

### 提交 Pull Request

* 填写所需的模板
* 不要在 PR 标题中包含 issue 编号
* 尽可能附上截图和动态 GIF
* 遵循代码风格指南
* 根据文档风格指南为新代码编写文档
* 所有文件以换行符结尾

## 🛠️ 开发环境设置

### 前置要求

* Python 3.10+
* Node.js 18+
* Bun 或 npm（JavaScript 包管理器）

### 设置开发环境

```bash
# 克隆仓库
git clone https://github.com/yourusername/kurisu.git
cd kurisu

# 后端设置
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 前端设置
cd ../frontend
npm install

# 配置环境变量
cd ../backend
cp .env.example .env
${EDITOR:-nano} .env
```

### 运行测试

```bash
# 后端测试
cd backend
source venv/bin/activate
pytest

# 前端测试
cd ../frontend
npm run test
```

### 代码风格

#### Python

* 遵循 [PEP 8](https://peps.python.org/pep-0008/) 风格指南
* 使用 [Black](https://github.com/psf/black) 进行代码格式化
* 使用 [isort](https://pycqa.github.io/isort/) 进行导入排序
* 使用 [Ruff](https://github.com/astral-sh/ruff) 进行代码检查

```bash
# 格式化代码 (在 backend 目录下)
cd backend
source venv/bin/activate
black .
isort .

# 代码检查 (在 backend 目录下)
ruff check .
```

#### TypeScript/JavaScript

* 遵循 [Airbnb JavaScript 风格指南](https://github.com/airbnb/javascript)
* 使用 [ESLint](https://eslint.org/) 进行代码检查
* 使用 [Prettier](https://prettier.io/) 进行代码格式化

```bash
# 格式化代码
npm run format

# 代码检查
npm run lint
```

## 📝 提交信息

我们遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范：

* **feat**: 新功能
* **fix**: Bug 修复
* **docs**: 仅文档更改
* **style**: 不影响代码含义的更改
* **refactor**: 既不修复 Bug 也不添加功能的代码更改
* **perf**: 提高性能的代码更改
* **test**: 添加缺失的测试或修正现有测试
* **chore**: 构建过程或辅助工具的更改

示例：
```
feat(agent): 添加长期存储的记忆模块

- 实现向量数据库集成
- 添加语义记忆检索
- 更新 Agent 核心以使用记忆模块
```

## 🏗️ 项目结构

```
kurisu/
├── frontend/             # Next.js 应用程序
├── backend/              # FastAPI 应用程序
│   ├── app/
│   │   ├── api/          # API 路由 (v1)
│   │   ├── core/         # 配置、安全、数据库连接
│   │   ├── services/     # 业务逻辑
│   │   ├── agents/       # AI Agent 逻辑
│   │   ├── strategies/   # 策略实现
│   │   └── models/       # Pydantic & SQL 模型
│   └── tests/
├── docs/                 # 文档
└── docker-compose.yml    # 容器编排
```

## 🔒 安全

### API 密钥和机密

* **永远不要将 API 密钥、密码或机密提交到仓库**
* 使用环境变量存储敏感配置
* 本地使用 `.env` 文件（这些文件已被 gitignore）
* 生产环境使用安全的密钥管理系统

### 报告安全漏洞

如果你发现安全漏洞，请**不要**公开 issue。请直接通过邮件联系维护者。

## 📚 文档

* 如果更改功能，请更新 README.md
* 架构变更请更新 docs/ 文件夹
* 为复杂逻辑添加内联注释
* 端点变更请更新 API 文档

## ❓ 有问题？

随时可以打开带有 `question` 标签的 issue，或直接联系维护者。

---

感谢你的贡献！🎉
