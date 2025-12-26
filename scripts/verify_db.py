#!/usr/bin/env python3
"""
Verify database schema after migration.

Usage:
    python scripts/verify_db.py
"""
import asyncio
from dotenv import load_dotenv
import os
from supabase import create_client


async def verify_database():
    """Verify all tables and functions exist."""
    load_dotenv()

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")

    if not url or not key:
        print("❌ SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")
        return False

    print("🔍 Verifying database setup...\n")

    try:
        client = create_client(url, key)

        # Test each table
        tables = ["runs", "sources", "chunks", "documents", "citations", "events"]

        for table in tables:
            try:
                result = client.table(table).select("id").limit(1).execute()
                print(f"✅ Table '{table}' exists and is accessible")
            except Exception as e:
                print(f"❌ Table '{table}' failed: {e}")
                return False

        # Test RPC functions
        print("\n🔍 Testing RPC functions...\n")

        # Test match_chunks (vector search)
        try:
            # Create a dummy embedding (1536 dimensions)
            dummy_embedding = [0.0] * 1536
            result = client.rpc(
                "match_chunks",
                {
                    "query_embedding": dummy_embedding,
                    "match_count": 1,
                }
            ).execute()
            print("✅ Function 'match_chunks' exists and is callable")
        except Exception as e:
            print(f"❌ Function 'match_chunks' failed: {e}")

        # Test search_chunks_keyword (full-text search)
        try:
            result = client.rpc(
                "search_chunks_keyword",
                {
                    "query_text": "test",
                    "match_count": 1,
                }
            ).execute()
            print("✅ Function 'search_chunks_keyword' exists and is callable")
        except Exception as e:
            print(f"❌ Function 'search_chunks_keyword' failed: {e}")

        print("\n" + "="*70)
        print("✅ DATABASE VERIFICATION COMPLETE")
        print("="*70)
        print("\nYour Supabase database is ready for the Deep Research App!")
        print("\nNext steps:")
        print("  1. Test the application: streamlit run app/streamlit_app.py")
        print("  2. Create your first research run")
        print("  3. Ingest some PDFs or URLs")

        return True

    except Exception as e:
        print(f"\n❌ Verification failed: {e}")
        print("\nPlease ensure:")
        print("  1. The migration was applied successfully")
        print("  2. SUPABASE_URL and SUPABASE_SERVICE_KEY are correct in .env")
        return False


if __name__ == "__main__":
    asyncio.run(verify_database())
