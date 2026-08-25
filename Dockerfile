# Small, fast base image
FROM python:3.11-slim

# Prevents Python from writing .pyc files and buffers stdout — cleaner logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first (layer caching — rebuilds are faster if
# requirements.txt hasn't changed but app code has)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app
COPY . .

# Where the SQLite database lives — mount a volume here in production
# so data survives rebuilds (see docker-compose.yml)
ENV DATA_DIR=/app/data
RUN mkdir -p /app/data

EXPOSE 5000

# gunicorn instead of Flask's dev server — handles real traffic properly.
# 2 workers is plenty for a school-sized suggestion box.
# init_db() runs once on container start — safe to call every time,
# it only creates tables/seeds the default account if they don't exist yet.
CMD ["sh", "-c", "python -c 'from app import init_db; init_db()' && gunicorn --bind 0.0.0.0:5463 --workers 2 app:app"]
