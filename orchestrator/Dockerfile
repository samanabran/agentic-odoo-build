FROM python:3.11-slim

WORKDIR /orchestrator

# Install dependencies before copying source so this layer is cached
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

# In development the source is mounted as a volume (see docker-compose.yml),
# so this COPY is primarily for standalone / CI builds.
COPY app/ ./app/
COPY tests/ ./tests/

EXPOSE 8088

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8088", "--reload"]
