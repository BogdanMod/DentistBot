FROM python:3.13-slim

# Устанавливаем uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Копируем зависимости
COPY pyproject.toml uv.lock ./

# Устанавливаем зависимости
RUN uv sync --frozen --no-dev

# Копируем код
COPY src/ ./src/

# Запуск
CMD ["uv", "run", "python", "-m", "src.bot.main"]