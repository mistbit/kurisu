# Contributing to Kurisu

First off, thank you for considering contributing to Kurisu! It's people like you that make Kurisu such a great tool.

## 📜 Code of Conduct

This project and everyone participating in it is governed by our Code of Conduct. By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

## 🤔 How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check the issue list as you might find out that you don't need to create one. When you are creating a bug report, please include as many details as possible:

* **Use a clear and descriptive title**
* **Describe the exact steps to reproduce the problem**
* **Provide specific examples to demonstrate the steps**
* **Describe the behavior you observed after following the steps**
* **Explain which behavior you expected to see instead and why**
* **Include screenshots and animated GIFs if possible**
* **Include your environment details** (OS, Python version, Node.js version, etc.)

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues. When creating an enhancement suggestion, include:

* **Use a clear and descriptive title**
* **Provide a step-by-step description of the suggested enhancement**
* **Provide specific examples to demonstrate the steps**
* **Describe the current behavior and explain the behavior you expected**
* **Explain why this enhancement would be useful**

### Pull Requests

* Fill in the required template
* Do not include issue numbers in the PR title
* Include screenshots and animated GIFs in your pull request whenever possible
* Follow the code style guidelines
* Document new code based on the Documentation Style Guide
* End all files with a newline

## 🛠️ Development Setup

### Prerequisites

* Python 3.10+
* Node.js 18+
* Bun or npm (JavaScript package manager)

### Setting Up the Development Environment

```bash
# Clone the repository
git clone https://github.com/yourusername/kurisu.git
cd kurisu

# Backend setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Frontend setup
cd ../frontend
npm install

# Configure environment
cp .env.example .env
${EDITOR:-nano} .env
```

### Running Tests

```bash
# Backend tests
pytest

# Frontend tests
cd frontend
npm run test
```

### Code Style

#### Python

* Follow [PEP 8](https://peps.python.org/pep-0008/) style guide
* Use [Black](https://github.com/psf/black) for code formatting
* Use [isort](https://pycqa.github.io/isort/) for import sorting
* Use [Ruff](https://github.com/astral-sh/ruff) for linting

```bash
# Format code
black .
isort .

# Lint code
ruff check .
```

#### TypeScript/JavaScript

* Follow the [Airbnb JavaScript Style Guide](https://github.com/airbnb/javascript)
* Use [ESLint](https://eslint.org/) for linting
* Use [Prettier](https://prettier.io/) for code formatting

```bash
# Format code
npm run format

# Lint code
npm run lint
```

## 📝 Commit Messages

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

* **feat**: A new feature
* **fix**: A bug fix
* **docs**: Documentation only changes
* **style**: Changes that do not affect the meaning of the code
* **refactor**: A code change that neither fixes a bug nor adds a feature
* **perf**: A code change that improves performance
* **test**: Adding missing tests or correcting existing tests
* **chore**: Changes to the build process or auxiliary tools

Example:
```
feat(agent): add memory module for long-term storage

- Implement vector database integration
- Add semantic memory retrieval
- Update agent core to use memory module
```

## 🏗️ Project Structure

```
kurisu/
├── frontend/             # Next.js Application
├── backend/              # FastAPI Application
│   ├── app/
│   │   ├── api/          # API Routes (v1)
│   │   ├── core/         # Config, Security, DB Connections
│   │   ├── services/     # Business Logic
│   │   ├── agents/       # AI Agent Logic
│   │   ├── strategies/   # Strategy Implementations
│   │   └── models/       # Pydantic & SQL Models
│   └── tests/
├── docs/                 # Documentation
└── docker-compose.yml    # Orchestration
```

## 🔒 Security

### API Keys and Secrets

* **Never commit API keys, passwords, or secrets to the repository**
* Use environment variables for sensitive configuration
* Use `.env` files locally (these are gitignored)
* For production, use secure secret management systems

### Reporting Security Vulnerabilities

If you discover a security vulnerability, please do NOT open an issue. Email the maintainers directly instead.

## 📚 Documentation

* Update the README.md if you change functionality
* Update the docs/ folder for architectural changes
* Add inline comments for complex logic
* Update API documentation for endpoint changes

## ❓ Questions?

Feel free to open an issue with the `question` label, or reach out to the maintainers directly.

---

Thank you for your contributions! 🎉
