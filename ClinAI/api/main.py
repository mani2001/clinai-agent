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
    try:
        data = await request.json()
        idx = data.get("idx", "").strip()
        conversation = data.get("conversation", "").strip()
        notes = data.get("notes", "").strip()

        # Validate inputs
        if not idx:
            raise HTTPException(status_code=400, detail="Patient ID is required")
        if not (conversation or notes):
            raise HTTPException(status_code=400, detail="Conversation or notes must be provided")

        # Create payload with nested 'data' field as expected by MCP tools
        payload = {"data": {"note": notes, "conversation": conversation}}
        
        # Call MCP tools and extract content from CallToolResult
        summary_result = await app.state.client.call_tool("patient_summary", payload)
        timeline_result = await app.state.client.call_tool("patient_timeline", payload)
        keywords_result = await app.state.client.call_tool("patient_keywords", payload)
        prescriptions_result = await app.state.client.call_tool("patient_prescriptions", payload)

        # Extract content, handling potential errors
        summary = summary_result.content[0].text if summary_result.content and not summary_result.isError else ""
        timeline = timeline_result.content[0].text if timeline_result.content and not timeline_result.isError else []
        keywords = keywords_result.content[0].text if keywords_result.content and not timeline_result.isError else []
        prescriptions = prescriptions_result.content[0].text if prescriptions_result.content and not prescriptions_result.isError else []

        # If any tool returned an error, log it for debugging
        if summary_result.isError:
            print(f"[MCP ERROR] patient_summary failed: {summary_result.content[0].text}")
        if timeline_result.isError:
            print(f"[MCP ERROR] patient_timeline failed: {timeline_result.content[0].text}")
        if keywords_result.isError:
            print(f"[MCP ERROR] patient_keywords failed: {keywords_result.content[0].text}")
        if prescriptions_result.isError:
            print(f"[MCP ERROR] patient_prescriptions failed: {prescriptions_result.content[0].text}")

        # Create the record to store in MongoDB
        record = {
            "patient_id": idx,
            "conversation": conversation,
            "note": notes,
            "summary": summary,
            "timeline": timeline,
            "keywords": keywords,
            "prescriptions": prescriptions
        }

        # Save to MongoDB
        result = await app.state.db[settings.mongodb_collection].update_one(
            {"patient_id": idx},
            {"$set": record},
            upsert=True
        )

        # Log outcome for debugging
        print(f"[MONGODB] Record saved for patient_id: {idx}, Modified: {result.modified_count}, Upserted: {result.upserted_id}")

        # Return JSON response instead of file download
        return JSONResponse(content={"message": f"Record saved successfully for patient {idx}"}, status_code=200)

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"[MCP/MONGODB ERROR] Failed to process or save record: {e}")
        return JSONResponse(content={"error": f"Failed to save record: {str(e)}"}, status_code=500)

@app.post("/delete_record")
async def delete_record(request: Request):
    try:
        data = await request.json()
        patient_id = data.get("patient_id", "").strip()

        # Validate input
        if not patient_id:
            raise HTTPException(status_code=400, detail="Patient ID is required")

        # Delete the record from MongoDB
        result = await app.state.db[settings.mongodb_collection].delete_one(
            {"patient_id": patient_id}
        )

        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail=f"No record found for patient ID {patient_id}")

        # Log outcome for debugging
        print(f"[MONGODB] Deleted record for patient_id: {patient_id}")

        return JSONResponse(content={"message": f"Record for patient {patient_id} deleted successfully"}, status_code=200)

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"[MONGODB ERROR] Failed to delete record: {e}")
        return JSONResponse(content={"error": f"Failed to delete record: {str(e)}"}, status_code=500)