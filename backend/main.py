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

    # This rule is added to EVERY prompt — no exceptions
    strict_rule = """
CRITICAL RULES — YOU MUST FOLLOW THESE EXACTLY:
1. You ONLY use information from the context provided below.
2. You NEVER use your own training data, general knowledge, or internet sources.
3. You NEVER search Google or any external source.
4. If the context does not contain enough information to answer the question,
   you MUST respond with exactly:
   "I don't have specific information on that in my current knowledge base.
   Please consult a certified fitness or nutrition professional."
5. Do NOT make up food names, supplement brands, specific studies, or numbers
   that are not explicitly stated in the context.
6. Every fact you state must be traceable to the context provided.
"""

    if intent == "injury":
        return f"""{strict_rule}
You are a certified fitness advisor.
The member has mentioned an injury or physical limitation.
ALWAYS prioritize safety before recommending any exercise.
If the condition seems medical, recommend they consult a physician.
Only use the context provided — never fabricate information."""

    elif intent == "nutrition":
        return f"""{strict_rule}
You are a certified fitness and nutrition advisor.
Answer nutrition questions based ONLY on the context provided below.
Give specific, practical advice grounded only in the retrieved content.
If the context does not mention specific foods, brands, or supplements —
do NOT invent them. Say you don't have that information instead."""

    else:
        return f"""{strict_rule}
You are a certified fitness advisor for a gym.
Answer the member's question based ONLY on the context provided below.
Be specific and practical. Always cite the source material.
If the context does not contain relevant information, say clearly:
"I don't have specific information on that in my current knowledge base.
Please consult a certified fitness professional." """

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

        # Step 2 — Retrieve chunks from Pinecone ONLY
        embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
        vectorstore = PineconeVectorStore(
            index_name=os.getenv("PINECONE_INDEX_NAME"),
            embedding=embeddings
        )

        search_filter = {"category": "nutrition"} if intent == "nutrition" \
                        else {"category": "fitness"}

        docs = vectorstore.similarity_search(
            request.message,
            k=5,
            filter=search_filter
        )

        # Step 3 — If no relevant chunks found — block immediately
        if not docs:
            return {
                "response": "I don't have specific information on that "
                            "in my current knowledge base. Please consult "
                            "a certified fitness or nutrition professional.",
                "sources": [],
                "intent": intent,
                "status": "no_content"
            }

        # Step 4 — Build context from retrieved chunks ONLY
        context = "\n\n---\n\n".join([doc.page_content for doc in docs])

        # Step 5 — Check if context is actually relevant
        # If chunks are too short or clearly irrelevant, block
        total_context_length = len(context.strip())
        if total_context_length < 100:
            return {
                "response": "I don't have specific information on that "
                            "in my current knowledge base. Please consult "
                            "a certified fitness or nutrition professional.",
                "sources": [],
                "intent": intent,
                "status": "insufficient_content"
            }

        # Step 6 — Build strict dynamic prompt
        system_prompt = build_system_prompt(intent)
        full_prompt = f"""{system_prompt}

CONTEXT FROM IFA FITNESS KNOWLEDGE BASE ONLY:
{context}

---
Member question: {request.message}

Answer using ONLY the context above. 
If the context does not directly address this question, say so:"""

        # Step 7 — Call GPT-4o with strict instructions
        llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0,        # 0 = most factual, least creative
            model_kwargs={
                "seed": 42        # consistent responses
            }
        )
        result = llm.invoke(full_prompt)

        # Step 8 — Extract citations
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
