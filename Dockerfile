FROM --platform=linux/x86_64 python:3.10-alpine

# Устанавливаем необходимые пакеты, включая bash, gcc, libffi и build-base для компиляции
RUN apk update && apk add --no-cache gcc libffi-dev bash cmake build-base

# Отключаем создание .pyc файлов и буферизацию вывода
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Копируем и устанавливаем зависимости
COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

# Устанавливаем рабочую директорию и копируем проект
WORKDIR /app
COPY . /app

# Создаем пользователя для безопасности и изменяем права
RUN adduser -u 5678 -D appuser && chown -R appuser /app
USER appuser

# Запуск приложения
CMD ["python", "main.py"]
