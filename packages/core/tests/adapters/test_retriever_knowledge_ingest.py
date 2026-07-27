"""RetrieverKnowledgeIngest tests."""

from __future__ import annotations

import pytest

from agent_base_core.adapters.fake_retriever import FakeRetriever
from agent_base_core.adapters.memory_ingest_job_store import MemoryIngestJobStore
from agent_base_core.adapters.retriever_knowledge_ingest import RetrieverKnowledgeIngest


@pytest.mark.asyncio
async def test_retriever_knowledge_ingest_records_job() -> None:
    store = MemoryIngestJobStore()
    ingest = RetrieverKnowledgeIngest(FakeRetriever(), store)
    result = await ingest.ingest_documents(
        [{"chunk_id": "c1", "text": "hello ingest"}],
        tenant_id="acme",
    )
    assert result["status"] == "completed"
    assert result["ingested_count"] == 1
    jobs = await store.list_jobs(tenant_id="acme")
    assert len(jobs) == 1
    assert jobs[0]["job_id"] == result["job_id"]
    assert jobs[0]["status"] == "completed"
