bashcd /workspaces/fitgenius/backend

cat > main.py << 'ENDOFFILE'
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from dotenv import load_dotenv
import os

load_dotenv()

from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_pinecone import PineconeVectorStore

app = FastAPI(title="FitGenius API", version="4.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Multi-intent detection ─────────────────────────────
def detect_intents(query: str) -> list:
    q = query.lower()
    intents = []

    if any(w in q for w in ["injury","pain","hurt","knee",
                             "shoulder","back","surgery",
                             "limitation","avoid","safe","sore"]):
        intents.append("injury")

    if any(w in q for w in ["eat","diet","calorie","protein",
                             "carb","fat","meal","nutrition",
                             "macro","food","drink","supplement",
                             "weight loss","lose weight"]):
        intents.append("nutrition")

    if any(w in q for w in ["exercise","workout","cardio","training",
                             "sets","reps","program","aerobic",
                             "strength","muscle","fitness","train",
                             "heart rate","warm up","cool down"]):
        intents.append("fitness")

    if not intents:
        intents.append("fitness")

    return intents

# ── System prompt ──────────────────────────────────────
def build_system_prompt(intents: list) -> str:

    strict_rule = """
CRITICAL RULES:
1. ONLY use information from the context provided below.
2. NEVER use your own training data or internet sources.
3. Every fact must be traceable to the context.
4. Do NOT invent food names, supplements, or numbers
   not explicitly in the context.
5. If context lacks relevant info — say so clearly.
6. Use conversation history SILENTLY — NEVER reference it
   explicitly. Do NOT say phrases like:
   "based on our previous conversation"
   "as mentioned earlier"
   "based on the previous conversation"
   "as you mentioned before"
   "from our earlier discussion"
   "you previously mentioned"
   Simply remember and USE the context naturally.
   Respond like a human trainer who naturally remembers
   what was discussed — without announcing that they remember.
   Just give the answer directly using what you know from
   the conversation so far.
"""

    sections = []

    if "injury" in intents:
        sections.append("""
INJURY GUIDELINES:
- Read context carefully for safe exercises and modifications
- Clearly state what exercises to AVOID
- Suggest safe low-impact alternatives if in context
- Always recommend consulting a physician for persistent pain
- Mention RICE method (Rest, Ice, Compression, Elevation) if relevant
- If ANY injury-related content exists — USE IT
- Be empathetic and helpful — don't just say "stop exercising"
  Give them alternatives they CAN do safely
""")

    if "fitness" in intents:
        sections.append("""
FITNESS GUIDELINES:
- Provide specific exercise recommendations from context
- Include sets, reps, intensity, frequency if mentioned
- Reference heart rate zones if relevant
- Cite specific IFA page numbers
- Be practical and specific — not generic
""")

    if "nutrition" in intents:
        sections.append("""
NUTRITION GUIDELINES:
- Only cite nutrition facts explicitly in context
- Do not invent specific foods, brands, or meal plans
- Reference calorie and protein data only if in context
- If context lacks specific food lists — say so honestly
""")

    combined = "\n".join(sections)
    intent_names = ", ".join(intents)

    return f"""You are FitGenius — a certified fitness advisor for a gym.
You speak naturally, warmly, and directly like a knowledgeable personal trainer.
{strict_rule}
This question involves: {intent_names}
{combined}
Address ALL aspects of the member's question.
Always cite the IFA source and page number for every fact.
Be conversational — not robotic. Get straight to the answer."""

# ── Health check ───────────────────────────────────────
@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "FitGenius API v4.1 — silent memory + multi-intent"
    }

# ── Request models ─────────────────────────────────────
class HistoryMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    history: Optional[List[HistoryMessage]] = []

# ── Chat endpoint ──────────────────────────────────────
@app.post("/chat")
def chat(request: ChatRequest):
    try:
        # Step 1 — Detect intents
        intents = detect_intents(request.message)

        # Step 2 — Set up vectorstore
        embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
        vectorstore = PineconeVectorStore(
            index_name=os.getenv("PINECONE_INDEX_NAME"),
            embedding=embeddings
        )

        # Step 3 — Build enriched search query using history
        history_context = ""
        if request.history:
            last_user_messages = [
                msg.content for msg in request.history[-4:]
                if msg.role == "user"
            ]
            history_context = " ".join(last_user_messages)

        search_query = f"{request.message} {history_context}".strip()

        # Step 4 — Search Pinecone for each intent
        all_docs = []
        seen_pages = set()

        for intent in intents:
            if intent == "injury":
                focused_query = f"injury safe exercise {search_query}"
            elif intent == "nutrition":
                focused_query = f"nutrition diet {search_query}"
            else:
                focused_query = f"exercise training {search_query}"

            docs = vectorstore.similarity_search(
                focused_query,
                k=3,
                filter={"category": "fitness"}
            )

            for doc in docs:
                page = doc.metadata.get("page", "")
                if page not in seen_pages:
                    seen_pages.add(page)
                    all_docs.append(doc)

        # Step 5 — Block if no content found
        if not all_docs:
            return {
                "response": "I don't have specific information on that "
                            "in my current knowledge base. Please consult "
                            "a certified fitness or nutrition professional.",
                "sources": [],
                "intents": intents,
                "status": "no_content"
            }

        # Step 6 — Build IFA context
        context = "\n\n---\n\n".join([
            doc.page_content for doc in all_docs
        ])

        if len(context.strip()) < 100:
            return {
                "response": "I don't have specific information on that "
                            "in my current knowledge base. Please consult "
                            "a certified fitness or nutrition professional.",
                "sources": [],
                "intents": intents,
                "status": "insufficient_content"
            }

        # Step 7 — Format conversation history
        history_text = ""
        if request.history and len(request.history) > 0:
            history_lines = []
            recent_history = request.history[-6:]
            for msg in recent_history:
                role = "Member" if msg.role == "user" else "FitGenius"
                history_lines.append(f"{role}: {msg.content}")
            history_text = "\n".join(history_lines)

        # Step 8 — Build full prompt
        system_prompt = build_system_prompt(intents)

        history_section = ""
        if history_text:
            history_section = f"""
CONVERSATION SO FAR (use silently for context — do not reference explicitly):
{history_text}

"""

        full_prompt = f"""{system_prompt}

CONTEXT FROM IFA FITNESS KNOWLEDGE BASE:
{context}

{history_section}---
Member: {request.message}

FitGenius:"""

        # Step 9 — Call GPT-4o
        llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0,
            model_kwargs={"seed": 42}
        )
        result = llm.invoke(full_prompt)

        # Step 10 — Extract citations
        sources = []
        for doc in all_docs:
            src = doc.metadata.get("source", "Unknown")
            page = doc.metadata.get("page", "")
            citation = f"{src}" + (f", p.{int(page)}" if page else "")
            if citation not in sources:
                sources.append(citation)

        return {
            "response": result.content,
            "sources": sources,
            "intents": intents,
            "status": "success"
        }

    except Exception as e:
        return {
            "response": f"Error: {str(e)}",
            "sources": [],
            "intents": [],
            "status": "error"
        }
