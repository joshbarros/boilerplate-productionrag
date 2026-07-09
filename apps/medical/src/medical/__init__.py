"""Medical RAG niche — the first non-demo application of production-rag.

This app composes the shared `production-rag-core` engine with
domain-specific:

- Data sources: PubMed Central (open-access biomedical literature)
- Domain prompt: physician's clinical reference tone
- Golden set: 8 hand-written medical Q&A pairs for the eval pipeline

Run: cd apps/medical && uv run uvicorn medical.app:app --port 8810
"""
