FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt* pyproject.toml* ./
RUN pip install --no-cache-dir flask flask-socketio eventlet pillow

COPY . .

ENV PORT=8080
EXPOSE 8080

CMD ["python", "main.py"]
