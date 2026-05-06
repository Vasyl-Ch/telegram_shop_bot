# Multi-stage build для оптимизации размера образа
FROM python:3.11-slim as builder

# Устанавливаем системные зависимости для сборки
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Копируем только requirements.txt для кеширования слоя
WORKDIR /build
COPY requirements.txt .

# Устанавливаем зависимости в отдельную директорию
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Финальный образ
FROM python:3.11-slim

# Метаданные
LABEL maintainer="your-email@example.com"
LABEL description="Telegram Shop Bot with Stripe & Google Sheets integration"

# Устанавливаем runtime зависимости + curl для healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Создаем непривилегированного пользователя
RUN groupadd -r botuser && useradd -r -g botuser botuser

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем установленные зависимости из builder
COPY --from=builder /install /usr/local

# Копируем код приложения
COPY --chown=botuser:botuser . .

# Создаем директории для данных
RUN mkdir -p /app/data && chown -R botuser:botuser /app/data

# Expose порт для healthcheck (документационно)
EXPOSE 8080

# Переключаемся на непривилегированного пользователя
USER botuser

# Healthcheck - проверяет HTTP endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/ || exit 1

# Запуск приложения
CMD ["python", "-u", "main.py"]

#🚀 Запуск и тестирование
#1. Пересобрать контейнер:
#bashdocker-compose down
#docker-compose build --no-cache
#docker-compose up -d
#2. Проверить логи запуска:
#bashdocker-compose logs -f telegram-bot
#```
#
#Вы должны увидеть:
#```
#✅ Healthcheck server started on 0.0.0.0:8080