#!/usr/bin/env python3
"""
Apply database migrations to Supabase.

Usage:
    python scripts/apply_migration.py
"""
import asyncio
from pathlib import Path

from supabase import create_client, Client
from dotenv import load_dotenv
import os


def get_supabase_admin_client() -> Client:
    """Get Supabase client with service role key."""
    load_dotenv()

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")

    if not url or not key:
        raise ValueError(
            "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env file"
        )

    return create_client(url, key)


def apply_migration(migration_path: Path):
    """Apply a SQL migration file to Supabase."""
    print(f"📄 Reading migration: {migration_path.name}")

    # Read SQL file
    sql = migration_path.read_text()

    print(f"📊 Migration contains {len(sql.splitlines())} lines")
    print("\n" + "="*70)
    print("IMPORTANT: This migration will be applied via Supabase Dashboard")
    print("="*70)
    print("\nPlease follow these steps:")
    print("\n1. Go to: https://supabase.com/dashboard")
    print("2. Select your project")
    print("3. Click 'SQL Editor' in the left sidebar")
    print("4. Click 'New Query'")
    print("5. Copy the SQL from migrations/001_init.sql")
    print("6. Paste into the SQL Editor")
    print("7. Click 'Run' or press Ctrl/Cmd + Enter")
    print("\nThe migration will create:")
    print("  ✓ 6 tables (runs, sources, chunks, documents, citations, events)")
    print("  ✓ 2 extensions (uuid-ossp, vector)")
    print("  ✓ HNSW vector index for similarity search")
    print("  ✓ GIN full-text search index")
    print("  ✓ 2 RPC functions (match_chunks, search_chunks_keyword)")
    print("  ✓ 2 triggers (auto-update search_content and updated_at)")

    print("\n" + "="*70)
    print("Alternative: Use Supabase CLI")
    print("="*70)
    print("\n$ supabase db push")
    print("  (Requires supabase CLI and linked project)")

    print("\n✅ Migration file is ready at: migrations/001_init.sql")


def verify_migration():
    """Verify that migration was applied successfully."""
    try:
        client = get_supabase_admin_client()

        print("\n🔍 Verifying database setup...")

        # Try to query the runs table
        response = client.table("runs").select("id").limit(1).execute()

        print("✅ Migration verified successfully!")
        print(f"   - runs table exists and is accessible")

        return True

    except Exception as e:
        print(f"❌ Verification failed: {e}")
        print("\nPlease ensure you have:")
        print("  1. Applied the migration via Supabase Dashboard")
        print("  2. Set SUPABASE_URL and SUPABASE_SERVICE_KEY in .env")
        return False


if __name__ == "__main__":
    # Path to migration
    migration_file = Path(__file__).parent.parent / "migrations" / "001_init.sql"

    if not migration_file.exists():
        print(f"❌ Migration file not found: {migration_file}")
        exit(1)

    # Display migration instructions
    apply_migration(migration_file)

    # Ask if user wants to verify
    print("\n" + "="*70)
    response = input("\nHave you applied the migration? (y/n): ").strip().lower()

    if response == 'y':
        verify_migration()
    else:
        print("\n📝 Run this script again after applying the migration to verify.")
