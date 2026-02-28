import os
import json
import re
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from youtube_transcript_api import YouTubeTranscriptApi
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

def extract_video_id(url: str) -> str:
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11})',
        r'youtu\.be\/([0-9A-Za-z_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError("Could not extract video ID")

def seconds_to_hhmmss(seconds: float) -> str:
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"

@app.post("/ask")
async def ask(request: AskRequest):
    try:
        video_id = extract_video_id(request.video_url)

        # New API usage
        ytt = YouTubeTranscriptApi()
        transcript_obj = ytt.fetch(video_id)
        transcript = [{"start": s.start, "text": s.text} for s in transcript_obj]

        # Format transcript with timestamps
        transcript_text = ""
        for entry in transcript:
            ts = seconds_to_hhmmss(entry['start'])
            transcript_text += f"[{ts}] {entry['text']}\n"

        # Ask Gemini to find the timestamp
        model = genai.GenerativeModel("gemini-2.0-flash")

        prompt = f"""Here is a transcript of a YouTube video with timestamps:

{transcript_text}

Find the timestamp when the topic "{request.topic}" is first spoken or discussed.
Return ONLY the timestamp in HH:MM:SS format (e.g. 00:05:47)."""

        response = model.generate_content(
            prompt,
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
