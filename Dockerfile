FROM mcr.microsoft.com/playwright/python:v1.62.0-jammy
RUN apt-get update && apt-get install -y --no-install-recommends fonts-noto-cjk && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
# playwright 버전은 베이스 이미지에 내장된 브라우저와 일치해야 함
RUN pip install --no-cache-dir -r requirements.txt "playwright==1.62.0"
COPY . .
ENTRYPOINT ["python", "-m", "agent"]
CMD ["--help"]
