"""
RAG pipeline: load Notion → chunk → embed → store → retrieve → generate.
"""

import os
import warnings

# Suppress noisy warnings (PyTorch/TF from tokenizers, Chroma deprecation)
warnings.filterwarnings("ignore", message=".*PyTorch.*TensorFlow.*Flax.*")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="langchain")
import shutil
from pathlib import Path
from typing import List, Optional, Union

try:
    from langchain_chroma import Chroma
except ImportError:
    from langchain_community.vectorstores import Chroma
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_text_splitters import RecursiveCharacterTextSplitter

from notion_client import Client
from notion_loader import NotionPageLoader, NotionDataSourceLoader, discover_data_source_from_page


DEFAULT_PERSIST_DIR = Path(__file__).parent / "chroma_db"
DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 150


def get_embeddings():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY required.")
    return OpenAIEmbeddings(model="text-embedding-3-small")


def get_llm():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY required.")
    return ChatOpenAI(model="gpt-4o-mini", temperature=0)


def load_notion_documents(
    page_ids: Optional[List[str]] = None,
    database_id: Optional[str] = None,
    data_source_id: Optional[str] = None,
) -> List[Document]:
    docs: List[Document] = []
    token = os.getenv("NOTION_API_KEY")

    if data_source_id:
        loader = NotionDataSourceLoader(data_source_id=data_source_id)
        docs.extend(loader.load())
        return docs

    if database_id:
        try:
            from langchain_community.document_loaders import NotionDBLoader
            loader = NotionDBLoader(integration_token=token, database_id=database_id.strip().replace("-", ""))
            docs.extend(loader.load())
        except Exception:
            pass

    if page_ids:
        notion = Client(auth=token)
        seen_ds = set()
        for raw_id in page_ids:
            raw_id = raw_id.strip().replace("-", "")
            if len(raw_id) != 32:
                continue
            page_id = f"{raw_id[:8]}-{raw_id[8:12]}-{raw_id[12:16]}-{raw_id[16:20]}-{raw_id[20:]}"
            ds_id = discover_data_source_from_page(notion, page_id)
            if ds_id and ds_id not in seen_ds:
                seen_ds.add(ds_id)
                loader = NotionDataSourceLoader(data_source_id=ds_id)
                docs.extend(loader.load())
            elif not ds_id:
                loader = NotionPageLoader(page_ids=[raw_id])
                docs.extend(loader.load())

    return docs


def create_vector_store(documents: List[Document], persist_directory: Union[str, Path] = DEFAULT_PERSIST_DIR,
                       chunk_size: int = DEFAULT_CHUNK_SIZE, chunk_overlap: int = DEFAULT_CHUNK_OVERLAP):
    if not documents:
        raise ValueError("No documents to process.")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap,
        length_function=len, separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(documents)
    embeddings = get_embeddings()
    persist_path = str(persist_directory)
    if Path(persist_path).exists():
        shutil.rmtree(persist_path)
    vectorstore = Chroma.from_documents(
        documents=chunks, embedding=embeddings,
        persist_directory=persist_path, collection_name="notion_rag",
    )
    return vectorstore


def load_vector_store(persist_directory: Union[str, Path] = DEFAULT_PERSIST_DIR):
    return Chroma(
        persist_directory=str(persist_directory),
        embedding_function=get_embeddings(),
        collection_name="notion_rag",
    )


def build_rag_chain(vectorstore, k: int = 8):
    retriever = vectorstore.as_retriever(search_kwargs={"k": k})
    llm = get_llm()
    template = """You are a warm, supportive life and career coach. Answer the question using the context from your Notion notes below. 

Tone: Be warm, empathetic, and encouraging—like a trusted friend or coach. Use "you" and "your" to make it personal. Add a brief supportive touch when it fits (e.g., "I'm glad you're asking," "That's a great question"). Keep it genuine, not over-the-top.

Rules: Use only information from the context—do not invent. If the context has relevant info, answer based on it in your warm voice. Only say something like "I'd love to help, but I don't have notes on that yet—try asking about coaching, career, mindset, or manifesting" if the context truly has nothing related.

Context:
{context}

Question: {question}

Answer:"""
    prompt = ChatPromptTemplate.from_template(template)
    chain = (
        {"context": retriever | (lambda docs: "\n\n---\n\n".join(d.page_content for d in docs)),
         "question": RunnablePassthrough()}
        | prompt
        | llm
    )
    return chain


def ingest(page_ids=None, database_id=None, data_source_id=None,
           persist_directory: Union[str, Path] = DEFAULT_PERSIST_DIR):
    docs = load_notion_documents(page_ids=page_ids, database_id=database_id, data_source_id=data_source_id)
    create_vector_store(docs, persist_directory=persist_directory)
    return len(docs)


def query(question: str, persist_directory: Union[str, Path] = DEFAULT_PERSIST_DIR, debug: bool = False) -> str:
    vs = load_vector_store(persist_directory=persist_directory)
    retriever = vs.as_retriever(search_kwargs={"k": 8})
    if debug:
        docs = retriever.invoke(question)
        print("--- Retrieved chunks ---")
        for i, doc in enumerate(docs, 1):
            prev = doc.page_content[:200] + "..." if len(doc.page_content) > 200 else doc.page_content
            print(f"\n[{i}] {prev}\n")
        print("--- Answer ---\n")
    chain = build_rag_chain(vs, k=8)
    return chain.invoke(question).content
