"""
Supabase storage client for database and object storage operations.

This module provides:
- Run, Source, Chunk, Document, Citation CRUD operations
- Vector search via pgvector
- Object storage for PDFs and HTML snapshots
"""

import json
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from supabase import Client, create_client

from schemas.config import RunConfig, get_settings
from schemas.models import (
    Chunk,
    Citation,
    Document,
    Event,
    Run,
    SearchResult,
    Source,
)

logger = logging.getLogger(__name__)


class SupabaseClient:
    """
    Supabase client wrapper for all database operations.

    Provides CRUD operations for:
    - Runs
    - Sources
    - Chunks
    - Documents
    - Citations
    - Events
    """

    def __init__(
        self,
        url: str | None = None,
        key: str | None = None,
    ):
        """
        Initialize the Supabase client.

        Args:
            url: Supabase project URL
            key: Supabase service key
        """
        settings = get_settings()
        self.url = url or settings.supabase_url
        self.key = key or settings.supabase_service_key

        if not self.url or not self.key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in environment variables"
            )

        self._client: Client | None = None

    @property
    def client(self) -> Client:
        """Lazy initialization of Supabase client."""
        if self._client is None:
            self._client = create_client(self.url, self.key)
            logger.info("Supabase client initialized")
        return self._client

    # =========================================================================
    # RUNS
    # =========================================================================

    async def create_run(self, config: RunConfig) -> Run:
        """
        Create a new research run.

        Args:
            config: Run configuration

        Returns:
            Created Run model
        """
        data = {
            "title": config.title,
            "objective": config.objective,
            "constraints": config.constraints,
            "status": "created",
            "config": config.model_dump(),
        }

        result = self.client.table("runs").insert(data).execute()

        if not result.data:
            raise ValueError("Failed to create run")

        run_data = result.data[0]
        return Run(
            id=UUID(run_data["id"]),
            title=run_data["title"],
            objective=run_data["objective"],
            constraints=run_data.get("constraints", {}),
            created_at=datetime.fromisoformat(run_data["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(run_data["updated_at"].replace("Z", "+00:00")),
            status=run_data["status"],
            config=RunConfig(**run_data["config"]),
        )

    async def get_run(self, run_id: UUID) -> Run | None:
        """
        Get a run by ID.

        Args:
            run_id: Run ID

        Returns:
            Run model or None if not found
        """
        result = (
            self.client.table("runs")
            .select("*")
            .eq("id", str(run_id))
            .execute()
        )

        if not result.data:
            return None

        run_data = result.data[0]
        return Run(
            id=UUID(run_data["id"]),
            title=run_data["title"],
            objective=run_data["objective"],
            constraints=run_data.get("constraints", {}),
            created_at=datetime.fromisoformat(run_data["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(run_data["updated_at"].replace("Z", "+00:00")),
            status=run_data["status"],
            config=RunConfig(**run_data["config"]),
        )

    async def list_runs(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Run]:
        """
        List all runs.

        Args:
            limit: Maximum number of runs to return
            offset: Offset for pagination

        Returns:
            List of Run models
        """
        result = (
            self.client.table("runs")
            .select("*")
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )

        return [
            Run(
                id=UUID(r["id"]),
                title=r["title"],
                objective=r["objective"],
                constraints=r.get("constraints", {}),
                created_at=datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")),
                updated_at=datetime.fromisoformat(r["updated_at"].replace("Z", "+00:00")),
                status=r["status"],
                config=RunConfig(**r["config"]),
            )
            for r in result.data
        ]

    async def get_runs(self, limit: int = 50, offset: int = 0) -> list[Run]:
        """Compatibility wrapper for listing runs.

        The UI still calls ``get_runs``; keep both names available while we
        transition to ``list_runs`` for clarity.
        """

        return await self.list_runs(limit=limit, offset=offset)

    async def update_run_status(
        self,
        run_id: UUID,
        status: str,
    ) -> None:
        """
        Update a run's status.

        Args:
            run_id: Run ID
            status: New status
        """
        self.client.table("runs").update({"status": status}).eq(
            "id", str(run_id)
        ).execute()

    async def update_run_config(self, run_id: UUID, config: RunConfig) -> Run:
        """Persist an updated run configuration (e.g., brief changes).

        Args:
            run_id: Run ID
            config: New run configuration to store

        Returns:
            Updated Run model
        """
        result = (
            self.client.table("runs")
            .update({"config": config.model_dump()})
            .eq("id", str(run_id))
            .execute()
        )

        if not result.data:
            raise ValueError("Failed to update run config")

        run_data = result.data[0]
        return Run(
            id=UUID(run_data["id"]),
            title=run_data["title"],
            objective=run_data["objective"],
            constraints=run_data.get("constraints", {}),
            created_at=datetime.fromisoformat(run_data["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(run_data["updated_at"].replace("Z", "+00:00")),
            status=run_data["status"],
            config=RunConfig(**run_data["config"]),
        )

    async def delete_run(self, run_id: UUID) -> None:
        """
        Delete a run and all associated data.

        Args:
            run_id: Run ID
        """
        self.client.table("runs").delete().eq("id", str(run_id)).execute()

    # =========================================================================
    # SOURCES
    # =========================================================================

    async def store_source(self, source: Source) -> Source:
        """
        Store a source in the database.

        Args:
            source: Source model

        Returns:
            Stored Source model
        """
        data = {
            "id": str(source.id),
            "run_id": str(source.run_id),
            "type": source.type,
            "title": source.title,
            "uri": source.uri,
            "captured_at": source.captured_at.isoformat(),
            "content_hash": source.content_hash,
            "metadata": source.metadata,
        }

        self.client.table("sources").insert(data).execute()
        return source

    async def get_sources(self, run_id: UUID) -> list[Source]:
        """
        Get all sources for a run.

        Args:
            run_id: Run ID

        Returns:
            List of Source models
        """
        result = (
            self.client.table("sources")
            .select("*")
            .eq("run_id", str(run_id))
            .execute()
        )

        return [
            Source(
                id=UUID(s["id"]),
                run_id=UUID(s["run_id"]),
                type=s["type"],
                title=s["title"],
                uri=s["uri"],
                captured_at=datetime.fromisoformat(s["captured_at"].replace("Z", "+00:00")),
                content_hash=s["content_hash"],
                metadata=s.get("metadata", {}),
            )
            for s in result.data
        ]

    # =========================================================================
    # CHUNKS
    # =========================================================================

    async def store_chunks(
        self,
        chunks: list[Chunk],
        batch_size: int = 50,
    ) -> None:
        """
        Store chunks in the database.

        Args:
            chunks: List of Chunk models
            batch_size: Batch size for insertion
        """
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]

            data = [
                {
                    "id": str(chunk.id),
                    "source_id": str(chunk.source_id),
                    "run_id": str(chunk.run_id),
                    "chunk_index": chunk.chunk_index,
                    "content": chunk.content,
                    "contextual_prefix": chunk.contextual_prefix,
                    "page_start": chunk.page_start,
                    "page_end": chunk.page_end,
                    "section_hint": chunk.section_hint,
                    "heading_hierarchy": chunk.heading_hierarchy,
                    "content_hash": chunk.content_hash,
                    "token_count": chunk.token_count,
                    "chunk_method": chunk.chunk_method,
                    "embedding": chunk.embedding,
                    "metadata": chunk.metadata,
                }
                for chunk in batch
            ]

            self.client.table("chunks").insert(data).execute()

        logger.info(f"Stored {len(chunks)} chunks")

    async def get_chunks(
        self,
        run_id: UUID,
        source_id: UUID | None = None,
    ) -> list[Chunk]:
        """
        Get chunks for a run, optionally filtered by source.

        Args:
            run_id: Run ID
            source_id: Optional source ID filter

        Returns:
            List of Chunk models
        """
        query = (
            self.client.table("chunks")
            .select("*")
            .eq("run_id", str(run_id))
        )

        if source_id:
            query = query.eq("source_id", str(source_id))

        result = query.order("chunk_index").execute()

        return [
            Chunk(
                id=UUID(c["id"]),
                source_id=UUID(c["source_id"]),
                run_id=UUID(c["run_id"]),
                chunk_index=c["chunk_index"],
                content=c["content"],
                contextual_prefix=c.get("contextual_prefix"),
                page_start=c.get("page_start"),
                page_end=c.get("page_end"),
                section_hint=c.get("section_hint"),
                heading_hierarchy=c.get("heading_hierarchy", []),
                content_hash=c["content_hash"],
                token_count=c["token_count"],
                chunk_method=c["chunk_method"],
                embedding=c.get("embedding"),
                metadata=c.get("metadata", {}),
            )
            for c in result.data
        ]

    async def get_chunk(self, chunk_id: UUID) -> Chunk | None:
        """
        Get a single chunk by ID.

        Args:
            chunk_id: Chunk ID

        Returns:
            Chunk model or None
        """
        result = (
            self.client.table("chunks")
            .select("*")
            .eq("id", str(chunk_id))
            .execute()
        )

        if not result.data:
            return None

        c = result.data[0]
        return Chunk(
            id=UUID(c["id"]),
            source_id=UUID(c["source_id"]),
            run_id=UUID(c["run_id"]),
            chunk_index=c["chunk_index"],
            content=c["content"],
            contextual_prefix=c.get("contextual_prefix"),
            page_start=c.get("page_start"),
            page_end=c.get("page_end"),
            section_hint=c.get("section_hint"),
            heading_hierarchy=c.get("heading_hierarchy", []),
            content_hash=c["content_hash"],
            token_count=c["token_count"],
            chunk_method=c["chunk_method"],
            embedding=c.get("embedding"),
            metadata=c.get("metadata", {}),
        )

    # =========================================================================
    # DOCUMENTS
    # =========================================================================

    async def store_document(self, document: Document) -> Document:
        """
        Store a document version.

        Args:
            document: Document model

        Returns:
            Stored Document model
        """
        data = {
            "id": str(document.id),
            "run_id": str(document.run_id),
            "version": document.version,
            "title": document.title,
            "markdown": document.markdown,
            "change_log": document.change_log,
            "config_snapshot": document.config_snapshot.model_dump(),
        }

        self.client.table("documents").insert(data).execute()
        return document

    async def get_document(
        self,
        run_id: UUID,
        version: int | None = None,
    ) -> Document | None:
        """
        Get a document, optionally by version.

        Args:
            run_id: Run ID
            version: Optional version number (latest if not specified)

        Returns:
            Document model or None
        """
        query = (
            self.client.table("documents")
            .select("*")
            .eq("run_id", str(run_id))
        )

        if version:
            query = query.eq("version", version)
        else:
            query = query.order("version", desc=True).limit(1)

        result = query.execute()

        if not result.data:
            return None

        d = result.data[0]
        return Document(
            id=UUID(d["id"]),
            run_id=UUID(d["run_id"]),
            version=d["version"],
            title=d["title"],
            markdown=d["markdown"],
            created_at=datetime.fromisoformat(d["created_at"].replace("Z", "+00:00")),
            change_log=d.get("change_log"),
            config_snapshot=RunConfig(**d["config_snapshot"]),
        )

    async def get_document_versions(self, run_id: UUID) -> list[Document]:
        """
        Get all document versions for a run.

        Args:
            run_id: Run ID

        Returns:
            List of Document models ordered by version
        """
        result = (
            self.client.table("documents")
            .select("*")
            .eq("run_id", str(run_id))
            .order("version")
            .execute()
        )

        return [
            Document(
                id=UUID(d["id"]),
                run_id=UUID(d["run_id"]),
                version=d["version"],
                title=d["title"],
                markdown=d["markdown"],
                created_at=datetime.fromisoformat(d["created_at"].replace("Z", "+00:00")),
                change_log=d.get("change_log"),
                config_snapshot=RunConfig(**d["config_snapshot"]),
            )
            for d in result.data
        ]

    # =========================================================================
    # CITATIONS
    # =========================================================================

    async def store_citations(self, citations: list[Citation]) -> None:
        """
        Store citations for a document.

        Args:
            citations: List of Citation models
        """
        data = [
            {
                "id": str(c.id),
                "document_id": str(c.document_id),
                "citation_key": c.citation_key,
                "source_id": str(c.source_id),
                "reference_entry": c.reference_entry,
                "anchors": [a.model_dump() for a in c.anchors],
            }
            for c in citations
        ]

        self.client.table("citations").insert(data).execute()

    async def get_citations(self, document_id: UUID) -> list[Citation]:
        """
        Get citations for a document.

        Args:
            document_id: Document ID

        Returns:
            List of Citation models
        """
        from schemas.models import CitationAnchor

        result = (
            self.client.table("citations")
            .select("*")
            .eq("document_id", str(document_id))
            .execute()
        )

        return [
            Citation(
                id=UUID(c["id"]),
                document_id=UUID(c["document_id"]),
                citation_key=c["citation_key"],
                source_id=UUID(c["source_id"]),
                reference_entry=c["reference_entry"],
                anchors=[CitationAnchor(**a) for a in c["anchors"]],
            )
            for c in result.data
        ]

    # =========================================================================
    # EVENTS
    # =========================================================================

    async def log_event(
        self,
        run_id: UUID,
        event_type: str,
        node_name: str | None = None,
        payload: dict | None = None,
    ) -> None:
        """
        Log a pipeline event.

        Args:
            run_id: Run ID
            event_type: Event type
            node_name: Optional node name
            payload: Optional event payload
        """
        data = {
            "run_id": str(run_id),
            "type": event_type,
            "node_name": node_name,
            "payload": payload or {},
        }

        self.client.table("events").insert(data).execute()

    async def get_events(
        self,
        run_id: UUID,
        event_type: str | None = None,
    ) -> list[Event]:
        """
        Get events for a run.

        Args:
            run_id: Run ID
            event_type: Optional event type filter

        Returns:
            List of Event models
        """
        query = (
            self.client.table("events")
            .select("*")
            .eq("run_id", str(run_id))
        )

        if event_type:
            query = query.eq("type", event_type)

        result = query.order("ts").execute()

        return [
            Event(
                id=UUID(e["id"]),
                run_id=UUID(e["run_id"]),
                ts=datetime.fromisoformat(e["ts"].replace("Z", "+00:00")),
                type=e["type"],
                node_name=e.get("node_name"),
                payload=e.get("payload", {}),
            )
            for e in result.data
        ]

    # =========================================================================
    # OBJECT STORAGE
    # =========================================================================

    async def store_pdf(
        self,
        source_id: UUID,
        file_path: str,
    ) -> str:
        """
        Store a PDF file in object storage.

        Args:
            source_id: Source ID
            file_path: Path to PDF file

        Returns:
            Storage path
        """
        import os

        bucket = "pdfs"
        storage_path = f"{source_id}.pdf"

        with open(file_path, "rb") as f:
            self.client.storage.from_(bucket).upload(
                storage_path,
                f.read(),
                {"content-type": "application/pdf"},
            )

        return f"{bucket}/{storage_path}"

    async def store_html_snapshot(
        self,
        source_id: UUID,
        html: str,
    ) -> str:
        """
        Store an HTML snapshot in object storage.

        Args:
            source_id: Source ID
            html: HTML content

        Returns:
            Storage path
        """
        bucket = "snapshots"
        storage_path = f"{source_id}.html"

        self.client.storage.from_(bucket).upload(
            storage_path,
            html.encode("utf-8"),
            {"content-type": "text/html"},
        )

        return f"{bucket}/{storage_path}"


# Singleton instance
_client: SupabaseClient | None = None


def get_supabase_client() -> SupabaseClient:
    """Get or create the Supabase client singleton."""
    global _client
    if _client is None:
        _client = SupabaseClient()
    return _client
