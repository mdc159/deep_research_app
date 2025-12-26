"""
Storage layer for database and object storage operations.

This package provides abstractions for Supabase/PostgreSQL operations
including vector search and object storage for PDFs/HTML snapshots.

Modules:
- supabase: Supabase client and CRUD operations
- vector: pgvector search operations
"""

from storage.supabase import SupabaseClient, get_supabase_client
from storage.vector import (
    HybridSearch,
    KeywordSearch,
    VectorSearch,
    get_hybrid_searcher,
)

__version__ = "0.1.0"

__all__ = [
    # Supabase
    "SupabaseClient",
    "get_supabase_client",
    # Vector Search
    "VectorSearch",
    "KeywordSearch",
    "HybridSearch",
    "get_hybrid_searcher",
]
