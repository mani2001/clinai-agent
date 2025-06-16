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

@app.patch("/patient/{patient_id}/summary")
async def update_patient_summary(patient_id: str, request: Request):
    try:
        data = await request.json()
        summary = data.get("summary", "")
        if not isinstance(summary, str):
            raise HTTPException(status_code=400, detail="Summary must be a string")

        result = await app.state.db[settings.mongodb_collection].update_one(
            {"patient_id": str(patient_id)},
            {"$set": {"summary": summary}}
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Patient not found")

        print(f"[MONGODB] Updated summary for patient_id: {patient_id}")
        return JSONResponse(content={"message": f"Summary updated successfully for patient {patient_id}"}, status_code=200)
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"[MONGODB ERROR] Failed to update summary: {e}")
        return JSONResponse(content={"error": f"Failed to update summary: {str(e)}"}, status_code=500)

@app.patch("/patient/{patient_id}/timeline")
async def update_patient_timeline(patient_id: str, request: Request):
    try:
        data = await request.json()
        timeline = data.get("timeline", "")
        if not isinstance(timeline, str):
            raise HTTPException(status_code=400, detail="Timeline must be a string")

        result = await app.state.db[settings.mongodb_collection].update_one(
            {"patient_id": str(patient_id)},
            {"$set": {"timeline": timeline}}
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Patient not found")

        print(f"[MONGODB] Updated timeline for patient_id: {patient_id}")
        return JSONResponse(content={"message": f"Timeline updated successfully for patient {patient_id}"}, status_code=200)
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"[MONGODB ERROR] Failed to update timeline: {e}")
        return JSONResponse(content={"error": f"Failed to update timeline: {str(e)}"}, status_code=500)

@app.patch("/patient/{patient_id}/prescriptions")
async def update_patient_prescriptions(patient_id: str, request: Request):
    try:
        data = await request.json()
        prescriptions = data.get("prescriptions", "")
        if not isinstance(prescriptions, str):
            raise HTTPException(status_code=400, detail="Prescriptions must be a string")

        result = await app.state.db[settings.mongodb_collection].update_one(
            {"patient_id": str(patient_id)},
            {"$set": {"prescriptions": prescriptions}}
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Patient not found")

        print(f"[MONGODB] Updated prescriptions for patient_id: {patient_id}")
        return JSONResponse(content={"message": f"Prescriptions updated successfully for patient {patient_id}"}, status_code=200)
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"[MONGODB ERROR] Failed to update prescriptions: {e}")
        return JSONResponse(content={"error": f"Failed to update prescriptions: {str(e)}"}, status_code=500)
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
@app.get("/update-patients", include_in_schema=False)
async def serve_update_patients_page():
    return FileResponse(frontend_dir / "updatepatients.html")

@app.get("/update-patient/{patient_id}", include_in_schema=False)
async def serve_update_patient_detail_page(patient_id: str):
    return FileResponse(frontend_dir / "updatepatient.html")

@app.get("/patients", include_in_schema=False)
async def serve_patients_page():
    return FileResponse(frontend_dir / "patients.html")
# Add this to your main.py - Semantic Search Backend

# Add this to your main.py - Semantic Search Backend

@app.get("/semantic-search", include_in_schema=False)
async def serve_semantic_search_page():
    return FileResponse(frontend_dir / "semantic-search.html")

@app.post("/api/search")
async def semantic_search(request: Request):
    try:
        data = await request.json()
        query = data.get("query", "").strip()
        
        if not query:
            raise HTTPException(status_code=400, detail="Query is required")
        
        print(f"[SEMANTIC SEARCH] Query: {query}")
        
        # Step 1: Use Gemini to analyze the query and extract medical concepts
        search_structure = await extract_structured_search_terms(query)
        print(f"[SEMANTIC SEARCH] Extracted structure: {search_structure}")
        
        # Step 2: Use extracted medical concepts to search MongoDB
        patients = await search_patient_records(search_structure)
        print(f"[SEMANTIC SEARCH] Found {len(patients)} patients")
        
        # Step 3: Use Gemini to rank results by clinical relevance
        ranked_results = await rank_search_results(query, search_structure, patients)
        
        # Return top results
        top_results = ranked_results[:5]
        
        return JSONResponse(content={
            "results": top_results,
            "total_found": len(patients),
            "query": query
        })
        
    except Exception as e:
        print(f"[SEMANTIC SEARCH ERROR] {e}")
        import traceback
        traceback.print_exc()
        return JSONResponse(
            content={"error": f"Search failed: {str(e)}"}, 
            status_code=500
        )

async def extract_structured_search_terms(query: str) -> Dict[str, Any]:
    """Use Gemini to extract detailed structured search terms from natural language query"""
    try:
        prompt = f"""
You are a clinical search expert. Analyze this search query and extract structured search terms for finding relevant patient records in a medical database. Your task is to convert any natural language descriptions into proper medical terminology.

Query: "{query}"

Return a comprehensive JSON object with these fields:
1. "required_terms": List of medical terms that MUST be matched (core conditions/symptoms)
2. "optional_terms": List of medical terms that are helpful but not required
3. "medical_context": Brief clinical interpretation of the query
4. "synonyms": Medical synonyms for the main condition (up to 5)
5. "implied_conditions": List of clinical conditions implied by the description
6. "demographics": Object with age_range (e.g. "30-45", "65+"), gender if mentioned

In all cases, extract the proper medical terms for what is being described, even if the query uses layperson terms.
For example, convert descriptions of symptoms into likely medical diagnoses.

Return valid JSON only:
"""
        
        model = genai.GenerativeModel("models/gemini-2.0-flash")
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.1,
                response_mime_type="application/json",
                max_output_tokens=1200
            )
        )
        
        result = json.loads(response.text.strip())
        
        # Add query as fallback
        if "original_query" not in result:
            result["original_query"] = query
            
        return result
        
    except Exception as e:
        print(f"[EXTRACT STRUCTURED TERMS ERROR] {e}")
        # Minimal fallback with just original query
        return {
            "required_terms": [],
            "optional_terms": [],
            "medical_context": query,
            "synonyms": [],
            "implied_conditions": [],
            "demographics": {},
            "original_query": query
        }
        
        model = genai.GenerativeModel("models/gemini-2.0-flash")
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.1,
                response_mime_type="application/json",
                max_output_tokens=1200
            )
        )
        
        result = json.loads(response.text.strip())
        
        # Add query as fallback
        if "original_query" not in result:
            result["original_query"] = query
            
        return result
        
    except Exception as e:
        print(f"[EXTRACT STRUCTURED TERMS ERROR] {e}")
        # Fallback with basic structure
        return {
            "required_terms": [query.lower().split()],
            "optional_terms": [],
            "excluded_terms": [],
            "medications": [],
            "demographics": {},
            "medical_context": query,
            "synonyms": [],
            "search_priority": "recall",
            "original_query": query
        }

async def search_patient_records(search_structure: Dict[str, Any]) -> List[Dict]:
    """Search MongoDB for patients matching the extracted medical concepts"""
    try:
        # All search terms from the search structure
        all_search_terms = []
        
        # Add required terms
        if search_structure.get("required_terms"):
            all_search_terms.extend(search_structure["required_terms"])
        
        # Add synonyms
        if search_structure.get("synonyms"):
            all_search_terms.extend(search_structure["synonyms"])
        
        # Add implied conditions (important for descriptive queries)
        if search_structure.get("implied_conditions"):
            all_search_terms.extend(search_structure["implied_conditions"])
        
        # Prioritize the keywords field for searching
        query_conditions = []
        
        # Create an $or query with each term
        for term in all_search_terms:
            if term and len(term) > 2:  # Skip very short terms
                # Prioritize keywords field
                query_conditions.append({"keywords": {"$regex": f"{term}", "$options": "i"}})
        
        # If no terms were extracted, use the original query
        if not query_conditions and search_structure.get("medical_context"):
            medical_context = search_structure["medical_context"]
            # Try to match with the medical context
            query_conditions.append({"keywords": {"$regex": f"{medical_context}", "$options": "i"}})
        
        # If still no terms, use the original query
        if not query_conditions and search_structure.get("original_query"):
            query_conditions.append({"keywords": {"$regex": f"{search_structure['original_query']}", "$options": "i"}})
        
        # Build the final query
        final_query = {"$or": query_conditions} if query_conditions else {"keywords": {"$exists": True}}
        
        # Add demographic filters if present
        demographics = search_structure.get("demographics", {})
        if demographics:
            demographic_conditions = []
            if demographics.get("gender"):
                demographic_conditions.append({"gender": {"$regex": demographics["gender"], "$options": "i"}})
            
            if demographics.get("age_range"):
                age_range = demographics["age_range"]
                if "-" in age_range:
                    min_age, max_age = age_range.split("-")
                    demographic_conditions.append({"age": {"$gte": min_age, "$lte": max_age}})
                elif "+" in age_range:
                    min_age = age_range.replace("+", "")
                    demographic_conditions.append({"age": {"$gte": min_age}})
                else:
                    demographic_conditions.append({"age": age_range})
            
            # Add demographic conditions to the final query
            if demographic_conditions:
                final_query = {"$and": [final_query, {"$and": demographic_conditions}]}
        
        print(f"[SEARCH DEBUG] MongoDB query: {final_query}")
        
        # Execute MongoDB query with field projections
        cursor = app.state.db[settings.mongodb_collection].find(
            final_query,
            {
                "_id": 0,
                "patient_id": 1,
                "name": 1,
                "age": 1,
                "gender": 1,
                "summary": 1,
                "keywords": 1,
                "prescriptions": 1,
                "timeline": 1
            }
        ).limit(20)
        
        patients = await cursor.to_list(length=20)
        print(f"[SEARCH DEBUG] Found {len(patients)} patients")
        
        return patients
        
    except Exception as e:
        print(f"[SEARCH ERROR] {e}")
        import traceback
        traceback.print_exc()
        return []

# Remove these functions as they're no longer used
def build_term_condition(term: str) -> Dict:
    """Build a MongoDB condition for searching a term across multiple fields with word boundaries"""
    # Escape regex special characters in the term
    safe_term = term.replace("\\", "\\\\").replace(".", "\\.").replace("*", "\\*")
    safe_term = safe_term.replace("+", "\\+").replace("?", "\\?").replace("|", "\\|")
    safe_term = safe_term.replace("(", "\\(").replace(")", "\\)").replace("[", "\\[")
    safe_term = safe_term.replace("]", "\\]").replace("{", "\\{").replace("}", "\\}")
    
    # Use word boundaries for more precise matching
    word_boundary_term = f"\\b{safe_term}\\b"
    
    # Order fields by importance for searching
    return {"$or": [
        {"keywords": {"$regex": word_boundary_term, "$options": "i"}},
        {"summary": {"$regex": word_boundary_term, "$options": "i"}},
        {"prescriptions": {"$regex": word_boundary_term, "$options": "i"}},
        {"timeline": {"$regex": word_boundary_term, "$options": "i"}},
        {"name": {"$regex": word_boundary_term, "$options": "i"}},
        {"note": {"$regex": word_boundary_term, "$options": "i"}},
        {"conversation": {"$regex": word_boundary_term, "$options": "i"}}
    ]}

async def rank_search_results(original_query: str, search_structure: Dict, patients: List[Dict]) -> List[Dict]:
    """Use Gemini to rank search results by clinical relevance"""
    try:
        if not patients:
            return []
        
        # For very few results, apply simple ranking
        if len(patients) <= 3:
            for i, patient in enumerate(patients):
                patient["relevance_score"] = max(95 - i * 5, 75)
                patient["relevance_reason"] = "Match to search criteria"
            return patients
        
        # Generate context summaries for Gemini
        patient_summaries = []
        for i, patient in enumerate(patients):
            # Create a comprehensive patient summary
            summary = f"""
Patient {i+1}:
- ID: {patient.get('patient_id', 'N/A')}
- Name: {patient.get('name', 'N/A')}
- Age: {patient.get('age', 'N/A')} Gender: {patient.get('gender', 'N/A')}
- Keywords: {str(patient.get('keywords', 'N/A'))[:200]}
- Medical Summary: {str(patient.get('summary', 'N/A'))[:300]}
- Prescriptions: {str(patient.get('prescriptions', 'N/A'))[:200]}
- Timeline Highlights: {str(patient.get('timeline', 'N/A'))[:200]}
"""
            patient_summaries.append(summary.strip())
        
        # Create detailed prompt for Gemini
        medical_context = search_structure.get("medical_context", "")
        required_terms = search_structure.get("required_terms", [])
        implied_conditions = search_structure.get("implied_conditions", [])
        
        prompt = f"""
You are a medical search expert. A healthcare provider searched for:
"{original_query}"

Medical interpretation: {medical_context}
Key clinical terms: {required_terms}
Implied medical conditions: {implied_conditions}

Evaluate these {len(patients)} patient records for relevance to the search query.
Focus on medical relevance rather than just keyword matching.

{chr(10).join(patient_summaries)}

Return a JSON array with ranking information for each patient:
[
  {{
    "patient_index": 0, 
    "relevance_score": 95,
    "reason": "Clear match to the queried medical condition"
  }},
  ...
]

Scoring criteria:
- Score 90-100: Perfect match to the medical condition/situation in the query
- Score 80-89: Strong match with most key elements present
- Score 70-79: Moderate match with some relevant elements
- Score 60-69: Partial match or related condition
- Score 40-59: Weak match, only peripheral relevance
- Score 0-39: Not relevant to the query

Include "patient_index" (0-based) in your response to identify each patient.
"""
        
        model = genai.GenerativeModel("models/gemini-2.0-flash")
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.2,
                response_mime_type="application/json",
                max_output_tokens=1500
            )
        )
        
        rankings = json.loads(response.text.strip())
        
        # Apply Gemini rankings to patients
        if len(rankings) == len(patients):
            for rank_info in rankings:
                patient_idx = rank_info.get("patient_index")
                if patient_idx is not None and 0 <= patient_idx < len(patients):
                    patients[patient_idx]["relevance_score"] = rank_info.get("relevance_score", 70)
                    patients[patient_idx]["relevance_reason"] = rank_info.get("reason", "Clinical match")
            
            # Sort by Gemini relevance score
            patients.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
        else:
            # If Gemini ranking doesn't match count, sort by natural order
            for i, patient in enumerate(patients):
                score = max(90 - i * 5, 40)
                patient["relevance_score"] = score
                patient["relevance_reason"] = "Ranked by clinical relevance"
        
        # Filter out low-relevance results (below 60 score)
        relevant_patients = [p for p in patients if p.get("relevance_score", 0) >= 60]
        
        # If all were filtered out but we had results, keep the top one
        if not relevant_patients and patients:
            relevant_patients = [patients[0]]
        
        return relevant_patients
        
    except Exception as e:
        print(f"[RANKING ERROR] {e}")
        import traceback
        traceback.print_exc()
        
        # Basic scoring if Gemini fails
        for i, patient in enumerate(patients):
            score = max(85 - i * 5, 40)
            patient["relevance_score"] = score
            patient["relevance_reason"] = "Basic relevance ranking"
        
        return patients[:5]