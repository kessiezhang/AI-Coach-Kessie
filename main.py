#!/usr/bin/env python3
"""Notion RAG CLI: ingest and query."""
import os
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
import argparse
import os
import sys
from pathlib import Path
from typing import List

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))
from rag import DEFAULT_PERSIST_DIR, ingest, query


def _get_page_ids() -> List[str]:
    raw = os.getenv("NOTION_PAGE_IDS", "")
    return [p.strip() for p in raw.split(",") if p.strip()]


def cmd_ingest(args):
    page_ids = args.page_ids or _get_page_ids()
    if args.page_ids:
        page_ids = [p.strip() for p in args.page_ids.split(",") if p.strip()]
    database_id = args.database_id or os.getenv("NOTION_DATABASE_ID")
    data_source_id = args.data_source_id or os.getenv("NOTION_DATA_SOURCE_ID")

    if not page_ids and not database_id and not data_source_id:
        print("Error: Provide --page-ids, --database-id, or --data-source-id")
        sys.exit(1)
    if not os.getenv("NOTION_API_KEY"):
        print("Error: NOTION_API_KEY required")
        sys.exit(1)
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY required")
        sys.exit(1)

    try:
        n = ingest(
            page_ids=page_ids or None,
            database_id=database_id,
            data_source_id=data_source_id,
            persist_directory=args.output or DEFAULT_PERSIST_DIR,
        )
        print(f"Ingested {n} document(s).")
    except Exception as e:
        print(f"Ingest failed: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_query(args):
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY required")
        sys.exit(1)
    persist = args.db or DEFAULT_PERSIST_DIR
    if not Path(persist).exists():
        print("Error: No vector store. Run 'ingest' first.")
        sys.exit(1)
    try:
        answer = query(args.question, persist_directory=persist, debug=args.debug)
        print(answer)
    except Exception as e:
        print(f"Query failed: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Notion RAG")
    sub = parser.add_subparsers(dest="command", required=True)
    p_ingest = sub.add_parser("ingest")
    p_ingest.add_argument("--page-ids", type=str)
    p_ingest.add_argument("--database-id", type=str)
    p_ingest.add_argument("--data-source-id", type=str)
    p_ingest.add_argument("--output", type=str, default=str(DEFAULT_PERSIST_DIR))
    p_ingest.set_defaults(func=cmd_ingest)
    p_query = sub.add_parser("query")
    p_query.add_argument("question", type=str)
    p_query.add_argument("--db", type=str, default=str(DEFAULT_PERSIST_DIR))
    p_query.add_argument("--debug", action="store_true")
    p_query.set_defaults(func=cmd_query)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
