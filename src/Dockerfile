FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src/ ./src/

RUN pip install --no-cache-dir -e .

EXPOSE 8080

CMD ["python", "-m", "agent_task_metering.evaluation.api", "--port", "8080"]
