#!/usr/bin/env python3
"""Quick ingest runner - use data source ID for faster load."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

# Use data source ID from env or default for Content Ideas database
ds_id = os.getenv("NOTION_DATA_SOURCE_ID", "5bcc97fa-499e-4e61-9885-32bb5e72edda")

from rag import ingest
n = ingest(data_source_id=ds_id)
print(f"Ingested {n} documents")
