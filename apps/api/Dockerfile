FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

COPY pyproject.toml ./
RUN uv sync --no-dev

COPY app ./app

EXPOSE 8000
CMD ["sh", "-c", "uv run python -m app.migrations && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000"]
