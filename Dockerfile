# Gunakan image python resmi
FROM python:3.10-slim

# Buat direktori kerja di dalam container
WORKDIR /app

# Copy semua file ke dalam container
COPY . .

# Install dependency
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Expose port Flask
EXPOSE 5000

# Jalankan aplikasi
CMD ["python", "app.py"]
