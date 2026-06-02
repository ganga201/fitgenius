from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from dotenv import load_dotenv
import os
import httpx

load_dotenv()

from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_pinecone import PineconeVectorStore

app = FastAPI(title="FitGenius API", version="5.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Redis quota via Upstash REST API ───────────────────
QUOTA_LIMIT = 30
QUOTA_WINDOW_SECONDS = 15 * 24 * 60 * 60  # 15 days

async def get_quota_remaining(user_id: str) -> int:
    url = f"{os.getenv('UPSTASH_REDIS_REST_URL')}/get/quota:{user_id}"
    headers = {"Authorization": f"Bearer {os.getenv('UPSTASH_REDIS_REST_TOKEN')}"}
    async with httpx.AsyncClient() as client:
        res = await client.get(url, headers=headers)
        data = res.json()
        if data.get("result") is None:
            return QUOTA_LIMIT
        return max(0, int(data["result"]))

async def decrement_quota(user_id: str) -> int:
    redis_url = os.getenv('UPSTASH_REDIS_REST_URL')
    token = os.getenv('UPSTASH_REDIS_REST_TOKEN')
    headers = {"Authorization": f"Bearer {token}"}
    key = f"quota:{user_id}"

    async with httpx.AsyncClient() as client:
        # Check if key exists
        check = await client.get(f"{redis_url}/exists/{key}", headers=headers)
        exists = check.json().get("result", 0)

        if not exists:
            # Set initial quota with TTL
            await client.get(
                f"{redis_url}/set/{key}/{QUOTA_LIMIT}",
                headers=headers
            )
            await client.get(
                f"{redis_url}/expire/{key}/{QUOTA_WINDOW_SECONDS}",
                headers=headers
            )

        # Get current value
        get_res = await client.get(f"{redis_url}/get/{key}", headers=headers)
        current = int(get_res.json().get("result") or QUOTA_LIMIT)

        if current <= 0:
            return 0

        # Decrement
        decr_res = await client.get(f"{redis_url}/decr/{key}", headers=headers)
        new_val = int(decr_res.json().get("result") or 0)
        return max(0, new_val)

# ── Intent detection ───────────────────────────────────
def detect_intents(query: str) -> list:
    q = query.lower()
    intents = []
    if any(w in q for w in ["injury","pain","hurt","knee","shoulder",
                             "back","surgery","limitation","avoid","safe","sore"]):
        intents.append("injury")
    if any(w in q for w in ["eat","diet","calorie","protein","carb","fat",
                             "meal","nutrition","macro","food","drink",
                             "supplement","weight loss","lose weight"]):
        intents.append("nutrition")
    if any(w in q for w in ["exercise","workout","cardio","training","sets",
                             "reps","program","aerobic","strength","muscle",
                             "fitness","train","heart rate","warm up","cool down"]):
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
4. Do NOT invent food names, supplements, or numbers not in context.
5. If context lacks relevant info — say so clearly.
6. Use conversation history SILENTLY — NEVER say phrases like
   "based on our previous conversation", "as mentioned earlier",
   "as you mentioned before", "from our earlier discussion".
   Simply USE the context naturally like a human trainer would.
"""
    sections = []
    if "injury" in intents:
        sections.append("""
INJURY GUIDELINES:
- Read context for safe exercises and modifications
- State clearly what to AVOID
- Suggest safe low-impact alternatives from context
- Always recommend physician for persistent pain
- Mention RICE method if relevant
- Be empathetic — give alternatives they CAN do
""")
    if "fitness" in intents:
        sections.append("""
FITNESS GUIDELINES:
- Specific exercise recommendations from context
- Include sets, reps, intensity, frequency if mentioned
- Reference heart rate zones if relevant
- Cite IFA page numbers
""")
    if "nutrition" in intents:
        sections.append("""
NUTRITION GUIDELINES:
- Only cite nutrition facts explicitly in context
- Do not invent specific foods or meal plans
- Reference calorie/protein data only if in context
""")
    combined = "\n".join(sections)
    intent_names = ", ".join(intents)
    return f"""You are FitGenius — a certified fitness advisor for a gym.
You speak naturally, warmly, and directly like a knowledgeable personal trainer.
{strict_rule}
This question involves: {intent_names}
{combined}
Address ALL aspects of the question. Cite IFA page numbers for every fact.
Be conversational — get straight to the answer."""

# ── Health check ───────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "service": "FitGenius API v5 — Clerk + Redis quota"}

# ── Quota check endpoint ───────────────────────────────
@app.get("/quota/{user_id}")
async def get_quota(user_id: str):
    remaining = await get_quota_remaining(user_id)
    return {"remaining": remaining, "limit": QUOTA_LIMIT}

# ── Request models ─────────────────────────────────────
class HistoryMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    user_id: str = "anonymous"
    session_id: str = "default"
    history: Optional[List[HistoryMessage]] = []

# ── Chat endpoint ──────────────────────────────────────
@app.post("/chat")
async def chat(request: ChatRequest):
    try:
        # Step 1 — Check quota BEFORE doing anything
        remaining = await get_quota_remaining(request.user_id)
        if remaining <= 0:
            raise HTTPException(
                status_code=429,
                detail="Quota exhausted. Please contact your gym."
            )

        # Step 2 — Detect intents
        intents = detect_intents(request.message)

        # Step 3 — Set up vectorstore
        embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
        vectorstore = PineconeVectorStore(
            index_name=os.getenv("PINECONE_INDEX_NAME"),
            embedding=embeddings
        )

        # Step 4 — Build enriched search query
        history_context = ""
        if request.history:
            history_context = " ".join([
                msg.content for msg in request.history[-4:]
                if msg.role == "user"
            ])
        search_query = f"{request.message} {history_context}".strip()

        # Step 5 — Search Pinecone per intent
        all_docs = []
        seen_pages = set()
        for intent in intents:
            if intent == "injury":
                focused = f"injury safe exercise {search_query}"
            elif intent == "nutrition":
                focused = f"nutrition diet {search_query}"
            else:
                focused = f"exercise training {search_query}"

            docs = vectorstore.similarity_search(
                focused, k=3, filter={"category": "fitness"}
            )
            for doc in docs:
                page = doc.metadata.get("page", "")
                if page not in seen_pages:
                    seen_pages.add(page)
                    all_docs.append(doc)

        # Step 6 — Block if no content
        if not all_docs or len("\n".join([d.page_content for d in all_docs]).strip()) < 100:
            return {
                "response": "I don't have specific information on that. "
                            "Please consult a certified fitness professional.",
                "sources": [], "intents": intents,
                "quota_remaining": remaining,
                "status": "no_content"
            }

        # Step 7 — Build context and history
        context = "\n\n---\n\n".join([d.page_content for d in all_docs])
        history_text = ""
        if request.history:
            lines = []
            for msg in request.history[-6:]:
                role = "Member" if msg.role == "user" else "FitGenius"
                lines.append(f"{role}: {msg.content}")
            history_text = "\n".join(lines)

        history_section = ""
        if history_text:
            history_section = f"""
CONVERSATION SO FAR (use silently — do not reference explicitly):
{history_text}

"""
        # Step 8 — Build and send prompt
        system_prompt = build_system_prompt(intents)
        full_prompt = f"""{system_prompt}

CONTEXT FROM IFA FITNESS KNOWLEDGE BASE:
{context}

{history_section}---
Member: {request.message}

FitGenius:"""

        llm = ChatOpenAI(model="gpt-4o", temperature=0, model_kwargs={"seed": 42})
        result = llm.invoke(full_prompt)

        # Step 9 — Decrement quota AFTER successful response
        new_remaining = await decrement_quota(request.user_id)

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
            "quota_remaining": new_remaining,
            "status": "success"
        }

    except HTTPException:
        raise
    except Exception as e:
        return {
            "response": f"Error: {str(e)}",
            "sources": [], "intents": [],
            "quota_remaining": 0,
            "status": "error"
        }
