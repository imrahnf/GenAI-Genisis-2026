FROM python:3.11-slim

WORKDIR /app
RUN mkdir -p /data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .

EXPOSE 8501
CMD ["python", "app.py"]
