# ClinAI_server/main.py – Gemini + MCP-aligned structured prompts
from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from dotenv import load_dotenv
import google.generativeai as genai
from mcp.server.fastmcp import FastMCP

# ────────────── initialise ──────────────
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

_GEMINI_MODEL = "models/gemini-2.0-flash"
mcp = FastMCP("clinai")

# ────────────── utility: safe JSON parse ──────────────

def _safe_json(raw: str, fallback: Any) -> Any:
    try:
        return json.loads(raw.strip())
    except Exception as e:
        print(f"JSON parse failed: {e}\nPayload was:\n{raw[:200]}\n")
        return fallback

# ────────────── LLM wrapper ──────────────

def call_gemini_structured(
    messages: List[Dict[str, str]],
    response_schema: Dict,
    model: str = _GEMINI_MODEL,
    temperature: float = 0.0,
) -> Any:
    chat = genai.GenerativeModel(model)
    convo = chat.start_chat(history=messages[:-1])
    resp = convo.send_message(
        messages[-1]["content"],
        generation_config=genai.GenerationConfig(
            temperature=temperature,
            response_schema=response_schema,
            response_mime_type="application/json"
        ),
    )
    return json.loads(resp.text.strip())

# ────────────── prompt helpers ──────────────

def summary_prompt(note: str, conv: str) -> str:
    return f"""You are a clinical summarization assistant.
Summarize the patient's case in one paragraph (max 4 sentences).

### NOTE
{note}

### CONVERSATION
{conv}"""

def timeline_prompt(note: str, conv: str) -> str:
    return f"""You are a medical reasoning assistant. Extract the chronological list of key clinical events.
Each event must be a concise string. Return a JSON array.

### NOTE
{note}

### CONVERSATION
{conv}"""

def drugs_prompt(note: str, conv: str) -> str:
    return f"""You are a medical assistant. Extract all mentioned medications and provide:
- Drug name
- Route (oral, IV, etc.)
- Dosage
- Status: one of ["added by doctor", "continued", "discontinued", "mentioned"]
Return a JSON array.

### NOTE
{note}

### CONVERSATION
{conv}"""

def keywords_prompt(note: str, conv: str) -> str:
    return f"""Identify up to 7 key disease or condition keywords describing this case. Return a JSON array.

### NOTE
{note}

### CONVERSATION
{conv}"""

# ────────────── schemas ──────────────
PRESCRIPTION_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "drug": {"type": "string"},
            "route": {"type": "string"},
            "dose": {"type": "string"},
            "status": {
                "type": "string",
                "enum": ["added by doctor", "continued", "discontinued", "mentioned"]
            }
        },
        "required": ["drug", "route", "dose", "status"]
    }
}

TIMELINE_SCHEMA = {
    "type": "array",
    "items": {"type": "string"}
}

KEYWORDS_SCHEMA = {
    "type": "array",
    "items": {"type": "string"},
}

# ────────────── extractors ──────────────

def get_summary(n: str, c: str) -> str:
    return call_gemini_structured([{"role": "user", "content": summary_prompt(n, c)}], {"type": "string"})

def get_timeline(n: str, c: str) -> List[str]:
    return call_gemini_structured([{"role": "user", "content": timeline_prompt(n, c)}], TIMELINE_SCHEMA)

def get_keywords(n: str, c: str) -> List[str]:
    return call_gemini_structured([{"role": "user", "content": keywords_prompt(n, c)}], KEYWORDS_SCHEMA)

def get_prescriptions(n: str, c: str) -> List[Dict[str, str]]:
    return call_gemini_structured([{"role": "user", "content": drugs_prompt(n, c)}], PRESCRIPTION_SCHEMA)

# ────────────── MCP tools ──────────────
@mcp.tool()
def patient_summary(note: str, conversation: str) -> str:
    """One-paragraph clinical summary."""
    return get_summary(note, conversation)

@mcp.tool()
def patient_timeline(note: str, conversation: str) -> List[str]:
    """Chronological events as strings."""
    return get_timeline(note, conversation)

@mcp.tool()
def patient_keywords(note: str, conversation: str) -> List[str]:
    """Disease/condition keywords."""
    return get_keywords(note, conversation)

@mcp.tool()
def patient_prescriptions(note: str, conversation: str) -> List[Dict[str, str]]:
    """All medications with route, dose, status."""
    return get_prescriptions(note, conversation)

# ────────────── run server ──────────────
if __name__ == "__main__":
    mcp.run(transport="stdio")
