from dotenv import load_dotenv
import os

load_dotenv('/workspaces/fitgenius/backend/.env')

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore

def ingest_pdf(filepath, source_name, category):
    print(f"\n{'='*50}")
    print(f"Processing: {source_name}")
    print(f"{'='*50}")

    # Step 1 — Load PDF
    print("\nStep 1: Loading PDF...")
    loader = PyPDFLoader(filepath)
    pages = loader.load()
    print(f"  Loaded {len(pages)} pages")

    # Step 2 — Chunk
    print("\nStep 2: Chunking...")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=100,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    chunks = splitter.split_documents(pages)
    print(f"  Created {len(chunks)} chunks")

    # Step 3 — Add metadata
    print("\nStep 3: Adding metadata...")
    for chunk in chunks:
        chunk.metadata["source"] = source_name
        chunk.metadata["category"] = category
        chunk.metadata["file"] = os.path.basename(filepath)
    print(f"  Metadata added to {len(chunks)} chunks")

    # Step 4 — Embed and upload to Pinecone
    print("\nStep 4: Embedding and uploading to Pinecone...")
    print("  This takes 2-5 minutes — please wait...")
    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")
    PineconeVectorStore.from_documents(
        documents=chunks,
        embedding=embeddings,
        index_name=os.getenv("PINECONE_INDEX_NAME"),
    )
    print(f"  ✅ Successfully uploaded {len(chunks)} chunks to Pinecone!")
    return len(chunks)

if __name__ == "__main__":
    total = 0

    # IFA Fitness ABCs
    if os.path.exists("ifa_fitness_abcs.pdf"):
        total += ingest_pdf(
            filepath="ifa_fitness_abcs.pdf",
            source_name="IFA Fitness ABCs",
            category="fitness"
        )
    else:
        print("❌ ifa_fitness_abcs.pdf not found in ingestion folder")

    # WHO Physical Activity (optional)
    if os.path.exists("who_physical_activity_2020.pdf"):
        total += ingest_pdf(
            filepath="who_physical_activity_2020.pdf",
            source_name="WHO Physical Activity Guidelines 2020",
            category="fitness"
        )
    else:
        print("⚠  who_physical_activity_2020.pdf not found — skipping")

    print(f"\n{'='*50}")
    print(f"✅ INGESTION COMPLETE")
    print(f"Total chunks uploaded to Pinecone: {total}")
    print(f"{'='*50}")
    print(f"\nNext: verify in Pinecone dashboard → Database → Indexes → fitgenius")
    print(f"You should see {total} vectors stored.")
