from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List

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
import json

from mcp_client import MCPClient
from mcp.types import CallToolResult, TextContent

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
        {"_id": 0, "summary": 1, "keywords": 1, "name": 1, "age": 1, "gender": 1},
    )
    if rec is None:
        raise HTTPException(status_code=404, detail="Patient not found")

    # Parse keywords if it's comma-separated
    keywords_raw = rec.get("keywords", "")
    keywords_parsed = []
    if keywords_raw and keywords_raw != "No main keywords found.":
        keywords_parsed = [k.strip() for k in keywords_raw.split(",")]

    # Pass through the stored data, properly formatted
    bundle: Dict[str, Any] = {
        "summary": rec.get("summary", ""),
        "keywords": keywords_parsed,
        "name": rec.get("name", "N/A"),
        "age": rec.get("age", "N/A"), 
        "gender": rec.get("gender", "N/A")
    }

    return JSONResponse(content=bundle)

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

@app.get("/patient/{patient_id}", include_in_schema=False)
async def serve_patient_page(patient_id: str):
    return FileResponse(frontend_dir / "patient.html")

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
            print(f"[GROQ ERROR] Status: {response.status_code}, Response: {response.text}")
            return JSONResponse(
                content={"error": "Groq transcription failed", "details": response.text},
                status_code=response.status_code
            )

    except Exception as e:
        print(f"[SERVER ERROR] {str(e)}")
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
        print(f"[GEMINI ERROR] {str(e)}")
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

        # Log inputs for debugging
        print(f"[SAVE_RECORD INPUT] patient_id: {idx}\nnotes: {notes[:200]}\nconversation: {conversation[:200]}")
        print(f"[SAVE_RECORD INPUT] Full notes length: {len(notes)}")
        print(f"[SAVE_RECORD INPUT] Full conversation length: {len(conversation)}")

        payload = {"data": {"note": notes, "conversation": conversation}}

        # Timeline (paragraph)
        try:
            timeline_result = await app.state.client.call_tool("patient_timeline", payload)
            timeline = timeline_result.content[0].text if isinstance(timeline_result, CallToolResult) and timeline_result.content else ""
            print(f"[MCP TOOL OUTPUT] patient_timeline for patient_id: {idx}\n{timeline}")
        except Exception as e:
            print(f"[MCP TOOL ERROR] patient_timeline failed for patient_id: {idx}: {str(e)}")
            timeline = ""

        # Keywords (plain string)
        try:
            keywords_result = await app.state.client.call_tool("patient_keywords", payload)
            keywords = keywords_result.content[0].text if isinstance(keywords_result, CallToolResult) and keywords_result.content else ""
            print(f"[MCP TOOL OUTPUT] patient_keywords for patient_id: {idx}\n{keywords}")
        except Exception as e:
            print(f"[MCP TOOL ERROR] patient_keywords failed for patient_id: {idx}: {str(e)}")
            keywords = ""

        # Prescriptions (plain string)
        try:
            prescriptions_result = await app.state.client.call_tool("patient_prescriptions", payload)
            prescriptions = prescriptions_result.content[0].text if isinstance(prescriptions_result, CallToolResult) and prescriptions_result.content else ""
            print(f"[MCP TOOL OUTPUT] patient_prescriptions for patient_id: {idx}\n{prescriptions}")
        except Exception as e:
            print(f"[MCP TOOL ERROR] patient_prescriptions failed for patient_id: {idx}: {str(e)}")
            prescriptions = ""

        # Summary (paragraph)
        try:
            summary_result = await app.state.client.call_tool("patient_summary", payload)
            summary = summary_result.content[0].text if isinstance(summary_result, CallToolResult) and summary_result.content else ""
            print(f"[MCP TOOL OUTPUT] patient_summary for patient_id: {idx}\n{summary}")
        except Exception as e:
            print(f"[MCP TOOL ERROR] patient_summary failed for patient_id: {idx}: {str(e)}")
            summary = ""

        # Name
        try:
            name_result = await app.state.client.call_tool("patient_name", payload)
            name = name_result.content[0].text if isinstance(name_result, CallToolResult) and name_result.content else "NA"
            print(f"[MCP TOOL OUTPUT] patient_name for patient_id: {idx}\n{name}")
        except Exception as e:
            print(f"[MCP TOOL ERROR] patient_name failed for patient_id: {idx}: {str(e)}")
            name = "NA"

        # Age
        try:
            age_result = await app.state.client.call_tool("patient_age", payload)
            age = age_result.content[0].text if isinstance(age_result, CallToolResult) and age_result.content else "NA"
            print(f"[MCP TOOL OUTPUT] patient_age for patient_id: {idx}\n{age}")
        except Exception as e:
            print(f"[MCP TOOL ERROR] patient_age failed for patient_id: {idx}: {str(e)}")
            age = "NA"

        # Gender
        try:
            gender_result = await app.state.client.call_tool("patient_gender", payload)
            gender = gender_result.content[0].text if isinstance(gender_result, CallToolResult) and gender_result.content else "NA"
            print(f"[MCP TOOL OUTPUT] patient_gender for patient_id: {idx}\n{gender}")
        except Exception as e:
            print(f"[MCP TOOL ERROR] patient_gender failed for patient_id: {idx}: {str(e)}")
            gender = "NA"

        # Create the record to store in MongoDB
        record = {
            "patient_id": idx,
            "conversation": conversation,
            "note": notes,
            "summary": summary,
            "timeline": timeline,
            "keywords": keywords,
            "prescriptions": prescriptions,
            "name": name,
            "age": age,
            "gender": gender
        }

        # Save to MongoDB
        result = await app.state.db[settings.mongodb_collection].update_one(
            {"patient_id": idx},
            {"$set": record},
            upsert=True
        )

        print(f"[MONGODB] Record saved for patient_id: {idx}, Modified: {result.modified_count}, Upserted: {result.upserted_id}")

        return JSONResponse(content={"message": f"Record saved successfully for patient {idx}"}, status_code=200)

    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"[MCP/MONGODB ERROR] Failed to process or save record: {str(e)}")
        return JSONResponse(content={"error": f"Failed to save record: {str(e)}"}, status_code=500)

@app.get("/api/patient/{patient_id}")
async def get_patient_data(patient_id: str):
    try:
        rec = await app.state.db[settings.mongodb_collection].find_one(
            {"patient_id": str(patient_id)},
            {"_id": 0, "note": 1, "summary": 1, "prescriptions": 1, "timeline": 1, "keywords": 1, "name": 1, "age": 1, "gender": 1}
        )
        if rec is None:
            raise HTTPException(status_code=404, detail="Patient not found")

        data = {
            "note": rec.get("note", ""),
            "summary": rec.get("summary", ""),
            "prescriptions": rec.get("prescriptions", ""),
            "timeline": rec.get("timeline", ""),
            "keywords": rec.get("keywords", ""),
            "name": rec.get("name", "N/A"),
            "age": rec.get("age", "N/A"),
            "gender": rec.get("gender", "N/A")
        }

        return JSONResponse(content=data)
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"[MONGODB ERROR] Failed to fetch patient data: {e}")
        return JSONResponse(content={"error": f"Failed to fetch patient data: {str(e)}"}, status_code=500)

@app.patch("/patient/{patient_id}/keywords")
async def update_patient_keywords(patient_id: str, request: Request):
    try:
        data = await request.json()
        keywords = data.get("keywords", "")
        if not isinstance(keywords, str):
            raise HTTPException(status_code=400, detail="Keywords must be a string")

        result = await app.state.db[settings.mongodb_collection].update_one(
            {"patient_id": str(patient_id)},
            {"$set": {"keywords": keywords}}
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Patient not found")

        print(f"[MONGODB] Updated keywords for patient_id: {patient_id}")
        return JSONResponse(content={"message": f"Keywords updated successfully for patient {patient_id}"}, status_code=200)
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"[MONGODB ERROR] Failed to update keywords: {e}")
        return JSONResponse(content={"error": f"Failed to update keywords: {str(e)}"}, status_code=500)