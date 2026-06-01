from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()

from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_pinecone import PineconeVectorStore

app = FastAPI(title="FitGenius API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def detect_intent(query: str) -> str:
    q = query.lower()
    if any(w in q for w in ["eat","diet","calorie","protein",
                             "carb","fat","meal","nutrition","macro",
                             "food","drink","water","supplement"]):
        return "nutrition"
    elif any(w in q for w in ["injury","pain","hurt","knee","shoulder",
                               "back","surgery","limitation","avoid","safe"]):
        return "injury"
    else:
        return "fitness"

def build_system_prompt(intent: str) -> str:

    strict_rule = """
CRITICAL RULES:
1. ONLY use information from the context provided below.
2. NEVER use your own training data or internet sources.
3. Every fact must be traceable to the context.
4. Do NOT invent food names, supplements, or numbers not in the context.
"""

    if intent == "injury":
        return f"""{strict_rule}
You are a certified fitness advisor helping a gym member with an injury.

INSTRUCTIONS:
- Read the context carefully for relevant exercises, precautions, or modifications
- If the context mentions safe exercises or alternatives — share them specifically
- If the context mentions what to AVOID — share that clearly
- ALWAYS recommend consulting a physician for serious or persistent pain
- Prioritize safety above all else
- Mention RICE method (Rest, Ice, Compression, Elevation) if relevant

Only say you lack information if the context is completely unrelated to
the injury mentioned. If ANY relevant content exists — use it."""

    elif intent == "nutrition":
        return f"""{strict_rule}
You are a certified fitness and nutrition advisor.
Answer ONLY based on the context provided.
Do NOT invent specific foods, brands, or supplements not mentioned in context.
If context lacks specific food lists — say so and share what IS in the context."""

    else:
        return f"""{strict_rule}
You are a certified fitness advisor for a gym.
Answer ONLY based on the context provided below.
Be specific and cite the source material.
If context does not contain relevant information, say:
"I don't have specific information on that. Please consult a certified professional." """

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "FitGenius API v2 — RAG only, no external sources"
    }

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"

@app.post("/chat")
def chat(request: ChatRequest):
    try:
        # Step 1 — Detect intent
        intent = detect_intent(request.message)

        # Step 2 — Retrieve chunks from Pinecone
        embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
        vectorstore = PineconeVectorStore(
            index_name=os.getenv("PINECONE_INDEX_NAME"),
            embedding=embeddings
        )

        # For injury — search fitness content
        # For nutrition — search nutrition content
        # For general — search fitness content
        if intent == "nutrition":
            search_filter = {"category": "nutrition"}
        else:
            search_filter = {"category": "fitness"}

        docs = vectorstore.similarity_search(
            request.message,
            k=5,
            filter=search_filter
        )

        # Step 3 — Block if no content found
        if not docs:
            return {
                "response": "I don't have specific information on that "
                            "in my current knowledge base. Please consult "
                            "a certified fitness or nutrition professional.",
                "sources": [],
                "intent": intent,
                "status": "no_content"
            }

        # Step 4 — Build context
        context = "\n\n---\n\n".join([doc.page_content for doc in docs])

        if len(context.strip()) < 100:
            return {
                "response": "I don't have specific information on that "
                            "in my current knowledge base. Please consult "
                            "a certified fitness or nutrition professional.",
                "sources": [],
                "intent": intent,
                "status": "insufficient_content"
            }

        # Step 5 — Build dynamic prompt
        system_prompt = build_system_prompt(intent)
        full_prompt = f"""{system_prompt}

CONTEXT FROM IFA FITNESS KNOWLEDGE BASE:
{context}

---
Member question: {request.message}

Provide a helpful, specific answer using ONLY the context above.
If the context contains relevant information — USE IT.
Cite specific sections or page references where possible."""

        # Step 6 — Call GPT-4o
        llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0,
            model_kwargs={"seed": 42}
        )
        result = llm.invoke(full_prompt)

        # Step 7 — Extract citations
        sources = []
        for doc in docs:
            src = doc.metadata.get("source", "Unknown")
            page = doc.metadata.get("page", "")
            citation = f"{src}" + (f", p.{int(page)}" if page else "")
            if citation not in sources:
                sources.append(citation)

        return {
            "response": result.content,
            "sources": sources,
            "intent": intent,
            "status": "success"
        }

    except Exception as e:
        return {
            "response": f"Error: {str(e)}",
            "sources": [],
            "intent": "unknown",
            "status": "error"
        }
