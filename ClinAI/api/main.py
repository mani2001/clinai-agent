from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.encoders import jsonable_encoder
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic_settings import BaseSettings
import google.generativeai as genai
import requests
import io
import uuid

from mcp_client import MCPClient

# ────────────────────────────────────────────────────────────────
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

class Settings(BaseSettings):
    server_script_path: str = os.getenv("SERVER_SCRIPT_PATH", "/Users/mani/Desktop/Clinai_project/ClinAI_server/main.py")
    mongodb_uri: str = os.getenv("ATLAS_URI")
    mongodb_db_name: str = os.getenv("MONGODB_DB_NAME", "clinical_data")
    mongodb_collection: str = os.getenv("MONGODB_COLLECTION", "patient_records")

settings = Settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    mcp_client = MCPClient()
    mongo_client = AsyncIOMotorClient(settings.mongodb_uri)
    try:
        await mcp_client.connect_to_server(settings.server_script_path)
        app.state.client = mcp_client
        app.state.db = mongo_client[settings.mongodb_db_name]
        yield
    finally:
        await mcp_client.cleanup()
        mongo_client.close()

app = FastAPI(title="ClinAI Client API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/patient/{patient_id}/details")
async def get_patient_details(patient_id: str):
    rec = await app.state.db[settings.mongodb_collection].find_one(
        {"patient_id": str(patient_id)},
        {"_id": 0, "note": 1, "conversation": 1},
    )
    if rec is None:
        raise HTTPException(status_code=404, detail="Patient not found")

    note, conversation = rec.get("note", ""), rec.get("conversation", "")
    if not (note or conversation):
        raise HTTPException(status_code=422, detail="No note or conversation available for patient")

    payload = {"note": note, "conversation": conversation}

    summary = await app.state.client.call_tool("patient_summary", payload)
    timeline = await app.state.client.call_tool("patient_timeline", payload)
    keywords = await app.state.client.call_tool("patient_keywords", payload)
    drugs = await app.state.client.call_tool("patient_prescriptions", payload)

    bundle: Dict[str, Any] = {
        "summary": summary,
        "timeline": timeline,
        "keywords": keywords,
        "prescriptions": drugs,
    }

    safe = jsonable_encoder(bundle)
    return JSONResponse(content=safe)

# ────────────────────────────────────────────────────────────────
# Static frontend pages
frontend_dir = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=frontend_dir / "static", html=True), name="static")

@app.get("/", include_in_schema=False)
async def serve_home():
    return FileResponse(frontend_dir / "index.html")

@app.get("/create", include_in_schema=False)
async def serve_create():
    return FileResponse(frontend_dir / "create.html")

@app.get("/patients", include_in_schema=False)
async def serve_patients_page():
    return FileResponse(frontend_dir / "patients.html")

# ────────────────────────────────────────────────────────────────
@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    try:
        audio_bytes = await file.read()
        headers = {
            "Authorization": f"Bearer " + os.getenv("GROQ_API_KEY")
        }
        files = {
            "file": (file.filename, audio_bytes, file.content_type)
        }
        data = {
            "model": "whisper-large-v3"
        }

        response = requests.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers=headers,
            files=files,
            data=data
        )

        if response.status_code == 200:
            transcription = response.json().get("text", "")
            return JSONResponse(content={"transcription": transcription})
        else:
            print("[GROQ ERROR]", response.status_code, response.text)
            return JSONResponse(
                content={"error": "Groq transcription failed", "details": response.text},
                status_code=response.status_code
            )

    except Exception as e:
        print("[SERVER ERROR]", str(e))
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.post("/label_conversation")
async def label_conversation(request: Request):
    body = await request.json()
    new_segment = body.get("conversation", "")
    previous = body.get("previous", "")

    full_conversation = (previous.strip() + "\n" + new_segment.strip()).strip()

    prompt = f"""You are a medical assistant. Label the following conversation with 'Doctor:' and 'Patient:' roles.
The doctor always speaks first.

### CONVERSATION
{full_conversation}

### LABELED OUTPUT (start immediately)
"""
    try:
        model = genai.GenerativeModel("models/gemini-2.0-flash")
        convo = model.start_chat()
        response = convo.send_message(prompt)
        labeled = response.text.strip()
        return JSONResponse(content={"labeled_conversation": labeled})
    except Exception as e:
        print("[GEMINI ERROR]", str(e))
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.post("/save_record")
async def save_record(request: Request):
    data = await request.json()
    conversation = data.get("conversation", "")
    notes = data.get("notes", "")

    content = f"--- Doctor-Patient Conversation ---\n{conversation}\n\n--- Doctor Notes ---\n{notes}"
    return StreamingResponse(
        iter([content]),
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=patient_record.txt"}
    )
