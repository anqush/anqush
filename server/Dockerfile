FROM python:3.11-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.5.29 /uv /uvx /bin/

# Install dependencies first (cache layer)
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev 2>/dev/null || uv sync --no-dev

ENV PATH="/app/.venv/bin:$PATH"

# Copy app code
COPY server/ ./server/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
