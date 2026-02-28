import os
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import google.generativeai as genai

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

class AskRequest(BaseModel):
    video_url: str
    topic: str

@app.post("/ask")
async def ask(request: AskRequest):
    try:
        model = genai.GenerativeModel("gemini-1.5-pro")

        prompt = f"""Watch this YouTube video and find the exact timestamp when the topic "{request.topic}" is first spoken or discussed.
Return ONLY a JSON with the timestamp in HH:MM:SS format."""

        response = model.generate_content(
            [
                {"text": prompt},
                {"file_data": {"mime_type": "video/mp4", "file_uri": request.video_url}}
            ],
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema={
                    "type": "object",
                    "properties": {
                        "timestamp": {
                            "type": "string",
                            "description": "Timestamp in HH:MM:SS format"
                        }
                    },
                    "required": ["timestamp"]
                }
            )
        )

        result = json.loads(response.text)
        timestamp = result["timestamp"]

        parts = timestamp.split(":")
        if len(parts) == 2:
            timestamp = "00:" + timestamp

        return {
            "timestamp": timestamp,
            "video_url": request.video_url,
            "topic": request.topic
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
