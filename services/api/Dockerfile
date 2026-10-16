# API and worker image. Run the API with the default command, the worker with
# `nexus-worker`, and migrations with `alembic upgrade head` (as the owner role).
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH="/app/.venv/bin:$PATH"

WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./
RUN uv sync --frozen --no-dev

RUN useradd --system --uid 10001 nexus && mkdir -p /data/storage && chown nexus /data/storage
USER nexus
ENV NEXUS_STORAGE_DIR=/data/storage
EXPOSE 8100
CMD ["uvicorn", "nexus.main:app", "--host", "0.0.0.0", "--port", "8100"]
