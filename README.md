# agent-task-metering

> Track and meter AI agent task usage and token consumption.

[![CI](https://github.com/ctava-msft/agent-task-metering/actions/workflows/ci.yml/badge.svg)](https://github.com/ctava-msft/agent-task-metering/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Overview

`agent-task-metering` is a lightweight Python library for recording, aggregating, and
summarizing token and task-level usage metrics produced by AI agents.

## Repository Layout

```
.
├── src/agent_task_metering/   # Library source
├── tests/                     # Unit tests (pytest)
├── infra/                     # Dockerfile and infrastructure files
├── docs/                      # Documentation
├── examples/                  # Usage examples
├── .devcontainer/             # VS Code Dev Container config
├── .github/workflows/         # GitHub Actions CI
├── Makefile                   # Developer shortcuts
└── pyproject.toml             # Project metadata and tool config
```

## Quick Start

### Requirements

- Python 3.9+
- Docker (optional, for container build)

### Install

```bash
pip install -e ".[dev]"
```

### Run tests

```bash
make test
```

### Lint

```bash
make lint
```

### Build container image

```bash
make build
```

## Dev Container

Open this repository in VS Code and choose **Reopen in Container** to get a
fully configured Python development environment.

## Example

```python
from agent_task_metering import TaskMeter

meter = TaskMeter()
meter.record("task-001", "my-agent", "chat", input_tokens=512, output_tokens=128)
print(meter.summary())
```

See [`examples/basic_usage.py`](examples/basic_usage.py) for more.

## Contributing

This project welcomes contributions and suggestions. Please see
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) and [SUPPORT.md](SUPPORT.md).

## Security

Please see [SECURITY.md](SECURITY.md) for reporting vulnerabilities.

## License

[MIT](LICENSE) © Microsoft Corporation
