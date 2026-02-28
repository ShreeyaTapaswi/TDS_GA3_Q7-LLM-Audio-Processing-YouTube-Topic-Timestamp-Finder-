FROM python:3.11-slim

RUN pip install fastapi uvicorn google-generativeai

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
