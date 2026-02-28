import os
import time
import tempfile
import subprocess
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
        # Step 1: Download audio using yt-dlp
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp:
            tmp_path = tmp.name

        subprocess.run([
            "yt-dlp",
            "-x", "--audio-format", "mp3",
            "--audio-quality", "0",
            "-o", tmp_path,
            "--no-playlist",
            request.video_url
        ], check=True, capture_output=True)

        # Step 2: Upload to Gemini Files API
        uploaded_file = genai.upload_file(tmp_path, mime_type="audio/mpeg")

        # Step 3: Poll until ACTIVE
        while uploaded_file.state.name == "PROCESSING":
            time.sleep(2)
            uploaded_file = genai.get_file(uploaded_file.name)

        if uploaded_file.state.name != "ACTIVE":
            raise HTTPException(status_code=500, detail="File upload failed")

        # Step 4: Ask Gemini for timestamp
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

        import json
        result = json.loads(response.text)
        timestamp = result["timestamp"]

        # Ensure HH:MM:SS format
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
        # Cleanup
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
        if uploaded_file:
            try:
                genai.delete_file(uploaded_file.name)
            except:
                pass
