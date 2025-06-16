from __future__ import annotations

import os
import traceback
from typing import Any, Dict

from dotenv import load_dotenv
import google.generativeai as genai
from mcp.server.fastmcp import FastMCP

# ───── Initialise ─────
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
_GEMINI_MODEL = "models/gemini-2.0-flash"
mcp = FastMCP("clinai")

print(f"[INIT] Server starting with model: {_GEMINI_MODEL}")

# ───── LLM Call Helper ─────
def call_gemini_text(prompt: str, temperature: float = 0.0) -> str:
    try:
        model = genai.GenerativeModel(_GEMINI_MODEL)
        resp = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=temperature,
                max_output_tokens=1024
            )
        )
        result = resp.text.strip()
        return result
    except Exception as e:
        print(f"[GEMINI TEXT ERROR] {e}")
        traceback.print_exc()
        return ""

# ───── Prompt Templates ─────

def summary_prompt(note: str, conv: str) -> str:
    return (
        "Summarize the provided clinical note and conversation in one concise paragraph (no more than 4 sentences). "
        "Include the overall clinical situation, main events, and outcome if stated. Only use the input provided.\n\n"
        f"Clinical Note: {note}\n"
        f"Conversation: {conv}"
    )

def timeline_prompt(note: str, conv: str) -> str:
    return (
        "Extract all major clinical events from the note and conversation, in clear chronological order. "
        "Return the result as a single Python-style string list, like ['event 1', 'event 2', ...]. "
        "Do not return as JSON, a paragraph, or a bulleted list. "
        "Only use the information provided.\n\n"
        f"Clinical Note: {note}\n"
        f"Conversation: {conv}"
    )

def prescriptions_prompt(note: str, conv: str) -> str:
    return (
        "Extract all prescription medications mentioned in the clinical note or conversation. "
        "For each medication, return a line in the format: "
        "'Drug: <drug name>, Dose: <dose>, Route: <route>, Status: <status>'. "
        "Possible status values: 'active' (doctor prescribed), 'stopped' (doctor told to stop), 'continuing' (doctor said to continue or did not specify). "
        "If a field is missing or not specified, use 'NA'. Return a plain list of lines, not JSON. "
        "If no medications, return 'No prescriptions found.'\n\n"
        f"Clinical Note: {note}\n"
        f"Conversation: {conv}\n"
    )

def keywords_prompt(note: str, conv: str) -> str:
    return (
        "Extract all main medical keywords, including primary problems, diseases, symptoms, medicines, and diagnostic tests "
        "from the clinical note and conversation. Return the keywords as a plain, comma-separated list. "
        "Do not return as JSON or a list object—just a readable comma-separated string. "
        "If nothing found, return 'No main keywords found.'\n\n"
        f"Clinical Note: {note}\n"
        f"Conversation: {conv}\n"
    )

def name_prompt(note: str, conv: str) -> str:
    return (
        "Extract only the patient's name from the clinical note and conversation. "
        "Return just the name, nothing else. If not found, return 'NA'.\n\n"
        f"Clinical Note: {note}\n"
        f"Conversation: {conv}\n"
    )

def age_prompt(note: str, conv: str) -> str:
    return (
        "Extract only the patient's age from the clinical note and conversation. "
        "Return just the age number, nothing else. If not found, return 'NA'.\n\n"
        f"Clinical Note: {note}\n"
        f"Conversation: {conv}\n"
    )

def gender_prompt(note: str, conv: str) -> str:
    return (
        "Extract only the patient's gender from the clinical note and conversation. "
        "Return just the gender (Male/Female/M/F), nothing else. If not found, return 'NA'.\n\n"
        f"Clinical Note: {note}\n"
        f"Conversation: {conv}\n"
    )

# ───── Extractor Functions ─────

def get_summary(n: str, c: str) -> str:
    try:
        prompt = summary_prompt(n, c)
        result = call_gemini_text(prompt)
        return result.strip()
    except Exception as e:
        print(f"[SUMMARY ERROR] Exception: {e}")
        traceback.print_exc()
        return ""

def get_timeline(n: str, c: str) -> str:
    try:
        prompt = timeline_prompt(n, c)
        result = call_gemini_text(prompt)
        return result.strip()
    except Exception as e:
        print(f"[TIMELINE ERROR] Exception: {e}")
        traceback.print_exc()
        return "[]"

def get_keywords(n: str, c: str) -> str:
    try:
        prompt = keywords_prompt(n, c)
        result = call_gemini_text(prompt)
        return result.strip()
    except Exception as e:
        print(f"[KEYWORDS ERROR] Exception: {e}")
        traceback.print_exc()
        return "No main keywords found."

def get_prescriptions(n: str, c: str) -> str:
    try:
        prompt = prescriptions_prompt(n, c)
        result = call_gemini_text(prompt)
        return result.strip()
    except Exception as e:
        print(f"[PRESCRIPTIONS ERROR] Exception: {e}")
        traceback.print_exc()
        return "No prescriptions found."

def get_name(n: str, c: str) -> str:
    try:
        prompt = name_prompt(n, c)
        result = call_gemini_text(prompt)
        return result.strip()
    except Exception as e:
        print(f"[NAME ERROR] Exception: {e}")
        traceback.print_exc()
        return "NA"

def get_age(n: str, c: str) -> str:
    try:
        prompt = age_prompt(n, c)
        result = call_gemini_text(prompt)
        return result.strip()
    except Exception as e:
        print(f"[AGE ERROR] Exception: {e}")
        traceback.print_exc()
        return "NA"

def get_gender(n: str, c: str) -> str:
    try:
        prompt = gender_prompt(n, c)
        result = call_gemini_text(prompt)
        return result.strip()
    except Exception as e:
        print(f"[GENDER ERROR] Exception: {e}")
        traceback.print_exc()
        return "NA"

# ───── MCP Tool Registration ─────

@mcp.tool()
def patient_summary(data: Dict[str, str]) -> str:
    note = data.get("note", "")
    conversation = data.get("conversation", "")
    result = get_summary(note, conversation)
    print(f"[TOOL] Summary result: {result}")
    return result

@mcp.tool()
def patient_timeline(data: Dict[str, str]) -> str:
    note = data.get("note", "")
    conversation = data.get("conversation", "")
    result = get_timeline(note, conversation)
    print(f"[TOOL] Timeline result: {result}")
    return result

@mcp.tool()
def patient_keywords(data: Dict[str, str]) -> str:
    note = data.get("note", "")
    conversation = data.get("conversation", "")
    result = get_keywords(note, conversation)
    print(f"[TOOL] Keywords result: {result}")
    return result

@mcp.tool()
def patient_prescriptions(data: Dict[str, str]) -> str:
    note = data.get("note", "")
    conversation = data.get("conversation", "")
    result = get_prescriptions(note, conversation)
    print(f"[TOOL] Prescriptions result: {result}")
    return result

@mcp.tool()
def patient_name(data: Dict[str, str]) -> str:
    note = data.get("note", "")
    conversation = data.get("conversation", "")
    result = get_name(note, conversation)
    print(f"[TOOL] Name result: {result}")
    return result

@mcp.tool()
def patient_age(data: Dict[str, str]) -> str:
    note = data.get("note", "")
    conversation = data.get("conversation", "")
    result = get_age(note, conversation)
    print(f"[TOOL] Age result: {result}")
    return result

@mcp.tool()
def patient_gender(data: Dict[str, str]) -> str:
    note = data.get("note", "")
    conversation = data.get("conversation", "")
    result = get_gender(note, conversation)
    print(f"[TOOL] Gender result: {result}")
    return result

# ───── Run MCP Server ─────

if __name__ == "__main__":
    print("[MAIN] Starting MCP server...")
    mcp.run(transport="stdio")