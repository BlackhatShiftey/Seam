"""Tests for PgVector composite primary key (record_id, model_name)."""
import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("PGVECTOR_TEST_DSN"),
    reason="PGVECTOR_TEST_DSN not set",
)


class TestPgVectorCompositePK:
    def test_composite_pk_allows_two_models_same_record(self):
        from seam_runtime.vector_adapters import PgVectorAdapter
        from seam_runtime.models import HashEmbeddingModel

        dsn = os.environ["PGVECTOR_TEST_DSN"]
        table = f"seam_vector_pk_test_{uuid.uuid4().hex[:12]}"

        # Create two adapters with different model names but same table
        model_a = HashEmbeddingModel(name="model-a", dimension=64)
        model_b = HashEmbeddingModel(name="model-b", dimension=64)

        adapter_a = PgVectorAdapter(dsn=dsn, model=model_a, table_name=table)
        adapter_b = PgVectorAdapter(dsn=dsn, model=model_b, table_name=table)

        try:
            adapter_a.ensure_schema()

            # Insert same record_id with two different model_names via raw SQL
            # because index_records() uses the adapter's own model name.
            with adapter_a._connect() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"""
                        insert into {table} (record_id, model_name, dimension, source_text, source_hash, embedding, updated_at)
                        values (%s, %s, %s, %s, %s, %s::vector, %s)
                        on conflict (record_id, model_name) do nothing
                        """,
                        ("test-record-1", "model-a", 64, "source text", "hash123", _vector_literal_64([0.1] * 64), "2025-01-01T00:00:00Z"),
                    )
                    cursor.execute(
                        f"""
                        insert into {table} (record_id, model_name, dimension, source_text, source_hash, embedding, updated_at)
                        values (%s, %s, %s, %s, %s, %s::vector, %s)
                        on conflict (record_id, model_name) do nothing
                        """,
                        ("test-record-1", "model-b", 64, "source text", "hash123", _vector_literal_64([0.2] * 64), "2025-01-01T00:00:00Z"),
                    )
                connection.commit()

            count = adapter_a.vector_count()
            assert count == 2, f"Expected 2 rows (one per model_name), got {count}"

            # Verify both rows exist
            with adapter_a._connect() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"select model_name from {table} where record_id = %s order by model_name",
                        ("test-record-1",),
                    )
                    model_names = [r[0] for r in cursor.fetchall()]
            assert model_names == ["model-a", "model-b"], f"Expected both model names, got {model_names}"

        finally:
            with adapter_a._connect() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(f'drop table if exists "{table}"')
                connection.commit()


def _vector_literal_64(vector: list[float]) -> str:
    return "[" + ",".join(f"{float(value):.8f}" for value in vector) + "]"
