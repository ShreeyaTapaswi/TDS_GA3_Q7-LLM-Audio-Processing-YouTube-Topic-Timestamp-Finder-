FROM python:3.11-slim

RUN apt-get update && apt-get install -y curl unzip ffmpeg && \
    curl -fsSL https://deno.land/install.sh | sh && \
    ln -s /root/.deno/bin/deno /usr/local/bin/deno

RUN pip install fastapi uvicorn google-generativeai yt-dlp

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
