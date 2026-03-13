"""
============================================================
RAG Tools (Retrieval-Augmented Generation)
============================================================
This module sets up the document intelligence pipeline for
accounting policy documents:
  1. Loads accounting policies, SOX guides, and close procedures
  2. Splits them into chunks for embedding
  3. Stores embeddings in ChromaDB
  4. Provides search functions agents can call

The agents use this to answer questions like:
  "What is the revenue recognition policy?"
  "What are the SOX requirements for journal entry approval?"
  "What is the reconciliation procedure for control accounts?"

Architecture:
  Documents -> LangChain TextSplitter -> OpenAI Embeddings -> ChromaDB

  Query -> Embedding -> ChromaDB Similarity Search -> Top-K Results

Same RAG pattern as AgenticFacilitiesMaintenance, applied to
accounting and compliance documents instead of maintenance manuals.
============================================================
"""

import os
from pathlib import Path
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma


# ============================================================
# CONFIGURATION
# ============================================================

# Where the accounting policy documents live
DOCS_DIR = str(Path(__file__).parent.parent / "docs")

# Where ChromaDB stores the vector index
CHROMA_DIR = str(Path(__file__).parent.parent / "data" / "chroma_db")

# Embedding model (OpenAI Ada-002 for cost-effective, high-quality embeddings)
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-ada-002")

# Chunking parameters:
# - chunk_size=1000: Enough context per chunk for accounting policies,
#   which often have multi-paragraph sections that should stay together.
# - chunk_overlap=200: Prevents losing context at chunk boundaries,
#   important for procedures that reference earlier steps.
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200

# Number of results to return from similarity search.
# 4 is a good balance between relevance and context window usage.
TOP_K = 4


# ============================================================
# VECTOR STORE SETUP
# ============================================================

# Module-level cache to avoid rebuilding the index on every query.
# The index is built once on first access, then reused.
_vector_store = None


def _get_or_create_vector_store() -> Chroma:
    """
    Load the vector store from disk, or create it from documents.

    Workflow:
      1. Check if a ChromaDB index already exists on disk
      2. If yes, load it (fast startup, no OpenAI calls)
      3. If no, read all accounting documents, chunk them,
         embed them via OpenAI, and create a new index

    The index is cached in the module-level _vector_store variable
    so subsequent calls reuse it without rebuilding.

    Returns:
        Chroma vector store ready for similarity search
    """
    global _vector_store

    if _vector_store is not None:
        return _vector_store

    embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)

    # Check if index already exists on disk (avoids re-embedding)
    if os.path.exists(CHROMA_DIR) and os.listdir(CHROMA_DIR):
        print("Loading existing accounting docs vector store from disk...")
        _vector_store = Chroma(
            persist_directory=CHROMA_DIR,
            embedding_function=embeddings,
            collection_name="accounting_docs",
        )
        return _vector_store

    # ---- Build the index from scratch ----
    print(f"Building vector store from documents in {DOCS_DIR}...")

    # Step 1: Load all markdown documents.
    # DirectoryLoader recursively finds all .md files in the docs directory.
    loader = DirectoryLoader(
        DOCS_DIR,
        glob="**/*.md",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
    )
    documents = loader.load()
    print(f"  Loaded {len(documents)} documents")

    # Step 2: Split documents into chunks.
    # RecursiveCharacterTextSplitter tries natural boundaries first
    # (paragraphs, then sentences, then words) before falling back
    # to raw character count. This preserves the structure of
    # accounting policies, which are organized by section.
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", " ", ""],
    )
    chunks = text_splitter.split_documents(documents)
    print(f"  Split into {len(chunks)} chunks")

    # Step 3: Create embeddings and store in ChromaDB.
    # Each chunk is converted to a 1536-dimension vector (Ada-002).
    # ChromaDB stores these vectors for fast similarity search.
    _vector_store = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=CHROMA_DIR,
        collection_name="accounting_docs",
    )
    print(f"  Vector store created and persisted to {CHROMA_DIR}")

    return _vector_store


def search_accounting_docs(query: str) -> str:
    """
    Search accounting documentation using semantic similarity.

    This is the main RAG function. Agents call it to find relevant
    policies, procedures, and compliance requirements.

    Semantic search means the query "how do we handle revenue at
    month end" will match documents about "revenue recognition
    cutoff procedures" even though the wording is different.

    Args:
        query: Natural language question about accounting policies,
               SOX compliance, or close procedures

    Returns:
        Relevant document excerpts with source attribution
    """
    try:
        vector_store = _get_or_create_vector_store()

        # Perform similarity search.
        # Returns the TOP_K most similar document chunks with distance scores.
        results = vector_store.similarity_search_with_score(query, k=TOP_K)

        if not results:
            return "No relevant accounting documentation found for this query."

        # Format results for the agent.
        # Include source file and relevance indicator so the agent
        # can assess information quality and cite its sources.
        output = f"ACCOUNTING DOCUMENTATION SEARCH RESULTS (Query: '{query}'):\n\n"

        for i, (doc, score) in enumerate(results, 1):
            source = Path(doc.metadata.get("source", "Unknown")).name
            # Score is distance (lower = more similar in ChromaDB)
            relevance = "High" if score < 0.5 else "Medium" if score < 1.0 else "Low"

            output += f"--- Result {i} ({relevance} relevance, source: {source}) ---\n"
            output += doc.page_content.strip()
            output += "\n\n"

        return output.strip()

    except Exception as e:
        return f"Error searching accounting docs: {str(e)}. Ensure OPENAI_API_KEY is set."


def get_document_list() -> str:
    """
    List all available accounting documents.

    Useful for agents to know what documentation exists before
    deciding which queries to run.
    """
    docs_path = Path(DOCS_DIR)
    if not docs_path.exists():
        return "No documentation directory found."

    files = list(docs_path.glob("**/*.md"))
    if not files:
        return "No accounting documents found."

    result = "AVAILABLE ACCOUNTING DOCUMENTS:\n"
    for f in files:
        size_kb = f.stat().st_size / 1024
        result += f"  - {f.name} ({size_kb:.1f} KB)\n"

    return result.strip()
