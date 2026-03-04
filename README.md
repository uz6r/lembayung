# Lembayung 🌅 - Protocol Analysis & Asynchronous Event Engine

![CI](https://github.com/uz6r/lembayung/actions/workflows/ci.yml/badge.svg)

Lembayung is a **technical demonstration** and **educational project** designed to explore the boundaries of asynchronous I/O, state-snapshot persistence, and public API protocol analysis. It exists primarily to study how modern web systems implement rate-limiting, Proof-of-Work (Altcha) challenges, and automated bot defenses.

> [!CAUTION]
> **LEGAL & ETHICAL NOTICE**: This repository is for **research and educational purposes only**. Using this tool to automate requests against third-party platforms may violate their Terms of Service (TOS). The authors do not condone the use of this software for scalping, commercial gain, or any activity that disrupts services. Users are responsible for ensuring their actions comply with local laws and the TOS of the target platforms.

> [!IMPORTANT]
> **RESEARCH OBJECTIVE**: This codebase maps the behavior of modern anti-automation strategies. It is architected to be "polite" by strictly respecting server-side status codes (like 428 and 429) and implementing human-like randomized delays to avoid service degradation.

## Engineering Implementation Details
- **High-Concurrency I/O**: Multi-cycle asynchronous execution using `asyncio` and `httpx`, optimized for low-latency request disparch and non-blocking notification handling.
- **Relational State Consistency**: Utilizes `aiosqlite` for persistent storage of availability snapshots, implementing an efficient set-difference logic to ensure exactly-once alerting.
- **Resilience Design**: Integrated `tenacity` for sophisticated retry-on-failure strategies, including exponential backoff and jitter to mitigate rate-limiting.
- **Schema-First Configuration**: Strict type-safe environment management using `Pydantic V2` and `pydantic-settings`, facilitating robust CI/CD integration and secret management.
- **Reverse-Engineering**: End-to-end mapping of proprietary widget protocols, including header spoofing, session management, and status-code handling.

- **Configuration-Only**: Does not run "out of the box." Requires explicit user setup via `.env` to prevent accidental or unauthorized use.

- **Asynchronous & Fast:** Uses Python `asyncio` and `httpx` to frequently poll the provider's widget API without blocking.
- **Deduplication:** Utilizes `aiosqlite` to store state snapshots. You only get alerted when a *new* slot appears, not continuously for the same open slot.
- **Robust Retries:** Implements exponential backoff via `tenacity` to handle rate limits and temporary networking errors gracefully.
- **Config-Driven:** Powered by `pydantic-settings`; entirely controllable via Environment Variables (`.env`).
- **Flexible Notifications:** Connects directly to Telegram bots or Slack Workspaces via webhooks.

## Architecture

The bot bypasses heavy frontends and UI bot-protections by relying directly on the backend endpoints that only require a valid `x-api-key`. Verification challenges (e.g. PoW) are only handled at execution, making monitoring pure and lightweight.

## Setup & Running Locally

### 1. Prerequisites
- Python 3.11+
- Virtualenv or Conda
- Docker (optional)

### 2. Installation
```bash
# Clone the repository and enter the directory
cd lembayung

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies (or install current package)
pip install -r requirements.txt
pip install -e .
```

### 3. Configuration
Create a `.env` file in the root directory.

```dotenv
# .env examples
TARGET_ID=1234  # Adjust to the actual target ID
TARGET_SLUG=target-resource
PROVIDER_API_KEY=your-api-key-here

# Rules
POLL_INTERVAL_SECONDS=60
FETCH_DAYS_AHEAD=30
MIN_PAX=2
MAX_PAX=8

# Notifications (Optional)
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

### 4. Running the Bot
You can run the worker loop using the configured CLI entry point:

```bash
# Recommended (installed via pip -e)
lembayung

# Or via the module
PYTHONPATH=src python3 -m lembayung.cli
```

### 5. Running the Telegram Bot
The Telegram bot is best run as a separate process:

```bash
# Recommended (installed via pip -e)
lembayung-bot

# Or via the module
PYTHONPATH=src python3 -m lembayung.bot
```

### 6. Local Development and CI
To keep code quality high before pushing upstream, you can use the provided Docker-based scripts to run `ruff`, `mypy`, and `pytest` locally without needing to install anything on your host machine:

```bash
# To check for linting errors and auto-fix them:
./scripts/lint.sh

# To format the codebase:
./scripts/format.sh

# To run static type checking (mypy):
./scripts/typecheck.sh

# To run tests (pytest):
./scripts/test.sh
```

These scripts will build a lightweight development container using `uv` for fast dependency resolution and run the tools against your local files.

## Docker Deployment (Recommended)

For production or persistent monitoring, it is highly recommended to use the provided Docker Compose stack which runs both the monitor and the bot as managed services.

```bash
# Start the entire stack (monitor + bot)
./scripts/docker-up.sh

# Stop the stack
./scripts/docker-down.sh
```

The stack uses `.env.local` for secrets and maps a local `data/` directory for persistent SQLite storage.

---

## Telegram Bot Integration

Lembayung includes a built-in interactive Telegram bot that provides real-time alerts and on-demand booking tools.

### 1. Configuration
Ensure your `.env` or `.env.local` file contains your Telegram credentials:
```dotenv
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
```

### 2. Available Commands
| Command | Description |
|---------|-------------|
| `/start` | Welcome message and command overview |
| `/status` | Shows current monitoring configuration |
| `/check` | Runs an immediate availability check (ad-hoc) |
| `/book` | Interactive flow: pick date → pick pax → see times → booking link |

### 3. Running via Docker
If using Docker, the `docker-compose.yml` is already configured to run both the monitor and the bot as separate services.
```bash
./scripts/docker-up.sh
```
---

## Legal & Ethical Usage Guide

When running this research engine, users must adhere to the following principles of **Responsible Automation**:

1.  **Respect Status Codes**: The engine is designed to stop immediately upon receiving a `428` or `429` error. Never attempt to "force" requests through a rate-limit.
2.  **Avoid Service Degradation**: Use the "Lean Stealth" settings to ensure your polling frequency does not impact the performance of the target platform's infrastructure.
3.  **Non-Commercial Only**: This tool is an academic exercise. Using it for commercial operations or to gain an unfair advantage in booking systems (scalping) is strictly discouraged.
4.  **Open Source Education**: The reverse-engineering documented here is intended to help developers understand how modern REST APIs and anti-bot systems (like Altcha) interact.

**Disclaimer**: *Lembayung is provided "as is" without warranty of any kind. The authors assume no liability for any misuse of the information or software provided.*
