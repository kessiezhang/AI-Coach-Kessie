#!/usr/bin/env python3
"""
See what's in your Notion—note titles, sample content, and suggested questions.
Run: python explore_notes.py

This loads directly from Notion (no vector store needed) so you know what
questions to ask. Run 'python test_rag.py ingest' first to index for queries.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from dotenv import load_dotenv
load_dotenv()

DS_ID = os.getenv("NOTION_DATA_SOURCE_ID", "5bcc97fa-499e-4e61-9885-32bb5e72edda")


def _get_titles_only(limit=25):
    """Fast: just fetch page titles from Notion (no block content)."""
    from notion_client import Client
    notion = Client(auth=os.getenv("NOTION_API_KEY"))
    ds_id = DS_ID
    if len(ds_id) == 32:
        ds_id = f"{ds_id[:8]}-{ds_id[8:12]}-{ds_id[12:16]}-{ds_id[16:20]}-{ds_id[20:]}"
    resp = notion.data_sources.query(data_source_id=ds_id, page_size=limit)
    titles = []
    for p in resp.get("results", []):
        for name, prop in (p.get("properties") or {}).items():
            if prop.get("type") == "title":
                arr = prop.get("title", [])
                t = "".join(x.get("plain_text", "") or x.get("text", {}).get("content", "") for x in (arr or []))
                titles.append(t or "Untitled")
                break
    return titles


def main():
    quick = "--quick" in sys.argv

    if quick:
        print("Loading note titles from Notion (quick)...")
        try:
            titles = _get_titles_only(30)
        except Exception as e:
            print(f"Error: {e}")
            return
        print("=" * 60)
        print(f"YOUR NOTION NOTES ({len(titles)} titles)")
        print("=" * 60)
        print()
        for t in titles:
            print(f"  • {t}")
        print("\n💡 Use words from these titles in your questions.")
        print("   Run without --quick to see sample content.")
        return

    from rag import load_notion_documents

    print("Loading from Notion (this may take 1–2 min for many notes)...")
    try:
        docs = load_notion_documents(data_source_id=DS_ID)
    except Exception as e:
        print(f"Error: {e}")
        print("Check NOTION_API_KEY and NOTION_DATA_SOURCE_ID in .env")
        return

    if not docs:
        print("No documents loaded. Check your Notion connection.")
        return

    print("=" * 60)
    print(f"WHAT'S IN YOUR NOTION ({len(docs)} notes)")
    print("=" * 60)

    print("\n📚 Note titles:\n")
    for d in docs[:25]:
        title = d.metadata.get("title", "Untitled")
        print(f"  • {title}")
    if len(docs) > 25:
        print(f"  ... and {len(docs) - 25} more")

    print("\n" + "-" * 60)
    print("📝 Sample content (from first 5 notes):\n")
    for d in docs[:5]:
        title = d.metadata.get("title", "Untitled")
        content = d.page_content[:200].replace("\n", " ")
        if len(d.page_content) > 200:
            content += "..."
        print(f"  [{title}]\n  {content}\n")

    print("-" * 60)
    print("💡 TRY ASKING QUESTIONS USING WORDS FROM ABOVE:\n")
    print("  • What coaching services are offered?")
    print("  • How can I book or schedule a session?")
    print("  • Tell me about [topic from your notes]")
    print("  • 教练服务是什么？ / 如何预约？")
    print("\n📌 TIPS:")
    print("  - Use keywords from your note titles and content")
    print("  - Run 'python test_rag.py ingest' to index these notes")
    print("  - Use --debug to see what gets retrieved:")
    print("    python test_rag.py query \"your question\" --debug")
    print("=" * 60)


if __name__ == "__main__":
    main()
