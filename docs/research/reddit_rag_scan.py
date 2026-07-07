#!/usr/bin/env python3
"""What RAG practitioners are discussing/complaining about — feeds the spec.
Uses the RedditClient in ~/BUSINESS/TOOLS. Output: reddit-rag-scan-2026-07.md"""
import sys, re
from collections import Counter
sys.path.insert(0, "/Users/josuebarros1995/BUSINESS/TOOLS")
from reddit_client import RedditClient

SEARCHES = [
    ("RAG production", "rag"), ("RAG chunking", "rag"), ("RAG evaluation", "rag"),
    ("RAG production", "LLMDevs"), ("RAG failing", "LLMDevs"),
    ("pgvector", "rag"), ("qdrant", "rag"), ("hybrid search", "rag"),
    ("RAG pipeline production", "LocalLLaMA"), ("RAG evaluation", "MLOps"),
    ("document parsing PDF", "rag"), ("reranking", "rag"),
]
PAIN = {
    "chunking": r"chunk", "evaluation/evals": r"\beval|golden|benchmark|faithfulness",
    "hallucination": r"hallucin", "PDF/parsing pain": r"pdf|ocr|parsing|table",
    "retrieval quality": r"retriev|recall|relevan", "hybrid/BM25": r"hybrid|bm25|keyword",
    "reranking": r"rerank", "pgvector": r"pgvector", "qdrant": r"qdrant",
    "chroma": r"chroma", "pinecone": r"pinecone", "weaviate": r"weaviate",
    "cost": r"\bcost|expensive|pricing|token budget", "latency": r"latency|slow",
    "scale": r"\bscale|million", "metadata": r"metadata", "graphrag": r"graph\s?rag",
    "agentic rag": r"agentic|agent", "context engineering": r"context engineer",
    "self-host/local": r"self-?host|on-?prem|local|ollama|vllm", "security/PII": r"pii|security|compliance|hipaa|gdpr",
    "langchain (neg or pos)": r"langchain", "citations": r"citation|source attribution|grounding",
}
r = RedditClient()
seen, themes, hi = set(), Counter(), []
for q, sub in SEARCHES:
    try:
        posts = r.search(q, subreddit=sub, sort="top", time_filter="month", limit=25)
    except Exception as e:
        print(f"!! {q}: {e}"); continue
    for p in posts:
        d = p.get("data", p)
        if d.get("id") in seen: continue
        seen.add(d.get("id"))
        txt = (d.get("title","") + " " + (d.get("selftext") or "")).lower()
        for name, rx in PAIN.items():
            if re.search(rx, txt): themes[name] += 1
        if d.get("score", 0) >= 20:
            hi.append((d.get("score"), d.get("subreddit"), d.get("title","")[:120]))
hi.sort(reverse=True)
out = [f"# Reddit RAG practitioner scan — 2026-07-07 (top/month, n={len(seen)} posts)", "",
       "## Theme frequency (posts mentioning)"]
for k, v in themes.most_common(): out.append(f"- {k}: {v}")
out.append("\n## High-signal threads (score ≥ 20)")
for s, sub, t in hi[:35]: out.append(f"- [{s}▲ r/{sub}] {t}")
open("/Users/josuebarros1995/AI-ENGINEERING/production-rag/docs/research/reddit-rag-scan-2026-07.md","w").write("\n".join(out))
print("\n".join(out[:45]))
