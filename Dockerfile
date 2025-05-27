FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy all project files
COPY . .

# Install dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Jalankan via Gunicorn
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8001", "app:app"]
