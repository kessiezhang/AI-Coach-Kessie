#!/usr/bin/env python3
"""Test the RAG.
  python test_rag.py          - full test (ingest + query)
  python test_rag.py ingest   - ingest only
  python test_rag.py query "your question"  - query only (run ingest first)
"""
import os
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from dotenv import load_dotenv
load_dotenv()

DS_ID = os.getenv("NOTION_DATA_SOURCE_ID", "5bcc97fa-499e-4e61-9885-32bb5e72edda")


def do_ingest():
    from rag import ingest
    print("Ingesting from Notion...")
    n = ingest(data_source_id=DS_ID)
    print(f"Done. Loaded {n} documents.")


def do_query(question: str, debug: bool = False):
    from rag import query
    print(query(question, debug=debug))


def main():
    args = sys.argv[1:]
    if args and args[0] == "ingest":
        do_ingest()
    elif args and args[0] == "query" and len(args) > 1:
        do_query(" ".join(args[1:]), debug="--debug" in args)
    else:
        do_ingest()
        print("\n--- Testing queries ---\n")
        for q in [
            "What coaching services are offered?",
            "How can I book a discovery session?",
        ]:
            print(f"Q: {q}")
            do_query(q)
            print()


if __name__ == "__main__":
    main()
