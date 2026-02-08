"""
Notion content loader for RAG.
Supports: single pages, databases, and data sources (embedded databases).
"""

import os
from typing import Iterator, List, Optional

from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document
from notion_client import Client


def _extract_rich_text(rich_text: list) -> str:
    if not rich_text:
        return ""
    return "".join(
        item.get("plain_text", "") or item.get("text", {}).get("content", "")
        for item in rich_text
    )


def _extract_block_text(block: dict) -> str:
    block_type = block.get("type", "")
    type_data = block.get(block_type, {})
    if "rich_text" in type_data:
        return _extract_rich_text(type_data["rich_text"])
    if block_type == "child_page":
        return type_data.get("title", "") or ""
    if block_type == "child_database":
        return type_data.get("title", "") or ""
    if block_type in ("bookmark", "embed"):
        return type_data.get("url", "") or ""
    if block_type == "code":
        return _extract_rich_text(type_data.get("rich_text", []))
    if block_type == "equation":
        return type_data.get("expression", "") or ""
    return ""


def _get_page_title_from_props(props: dict) -> str:
    for name, prop in (props or {}).items():
        if prop.get("type") == "title":
            arr = prop.get("title", [])
            return _extract_rich_text(arr) if arr else "Untitled"
    return "Untitled"


def _fetch_blocks_recursive(notion: Client, block_id: str) -> List[str]:
    parts = []
    cursor = None
    while True:
        resp = notion.blocks.children.list(block_id=block_id, page_size=100, start_cursor=cursor)
        for block in resp.get("results", []):
            if block.get("archived") or block.get("in_trash"):
                continue
            text = _extract_block_text(block)
            if text.strip():
                parts.append(text.strip())
            if block.get("has_children"):
                parts.extend(_fetch_blocks_recursive(notion, block["id"]))
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return parts


def _fetch_block_text_full(notion: Client, block_id: str) -> str:
    parts = []
    cursor = None
    while True:
        try:
            resp = notion.blocks.children.list(block_id=block_id, page_size=100, start_cursor=cursor)
        except Exception:
            # Skip blocks that fail (e.g. transcription, unsupported types)
            return "\n".join(p for p in parts if p and p.strip())
        for block in resp.get("results", []):
            if block.get("archived") or block.get("in_trash"):
                continue
            bt = block.get("type", "")
            if bt == "unsupported":
                continue
            data = block.get(bt, {})
            if "rich_text" in data:
                txt = _extract_rich_text(data.get("rich_text", []))
                if txt:
                    parts.append(txt)
            elif bt == "child_page":
                parts.append(data.get("title", "") or "")
            if block.get("has_children"):
                try:
                    parts.append(_fetch_block_text_full(notion, block["id"]))
                except Exception:
                    pass
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    return "\n".join(p for p in parts if p and p.strip())


class NotionPageLoader(BaseLoader):
    """Load content from Notion page(s)."""

    def __init__(self, page_ids: List[str], *, integration_token: Optional[str] = None):
        self.page_ids = [p.strip().replace("-", "") for p in page_ids if p.strip()]
        self.integration_token = integration_token or os.getenv("NOTION_API_KEY")
        if not self.integration_token:
            raise ValueError("NOTION_API_KEY required.")

    def lazy_load(self) -> Iterator[Document]:
        notion = Client(auth=self.integration_token)
        for raw_id in self.page_ids:
            page_id = f"{raw_id[:8]}-{raw_id[8:12]}-{raw_id[12:16]}-{raw_id[16:20]}-{raw_id[20:]}" if len(raw_id) == 32 else raw_id
            try:
                page = notion.pages.retrieve(page_id=page_id)
                title = _get_page_title_from_props(page.get("properties", {}))
                blocks = _fetch_blocks_recursive(notion, page_id)
                content = "\n\n".join(blocks) if blocks else f"[Page: {title}]"
                yield Document(page_content=content, metadata={"source": page_id, "title": title})
            except Exception as e:
                raise RuntimeError(f"Failed to load page {page_id}: {e}") from e


class NotionDataSourceLoader(BaseLoader):
    """Load content from Notion data source (embedded database)."""

    def __init__(self, data_source_id: str, *, integration_token: Optional[str] = None):
        self.data_source_id = data_source_id.strip().replace("-", "")
        self.integration_token = integration_token or os.getenv("NOTION_API_KEY")
        if not self.integration_token:
            raise ValueError("NOTION_API_KEY required.")

    def lazy_load(self) -> Iterator[Document]:
        notion = Client(auth=self.integration_token)
        ds_id = self.data_source_id
        if len(ds_id) == 32:
            ds_id = f"{ds_id[:8]}-{ds_id[8:12]}-{ds_id[12:16]}-{ds_id[16:20]}-{ds_id[20:]}"
        cursor = None
        while True:
            resp = notion.data_sources.query(data_source_id=ds_id, page_size=100, start_cursor=cursor)
            for page in resp.get("results", []):
                page_id = page["id"]
                title = _get_page_title_from_props(page.get("properties", {}))
                content = _fetch_block_text_full(notion, page_id)
                if not content.strip():
                    content = f"[Page: {title}]"
                yield Document(page_content=content, metadata={"source": page_id, "title": title})
            if not resp.get("has_more"):
                break
            cursor = resp.get("next_cursor")


def discover_data_source_from_page(notion: Client, page_id: str) -> Optional[str]:
    """Discover data_source_id for a page with embedded database."""
    try:
        search_resp = notion.search(filter={"property": "object", "value": "data_source"}, page_size=5)
        for ds in search_resp.get("results", []):
            ds_id = ds.get("id")
            if ds_id:
                try:
                    notion.data_sources.query(data_source_id=ds_id, page_size=1)
                    return ds_id
                except Exception:
                    continue
    except Exception:
        pass
    return None
