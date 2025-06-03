from __future__ import annotations

import os
import traceback
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
MODEL = "models/gemini-2.0-flash"

# Input conversation and note
CONVERSATION = """Doctor: Good morning, sir. How are you feeling today?
Patient: I’m okay, doctor. Just a little bit worried about this bulge in my right groin.
Doctor: Can you tell me more about your chief complaint?
Patient: Yes, doctor. I’ve had this bulge in my right groin for about 6 weeks now. At first, it was very painful, but it’s been asymptomatic ever since. I’m not sure what caused it.
Doctor: Hmm, I see. Have you had any hernia repair in the past?
Patient: Yes, doctor. I had a hernia repair in 1977, but I don’t remember much about it. I don’t think they used any mesh for the implantation.
Doctor: Okay, let me take a look. Can you lie down on the bed, please?
Patient: Sure, doctor.
Doctor: (after physical examination) I found a 3 cm × 3 cm firm, nontender mass in your right groin just lateral to the pubic tubercle. I’d like to perform a computed tomography scan of your abdomen and pelvis to see what’s causing the mass.
Patient: Okay, doctor.
Doctor: (after the scan) The imaging showed that you have a right inguinal hernia and your appendix is inside the sac. Your laboratory test also showed a white blood cell count of 4.7 × 109/L.
Patient: Is that bad, doctor?
Doctor: No, it’s not necessarily bad. But we need to perform a surgical intervention to repair the hernia.
Patient: Okay, doctor. I’ll do it.
Doctor: (on the day of the surgery) We’ll make a classic oblique incision in your right groin using the anterior superior iliac spine and pubic tubercle as landmarks.
Patient: Okay, doctor.
Doctor: (after the surgery) The hernia was composed of an extremely hard and dense amount of omentum that had a chronic, scarred appearance. We tried to reduce the appendix back into the peritoneal cavity, but the adhesions prevented it. So, we had to make a relaxing incision in the typical transverse fashion in your right lower quadrant through the rectus sheath, and entered the peritoneum.
Patient: Is everything okay now, doctor?
Doctor: Yes, the surgery was successful. We’ll monitor you closely for the next few days. You may experience some discomfort or pain, but it should subside in a few days.
Patient: Thank you, doctor."""

NOTE = """An 88-year-old male presented in the outpatient surgical setting with a chief complaint of a right groin bulge that had been present for 6 weeks. He had sharp pain initially when he first developed the abnormality but had been asymptomatic ever since. He did not recall any inciting factors. He was concerned that a previously repaired right inguinal hernia had recurred from its original tissue repair in 1977. Details of the original right inguinal hernia repair were unknown to the patient, other than no implantation of mesh occurred. On physical examination, a 3 cm × 3 cm firm, nontender mass was palpable in the right groin just lateral to the pubic tubercle. A computed tomography scan of the abdomen and pelvis was performed to elucidate the cause of the mass in his groin (Figs. , , and ). The imaging was relevant for a right inguinal hernia with the appendix present within the sac. Preoperative laboratory testing revealed a white blood cell count of 4.7 × 109/L. The patient elected to proceed with surgical intervention for hernia repair.\nThe patient presented to the hospital setting for his elective right inguinal hernia repair. A classic oblique incision was made in the right groin using the anterior superior iliac spine and pubic tubercle as landmarks. The external oblique aponeurosis was opened and closed. The hernia was noted to be comprised of an extremely hard and dense amount of omentum that had a chronic, scarred appearance. The base of the appendix could be seen exiting the internal inguinal ring, but the densely adhered omentum prevented reduction of the appendix back into the peritoneal cavity. Initially, there was no indication to perform an appendectomy at the time of the procedure if the appendix could be successfully reduced into the abdominal cavity. However, the chronic appearing adhesions in the area prevented this step. In order to reduce the appendix at that point, a relaxing incision was then made in the typical transverse fashion in the right lower quadrant through the rectus sheath, and the peritoneum entered. The appendix was clearly visualized exiting the abdominal cavity into the inguinal defect. The appendix and its adhered omentum were then carefully reduced back into the abdominal cavity using intraperitoneal countertension without any rupture or spillage. Due to its densely adherent chronic inflammatory tissue, an incidental appendectomy was performed as there was significant tension on the cecum after placing the appendix back in its anatomical location. There was concern for the development of appendicitis post-operatively due to the manipulation performed during the procedure. The appendix was then stapled at its base using a standard gastrointestinal anastomosis stapler and passed off the field. The indirect hernia defect was very small and closed with a medium size lightweight mesh plug. The patient was discharged from the post-anesthesia care unit the same day as surgery and had no complications. No additional antibiotics were given other than a single prophylactic dose during the surgical case. At his 2-week follow-up, he had no recurrence of his hernia and was doing well. On pathologic examination, there was no evidence of appendiceal inflammation or appendicitis. The periappendiceal fat did exhibit some fat necrosis, however, supporting the chronic periappendiceal adhesive changes."""

# Prompt to extract timeline events
def timeline_prompt(note: str, conv: str) -> str:
    return (
        f"List all clinical events from the note and conversation, one per line. Club events where necessary, while there is no limit on the number of events, less is better, but it should be clear what happened.\n\n"
        f"Note: {note}\n"
        f"Conversation: {conv}"
    )

# Function to get timeline events
def get_timeline(note: str, conv: str) -> List[str]:
    try:
        print("[TIMELINE] Starting extraction...")
        print(f"[TIMELINE] Note (first 200 chars): {repr(note[:200])}...")
        print(f"[TIMELINE] Conversation (first 200 chars): {repr(conv[:200])}...")
        
        prompt = timeline_prompt(note, conv)
        print(f"[TIMELINE] Prompt length: {len(prompt)}")
        
        model = genai.GenerativeModel(MODEL)
        resp = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(temperature=0.0)
        )
        
        result = resp.text.strip()
        print(f"[TIMELINE] Raw result: {repr(result)}")
        
        # Process text: split by newlines, strip whitespace, filter empty lines
        timeline = [line.strip() for line in result.split('\n') if line.strip()]
        print(f"[TIMELINE] Processed timeline: {timeline}")
        
        print("[TIMELINE] Extraction complete.")
        return timeline
    except Exception as e:
        print(f"[TIMELINE ERROR] Exception: {e}")
        traceback.print_exc()
        return []

# Run the test
if __name__ == "__main__":
    print("Testing Gemini timeline extraction...")
    events = get_timeline(NOTE, CONVERSATION)
    print("\nFinal Timeline Events:")
    for i, event in enumerate(events, 1):
        print(f"{i}. {event}")