# LinkedIn post — content bank #73

**Title:** Everyone has a RAG demo; almost nobody publishes eval numbers.

---

Shipped production-rag v0.1.0 — a self-hosted, citation-grounded document QA system.

**The thing I kept getting asked:** "how do I know the answers are actually grounded? how do I know the model isn't hallucinating?"

The honest answer was always: "you run the same 8 questions and check." So I built that into the repo.

**What it does:**
- Answers questions from indexed PDFs with verbatim citations
- **Refuses to answer** when it can't cite a real passage (no hallucination)
- HTTP + MCP surfaces over a shared service layer
- Budget enforcement: $5/day, $0.10/query caps
- Docling OCR fallback for scanned PDFs
- 8-case golden eval suite, runnable any time

**The eval result (gpt-4o-mini via OpenRouter):**
- 75% pass rate (6/8 questions answered correctly with valid citations)
- 100% refusal rate (2/2 out-of-scope questions correctly refused)
- 2.9s avg latency
- $0.00 cost (free OpenRouter credits)

**The 2 failures aren't bugs** — they're bullet-list questions where the model paraphrases instead of quoting. The cite-or-refuse guard downgrades them to `not_found` because the excerpts don't verify. That's *correct* behavior. I'd rather refuse than fabricate.

**What it's not:** a 500k-chunk scale test. A pgvector backend. A reranker. A Qdrant benchmark. All deferred, all documented in `docs/limits.md`.

**The thing I want to push back on:** every RAG demo looks great on a single document. The hard part is making it **admit when it doesn't know** and **proving it does the right thing on demand**. That's what the eval suite is for. That's what gets you trust in production.

GitHub: https://github.com/joshbarros/boilerplate-productionrag
Release: https://github.com/joshbarros/boilerplate-productionrag/releases/tag/v0.1.0
Eval results: https://github.com/joshbarros/boilerplate-productionrag/blob/v0.1.0/docs/eval_results_v0.1.0.md
Limits: https://github.com/joshbarros/boilerplate-productionrag/blob/v0.1.0/docs/limits.md

#RAG #LLM #MLOps #OpenSource
