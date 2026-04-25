FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 雖然 server.py 內建檢查並安裝 playwright，但建議在 Docker 內直接裝好以節省每次啟動時間
RUN playwright install chromium

COPY . .

CMD ["python", "server.py"]
