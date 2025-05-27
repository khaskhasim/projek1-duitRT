FROM python:3.11-slim

WORKDIR /app

COPY . /app

RUN pip install --upgrade pip && \
    pip install -r requirements.txt

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "app:app"]
