FROM python:3.13-slim

# tzdata нужен для ZoneInfo(Europe/Moscow) и корректного CronTrigger в контейнере
RUN apt-get update && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

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