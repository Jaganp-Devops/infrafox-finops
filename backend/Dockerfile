FROM python:3.11-slim

WORKDIR /app

# Install dependencies first, separately from app code, so Docker's layer
# cache avoids reinstalling every dependency on every code change.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# Non-root user - containers should never run as root by default.
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
