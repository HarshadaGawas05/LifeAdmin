FROM python:3.11-slim

WORKDIR /app

# Use prebuilt wheels; avoid apt to prevent DNS/mirror issues
RUN pip install --no-cache-dir --upgrade pip

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

