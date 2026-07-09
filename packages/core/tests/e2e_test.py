"""End-to-end pipeline test — ingest PDF, ask answerable + unanswerable questions."""

import asyncio

from ragcore.service import service


def main() -> None:
    # 1. Ingest the demo PDF
    print("=== INGESTING PDF ===")
    result = service.ingest("tests/fixtures/langchain_demo.pdf")
    print(f"Ingest: {result}")

    # 2. Ask an answerable question
    print("\n=== ANSWERABLE QUESTION ===")
    answer = asyncio.run(service.ask("What is this document about?"))
    print(f"Status: {answer.status}")
    print(f"Answer: {answer.answer}")
    print(f"Citations: {len(answer.citations)}")
    for c in answer.citations:
        print(f"  page {c.page}: {c.excerpt[:80]}...")
    print(f"Cost: {answer.cost.prompt_tokens}+{answer.cost.completion_tokens} tokens")
    print(f"Latency: {answer.latency_ms}ms")
    print(f"Config: {answer.config}")

    # 3. Ask an unanswerable question (with small delay for rate limit)
    import time

    time.sleep(2)
    print("\n=== UNANSWERABLE QUESTION ===")
    answer2 = asyncio.run(
        service.ask("What is the VAT rate for electronics in Brazil?")
    )
    print(f"Status: {answer2.status}")
    print(f"Answer: {answer2.answer}")
    print(f"Citations: {len(answer2.citations)}")

    print("\n=== E2E TEST COMPLETE ===")


if __name__ == "__main__":
    main()
