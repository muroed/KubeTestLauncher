# Базовый образ Python
FROM python:3.11-slim

# Рабочая директория в контейнере
WORKDIR /app

# Переменные окружения
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Копирование и установка зависимостей
COPY dependencies.txt .
RUN pip install --no-cache-dir -r dependencies.txt

# Копирование файлов проекта
COPY . .

# Порт, который будет прослушивать приложение
EXPOSE 5000

# Запуск приложения через Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--reuse-port", "--access-logfile", "-", "main:app"]
