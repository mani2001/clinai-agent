from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.encoders import jsonable_encoder
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic_settings import BaseSettings

from mcp_client import MCPClient

# ────────────────────────────────────────────────────────────────
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

class Settings(BaseSettings):
    server_script_path: str = os.getenv(
        "SERVER_SCRIPT_PATH",
        "/Users/mani/Desktop/ClinAI_server/main.py",
    )
    mongodb_uri: str = os.getenv("ATLAS_URI")
    mongodb_db_name: str = os.getenv("MONGODB_DB_NAME", "clinical_data")
    mongodb_collection: str = os.getenv("MONGODB_COLLECTION", "patient_records")

settings = Settings()

# ────────────────────────────────────────────────────────────────
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

# ────────────────────────────────────────────────────────────────
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
        raise HTTPException(
            status_code=422, detail="No note or conversation available for patient"
        )

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
    print("Patient", patient_id, "bundle:\n", json.dumps(safe, indent=2), "\n")

    return JSONResponse(content=safe)

# ───────────────────────── Serve Frontend ─────────────────────────
frontend_dir = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=frontend_dir, html=True), name="static")

@app.get("/", include_in_schema=False)
async def serve_index():
    return FileResponse(frontend_dir / "index.html")

# ───────────────────────── Entrypoint ─────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
