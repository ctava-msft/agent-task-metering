FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src/ ./src/

RUN pip install --no-cache-dir -e .

CMD ["python", "-c", "from agent_task_metering import TaskMeter; print('agent-task-metering ready')"]
