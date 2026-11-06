FROM python:3.14-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.19 /uv /uvx /bin/
# The venv lives outside /code so docker-compose's source mount doesn't shadow it.
ENV UV_PROJECT_ENVIRONMENT=/venv UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never PATH="/venv/bin:$PATH"
WORKDIR /code
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen
COPY . .
ENV FLASK_APP=auth FLASK_ENV=development FLASK_DEBUG=1
CMD ["flask", "run", "-h", "0.0.0.0"]
