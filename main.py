import os
import time
import tempfile
import subprocess
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
    tmp_path = None
    uploaded_file = None
    
    try:
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
            tmp_path = tmp.name

        subprocess.run([
            "yt-dlp",
            "-f", "bestaudio",
            "--no-playlist",
            "--remote-components", "ejs:github",
            "-o", tmp_path,
            request.video_url
        ], check=True, capture_output=True)

        uploaded_file = genai.upload_file(tmp_path, mime_type="audio/webm")

        while uploaded_file.state.name == "PROCESSING":
            time.sleep(2)
            uploaded_file = genai.get_file(uploaded_file.name)

        if uploaded_file.state.name != "ACTIVE":
            raise HTTPException(status_code=500, detail="File upload failed")

        model = genai.GenerativeModel("gemini-2.0-flash")
        
        prompt = f"""Listen to this audio and find when the topic "{request.topic}" is first spoken or discussed.
Return ONLY the timestamp in HH:MM:SS format (e.g. 00:05:47).
Just the timestamp, nothing else."""

        response = model.generate_content(
            [uploaded_file, prompt],
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

    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=400, detail=f"yt-dlp error: {e.stderr.decode()}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
        if uploaded_file:
            try:
                genai.delete_file(uploaded_file.name)
            except:
                pass
