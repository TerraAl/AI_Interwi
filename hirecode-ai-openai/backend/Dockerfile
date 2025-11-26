FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 🔥 копируем шрифты ПОСЛЕ COPY .
RUN cp /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf /app/DejaVuSans.ttf && \
    cp /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf /app/DejaVuSans-Bold.ttf

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
