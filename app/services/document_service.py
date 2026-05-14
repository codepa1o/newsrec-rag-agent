from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.config import Settings
from app.core.text import tokenize
from app.services.database import Database
from app.services.embedding import EmbeddingProvider, cosine_similarity


SUPPORTED_EXTENSIONS = {".md", ".markdown", ".txt", ".pdf"}
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_OVERLAP = 160


@dataclass(frozen=True)
class ParsedPage:
    text: str
    page: int | None = None
    heading_path: str = ""


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    document_id: str
    user_id: str
    filename: str
    chunk_index: int
    text: str
    page: int | None
    heading_path: str
    source: str
    token_count: int

    def to_record(self) -> dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "user_id": self.user_id,
            "chunk_index": self.chunk_index,
            "text": self.text,
            "page": self.page,
            "heading_path": self.heading_path,
            "source": self.source,
            "token_count": self.token_count,
        }

    def to_dict(self, score: float = 0.0) -> dict[str, Any]:
        snippet = self.text[:260].replace("\n", " ")
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "filename": self.filename,
            "chunk_index": self.chunk_index,
            "page": self.page,
            "heading_path": self.heading_path,
            "source": self.source,
            "snippet": snippet,
            "score": round(score, 4),
        }


@dataclass(frozen=True)
class DocumentHit:
    chunk: DocumentChunk
    score: float


class DocumentVectorIndex:
    """Small local vector index used as the always-available fallback."""

    def __init__(self, embedding_provider: EmbeddingProvider) -> None:
        self.embedding_provider = embedding_provider
        self.chunks: dict[str, DocumentChunk] = {}
        self.vectors: dict[str, list[float]] = {}

    def upsert(self, chunks: list[DocumentChunk]) -> None:
        for chunk in chunks:
            self.chunks[chunk.chunk_id] = chunk
            self.vectors[chunk.chunk_id] = self.embedding_provider.embed(chunk.text)

    def delete_document(self, document_id: str) -> None:
        chunk_ids = [chunk_id for chunk_id, chunk in self.chunks.items() if chunk.document_id == document_id]
        for chunk_id in chunk_ids:
            self.chunks.pop(chunk_id, None)
            self.vectors.pop(chunk_id, None)

    def search(self, user_id: str, query: str, top_k: int = 6, document_id: str | None = None) -> list[DocumentHit]:
        if not query.strip():
            return []
        query_vector = self.embedding_provider.embed(query)
        hits: list[DocumentHit] = []
        for chunk_id, vector in self.vectors.items():
            chunk = self.chunks[chunk_id]
            if chunk.user_id != user_id:
                continue
            if document_id and chunk.document_id != document_id:
                continue
            hits.append(DocumentHit(chunk=chunk, score=cosine_similarity(query_vector, vector)))
        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:top_k]


class ChromaDocumentVectorIndex(DocumentVectorIndex):
    """Chroma-backed document index with the same interface as the local fallback."""

    def __init__(self, persist_dir: Path, embedding_provider: EmbeddingProvider) -> None:
        try:
            import chromadb
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("Install chromadb to use Chroma document index.") from exc
        super().__init__(embedding_provider)
        self.client = chromadb.PersistentClient(path=str(persist_dir))
        self.collection = self.client.get_or_create_collection("local_documents")

    def upsert(self, chunks: list[DocumentChunk]) -> None:
        super().upsert(chunks)
        if not chunks:
            return
        self.collection.upsert(
            ids=[chunk.chunk_id for chunk in chunks],
            documents=[chunk.text for chunk in chunks],
            embeddings=[self.embedding_provider.embed(chunk.text) for chunk in chunks],
            metadatas=[
                {
                    "document_id": chunk.document_id,
                    "user_id": chunk.user_id,
                    "filename": chunk.filename,
                    "chunk_index": chunk.chunk_index,
                    "page": chunk.page or -1,
                    "heading_path": chunk.heading_path,
                    "source": chunk.source,
                }
                for chunk in chunks
            ],
        )

    def delete_document(self, document_id: str) -> None:
        super().delete_document(document_id)
        try:
            self.collection.delete(where={"document_id": document_id})
        except Exception:
            pass

    def search(self, user_id: str, query: str, top_k: int = 6, document_id: str | None = None) -> list[DocumentHit]:
        if not query.strip():
            return []
        where: dict[str, Any] = {"user_id": user_id}
        if document_id:
            where = {"$and": [{"user_id": user_id}, {"document_id": document_id}]}
        try:
            result = self.collection.query(
                query_embeddings=[self.embedding_provider.embed(query)],
                n_results=top_k,
                where=where,
            )
        except Exception:
            return super().search(user_id, query, top_k=top_k, document_id=document_id)
        ids = result.get("ids", [[]])[0]
        distances = result.get("distances", [[]])[0]
        hits: list[DocumentHit] = []
        for chunk_id, distance in zip(ids, distances):
            chunk = self.chunks.get(chunk_id)
            if chunk is None:
                continue
            hits.append(DocumentHit(chunk=chunk, score=1.0 - float(distance)))
        return hits


class DocumentService:
    def __init__(self, settings: Settings, database: Database, embedding_provider: EmbeddingProvider) -> None:
        self.settings = settings
        self.database = database
        self.embedding_provider = embedding_provider
        self.upload_dir = settings.upload_dir
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.index = self._build_index()
        self._load_existing_chunks()

    def ingest_upload(self, user_id: str, filename: str, fileobj) -> dict[str, Any]:
        safe_name = sanitize_filename(filename)
        extension = Path(safe_name).suffix.lower()
        if extension not in SUPPORTED_EXTENSIONS:
            raise ValueError("仅支持上传 Markdown、TXT 和 PDF 文件")

        raw = fileobj.read()
        if not raw:
            raise ValueError("上传文件为空")
        if len(raw) > self.settings.max_upload_mb * 1024 * 1024:
            raise ValueError(f"文件不能超过 {self.settings.max_upload_mb} MB")

        content_hash = hashlib.sha256(raw).hexdigest()
        document_id = self.database.create_or_replace_document(
            user_id=user_id,
            filename=safe_name,
            file_type=extension.lstrip("."),
            file_path="",
            content_hash=content_hash,
        )
        user_dir = self.upload_dir / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        stored_path = user_dir / f"{document_id}{extension}"
        stored_path.write_bytes(raw)

        self.database.create_or_replace_document(
            user_id=user_id,
            filename=safe_name,
            file_type=extension.lstrip("."),
            file_path=str(stored_path),
            content_hash=content_hash,
        )

        try:
            chunks = self._parse_and_chunk(user_id, document_id, safe_name, stored_path, extension)
            self.database.add_document_chunks([chunk.to_record() for chunk in chunks])
            self.database.update_document_status(document_id, "ready", chunk_count=len(chunks))
            self.index.delete_document(document_id)
            self.index.upsert(chunks)
            return {
                "document_id": document_id,
                "filename": safe_name,
                "status": "ready",
                "chunk_count": len(chunks),
                "message": "文档已解析并写入本地资料库",
            }
        except Exception as exc:
            self.database.update_document_status(document_id, "failed", error_message=str(exc))
            return {
                "document_id": document_id,
                "filename": safe_name,
                "status": "failed",
                "chunk_count": 0,
                "message": f"文档解析失败：{exc}",
            }

    def list_documents(self, user_id: str) -> list[dict[str, Any]]:
        return self.database.list_documents(user_id)

    def get_document(self, user_id: str, document_id: str) -> dict[str, Any]:
        document = self.database.get_document(user_id, document_id)
        if not document:
            raise KeyError(document_id)
        chunks = self.database.list_document_chunks(user_id=user_id, document_id=document_id)
        document["chunks"] = [
            {
                "chunk_id": chunk["chunk_id"],
                "chunk_index": chunk["chunk_index"],
                "page": chunk["page"],
                "heading_path": chunk["heading_path"],
                "snippet": chunk["text"][:260],
            }
            for chunk in chunks[:20]
        ]
        return document

    def delete_document(self, user_id: str, document_id: str) -> bool:
        document = self.database.get_document(user_id, document_id)
        deleted = self.database.delete_document(user_id, document_id)
        if deleted:
            self.index.delete_document(document_id)
            if document and document.get("file_path"):
                path = Path(document["file_path"])
                if path.exists() and self.upload_dir in path.parents:
                    path.unlink()
        return deleted

    def reindex_document(self, user_id: str, document_id: str) -> dict[str, Any]:
        document = self.database.get_document(user_id, document_id)
        if not document:
            raise KeyError(document_id)
        path = Path(document["file_path"])
        if not path.exists():
            self.database.update_document_status(document_id, "failed", error_message="原始文件不存在")
            return {"document_id": document_id, "status": "failed", "message": "原始文件不存在"}
        self.database.delete_document(user_id, document_id)
        content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        restored_id = self.database.create_or_replace_document(
            user_id=user_id,
            filename=document["filename"],
            file_type=document["file_type"],
            file_path=str(path),
            content_hash=content_hash,
        )
        chunks = self._parse_and_chunk(user_id, restored_id, document["filename"], path, f".{document['file_type']}")
        self.database.add_document_chunks([chunk.to_record() for chunk in chunks])
        self.database.update_document_status(restored_id, "ready", chunk_count=len(chunks))
        self.index.delete_document(restored_id)
        self.index.upsert(chunks)
        return {
            "document_id": restored_id,
            "filename": document["filename"],
            "status": "ready",
            "chunk_count": len(chunks),
            "message": "文档已重新索引",
        }

    def search(self, user_id: str, query: str, top_k: int = 6, document_id: str | None = None) -> list[DocumentHit]:
        hits = self.index.search(user_id=user_id, query=query, top_k=max(top_k * 3, top_k), document_id=document_id)
        return rerank_document_hits(query, hits)[:top_k]

    def _parse_and_chunk(
        self,
        user_id: str,
        document_id: str,
        filename: str,
        path: Path,
        extension: str,
    ) -> list[DocumentChunk]:
        pages = parse_file(path, extension)
        chunks: list[DocumentChunk] = []
        for page in pages:
            for piece in split_text(page.text, chunk_size=DEFAULT_CHUNK_SIZE, overlap=DEFAULT_OVERLAP):
                text = piece.strip()
                if not text:
                    continue
                chunk_index = len(chunks)
                chunks.append(
                    DocumentChunk(
                        chunk_id=f"{document_id}-{chunk_index}",
                        document_id=document_id,
                        user_id=user_id,
                        filename=filename,
                        chunk_index=chunk_index,
                        text=text,
                        page=page.page,
                        heading_path=page.heading_path,
                        source=filename,
                        token_count=max(len(tokenize(text)), len(text) // 2),
                    )
                )
        if not chunks:
            raise ValueError("没有从文档中解析出可索引文本")
        return chunks

    def _load_existing_chunks(self) -> None:
        rows = self.database.list_document_chunks()
        chunks: list[DocumentChunk] = []
        for row in rows:
            filename = row.get("source") or row["document_id"]
            chunks.append(
                DocumentChunk(
                    chunk_id=row["chunk_id"],
                    document_id=row["document_id"],
                    user_id=row["user_id"],
                    filename=filename,
                    chunk_index=row["chunk_index"],
                    text=row["text"],
                    page=row["page"],
                    heading_path=row["heading_path"] or "",
                    source=row["source"] or filename,
                    token_count=row["token_count"],
                )
            )
        self.index.upsert(chunks)

    def _build_index(self) -> DocumentVectorIndex:
        if self.settings.use_chroma:
            try:
                return ChromaDocumentVectorIndex(self.settings.chroma_persist_dir, self.embedding_provider)
            except Exception:
                return DocumentVectorIndex(self.embedding_provider)
        return DocumentVectorIndex(self.embedding_provider)


def parse_file(path: Path, extension: str) -> list[ParsedPage]:
    if extension in {".txt", ".md", ".markdown"}:
        text = read_text_file(path)
        if extension in {".md", ".markdown"}:
            return parse_markdown(text)
        return [ParsedPage(text=text)]
    if extension == ".pdf":
        return parse_pdf(path)
    raise ValueError("不支持的文件类型")


def read_text_file(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="ignore")


def parse_markdown(text: str) -> list[ParsedPage]:
    pages: list[ParsedPage] = []
    headings: list[str] = []
    buffer: list[str] = []
    current_heading = ""
    for line in text.splitlines():
        match = re.match(r"^(#{1,6})\s+(.+)$", line.strip())
        if match:
            if buffer:
                pages.append(ParsedPage(text="\n".join(buffer), heading_path=current_heading))
                buffer = []
            level = len(match.group(1))
            title = match.group(2).strip()
            headings = headings[: level - 1]
            headings.append(title)
            current_heading = " / ".join(headings)
        buffer.append(line)
    if buffer:
        pages.append(ParsedPage(text="\n".join(buffer), heading_path=current_heading))
    return pages or [ParsedPage(text=text)]


def parse_pdf(path: Path) -> list[ParsedPage]:
    try:
        import fitz
    except ImportError as exc:
        raise ValueError("需要安装 PyMuPDF 才能解析 PDF") from exc

    document = fitz.open(path)
    pages: list[ParsedPage] = []
    for index, page in enumerate(document, start=1):
        text = page.get_text("text").strip()
        if len(text) < 30:
            ocr_text = ocr_pdf_page(page)
            text = ocr_text or text
        if text:
            pages.append(ParsedPage(text=text, page=index))
    document.close()
    return pages


def ocr_pdf_page(page) -> str:
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        return ""
    try:
        ocr = RapidOCR()
        pix = page.get_pixmap(dpi=180)
        temp_path = Path(".ocr-temp") / f"{uuid4().hex}.png"
        temp_path.parent.mkdir(exist_ok=True)
        pix.save(temp_path)
        result, _ = ocr(str(temp_path))
        temp_path.unlink(missing_ok=True)
        if not result:
            return ""
        return "\n".join(item[1] for item in result if len(item) >= 2)
    except Exception:
        return ""


def split_text(text: str, chunk_size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_OVERLAP) -> list[str]:
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > chunk_size:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(split_long_text(paragraph, chunk_size, overlap))
            continue
        if len(current) + len(paragraph) + 2 <= chunk_size:
            current = f"{current}\n\n{paragraph}".strip()
        else:
            if current:
                chunks.append(current)
            current = paragraph
    if current:
        chunks.append(current)
    return chunks


def split_long_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def rerank_document_hits(query: str, hits: list[DocumentHit]) -> list[DocumentHit]:
    query_terms = set(tokenize(query))
    reranked: list[DocumentHit] = []
    for hit in hits:
        text_terms = set(tokenize(hit.chunk.text))
        overlap = len(query_terms & text_terms) / max(len(query_terms), 1)
        reranked.append(DocumentHit(chunk=hit.chunk, score=hit.score + overlap * 0.25))
    reranked.sort(key=lambda item: item.score, reverse=True)
    return reranked


def sanitize_filename(filename: str) -> str:
    name = Path(filename or "document").name
    name = re.sub(r"[^\w.\-\u4e00-\u9fff ]+", "_", name, flags=re.UNICODE).strip()
    return name or "document.txt"
