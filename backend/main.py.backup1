from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from dotenv import load_dotenv
import os

load_dotenv()

from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_pinecone import PineconeVectorStore

app = FastAPI(title="FitGenius API", version="4.0.0")

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
6. Use the conversation history to maintain context
   and give consistent, connected answers.
"""

    sections = []

    if "injury" in intents:
        sections.append("""
INJURY GUIDELINES:
- Read context carefully for safe exercises and modifications
- Clearly state what exercises to AVOID
- Suggest safe low-impact alternatives if in context
- Always recommend consulting a physician for persistent pain
- Mention RICE method if relevant
- If ANY injury-related content exists — USE IT
""")

    if "fitness" in intents:
        sections.append("""
FITNESS GUIDELINES:
- Provide specific exercise recommendations from context
- Include sets, reps, intensity, frequency if mentioned
- Reference heart rate zones if relevant
- Cite specific IFA page numbers
""")

    if "nutrition" in intents:
        sections.append("""
NUTRITION GUIDELINES:
- Only cite nutrition facts explicitly in context
- Do not invent specific foods, brands, or meal plans
- Reference calorie and protein data only if in context
""")

    combined = "\n".join(sections)
    intent_names = ", ".join(intents)

    return f"""You are a certified fitness advisor for a gym.
{strict_rule}
This question involves: {intent_names}
{combined}
Address ALL aspects of the member's question.
Always cite the source (IFA page number) for every fact.
Use the conversation history to give contextually aware answers."""

# ── Health check ───────────────────────────────────────
@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "FitGenius API v4 — memory + multi-intent RAG"
    }

# ── Chat request model with history ───────────────────
class HistoryMessage(BaseModel):
    role: str      # "user" or "assistant"
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
        # Include last user message for better context
        history_context = ""
        if request.history:
            last_messages = request.history[-4:]  # last 4 messages
            history_context = " ".join([
                msg.content for msg in last_messages
                if msg.role == "user"
            ])

        # Combine current message with recent history for search
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

        # Step 5 — Block if no content
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

        # Step 7 — Format conversation history for prompt
        history_text = ""
        if request.history and len(request.history) > 0:
            history_lines = []
            # Include last 6 messages (3 exchanges)
            recent_history = request.history[-6:]
            for msg in recent_history:
                role = "Member" if msg.role == "user" else "FitGenius"
                history_lines.append(f"{role}: {msg.content}")
            history_text = "\n".join(history_lines)

        # Step 8 — Build full prompt with memory
        system_prompt = build_system_prompt(intents)

        # Include history only if it exists
        history_section = ""
        if history_text:
            history_section = f"""
CONVERSATION HISTORY (use this for context):
{history_text}

"""

        full_prompt = f"""{system_prompt}

CONTEXT FROM IFA FITNESS KNOWLEDGE BASE:
{context}

{history_section}---
Current member question: {request.message}

Provide a complete answer using ONLY the IFA context above.
Use conversation history to give contextually aware answers.
If the member mentioned an injury or goal earlier — remember it.
Cite IFA page numbers for every fact."""

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
