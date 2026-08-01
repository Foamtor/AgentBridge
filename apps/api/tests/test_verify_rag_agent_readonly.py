from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def test_acceptance_summary_redacts_knowledge_and_credentials() -> None:
    script = Path(__file__).resolve().parents[3] / "scripts" / "verify_rag_agent_readonly.py"
    spec = importlib.util.spec_from_file_location("verify_rag_agent_readonly", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    document = "sensitive knowledge body"
    summary = module.acceptance_summary(
        hit_count=1,
        citations=[
            {
                "chunk_id": "chunk-1",
                "text": document,
                "embedding": [0.1],
                "dsn": "postgresql://secret",
                "password": "secret",
            }
        ],
        latency_ms=12,
    )

    assert set(summary) == {
        "status",
        "tenant_id",
        "hit_count",
        "citation_ids",
        "latency_ms",
    }
    rendered = json.dumps(summary)
    for forbidden in ("text", "embedding", "dsn", "password", document):
        assert forbidden not in rendered
