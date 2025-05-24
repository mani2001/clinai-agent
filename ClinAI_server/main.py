from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from dotenv import load_dotenv
import google.generativeai as genai
from mcp.server.fastmcp import FastMCP

# ───────────────────────── initialise ─────────────────────────
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

_GEMINI_MODEL = "models/gemini-2.0-flash"
mcp = FastMCP("clinai")

# ───────────────────────── utility: safe JSON parse ─────────────────────────
def _safe_json(raw: str, fallback: Any) -> Any:
    try:
        return json.loads(raw.strip())
    except Exception as e:
        print(f"JSON parse failed: {e}\nPayload was:\n{raw[:200]}\n")
        return fallback

# ───────────────────────── LLM wrapper ─────────────────────────
def call_gemini_llm(
    messages: List[Dict[str, str]],
    model: str = _GEMINI_MODEL,
    temperature: float = 0.0,
) -> str:
    chat = genai.GenerativeModel(model)
    convo = chat.start_chat(history=messages[:-1])
    resp = convo.send_message(
        messages[-1]["content"],
        generation_config=genai.GenerationConfig(temperature=temperature),
    )
    return resp.text.strip()

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

# ───────────────────────── prompt helpers ─────────────────────
def summary_prompt(note: str, conv: str) -> str:
    return f"""Write one paragraph (max 4 sentences) summarising the clinical situation, key events, and outcome.

### NOTE
{note}

### CONVERSATION
{conv}"""

def timeline_prompt(note: str, conv: str) -> str:
    return f"""Extract chronological events from this clinical case. List events in order with short phrasing and prepend date if known.

### NOTE
{note}

### CONVERSATION
{conv}"""

def drugs_prompt(note: str, conv: str) -> str:
    return f"""Extract ALL medications mentioned in this clinical case. For each medication, identify:
- The drug name
- Route of administration (oral, IV, subcutaneous, etc.)
- Dosage information
- Current status (added by doctor, continued, discontinued, or mentioned)

### NOTE
{note}

### CONVERSATION
{conv}"""

def keywords_prompt(note: str, conv: str) -> str:
    return f"""Extract up to 7 condition or disease keywords that best describe this clinical case.

### NOTE
{note}

### CONVERSATION
{conv}"""

# ───────────────────────── response schemas ─────────────────────────
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
    "items": {
        "type": "string"
    }
}

KEYWORDS_SCHEMA = {
    "type": "array",
    "items": {
        "type": "string"
    }
}

# ───────────────────────── LLM extractors ─────────────────────
def get_summary(n: str, c: str) -> str:
    return call_gemini_llm([{"role": "user", "content": summary_prompt(n, c)}])

def get_timeline(n: str, c: str) -> List[str]:
    try:
        return call_gemini_structured([{"role": "user", "content": timeline_prompt(n, c)}], TIMELINE_SCHEMA)
    except Exception as e:
        print(f"Structured timeline extraction failed: {e}")
        return []

def get_keywords(n: str, c: str) -> List[str]:
    try:
        return call_gemini_structured([{"role": "user", "content": keywords_prompt(n, c)}], KEYWORDS_SCHEMA)
    except Exception as e:
        print(f"Structured keywords extraction failed: {e}")
        return []

def get_prescriptions(n: str, c: str) -> List[Dict[str, str]]:
    try:
        return call_gemini_structured([{"role": "user", "content": drugs_prompt(n, c)}], PRESCRIPTION_SCHEMA)
    except Exception as e:
        print(f"Structured prescription extraction failed: {e}")
        return []

# ───────────────────────── MCP tools ──────────────────────────
@mcp.tool()
def patient_summary(data: Dict[str, str]) -> str:
    """One-paragraph clinical summary."""
    return get_summary(data["note"], data["conversation"])

@mcp.tool()
def patient_timeline(data: Dict[str, str]) -> List[str]:
    """Chronological events as strings."""
    return get_timeline(data["note"], data["conversation"])

@mcp.tool()
def patient_keywords(data: Dict[str, str]) -> List[str]:
    """Disease/condition keywords."""
    return get_keywords(data["note"], data["conversation"])

@mcp.tool()
def patient_prescriptions(data: Dict[str, str]) -> List[Dict[str, str]]:
    """All medications with route, dose, status."""
    return get_prescriptions(data["note"], data["conversation"])

# ───────────────────────── run server ─────────────────────────
if __name__ == "__main__":
    mcp.run(transport="stdio")
