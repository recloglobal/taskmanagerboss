FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .
COPY alembic/ /app/alembic/
COPY alembic.ini .

CMD ["python", "main.py"]