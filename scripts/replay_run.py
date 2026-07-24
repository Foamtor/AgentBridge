"""CLI stub: replay committed events for a run_id.

Memory EventLog is process-local; prefer GET /runs/{id}/events against a running API.
This script exercises the core replay helper when an in-process log is provided later
(e.g. Postgres adapter). For now it prints usage.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys


async def _main(run_id: str) -> int:
    # Import kept local so script can be listed without full API boot.
    from agent_base_core.application.replay import replay_run
    from agent_base_core.adapters.memory_event_log import MemoryEventLog

    log = MemoryEventLog()
    events = await replay_run(log, run_id)
    if not events:
        print(
            "No events in empty MemoryEventLog. "
            "Use GET /runs/{run_id}/events on a running API host.",
            file=sys.stderr,
        )
        return 1
    for evt in events:
        print(json.dumps(evt, ensure_ascii=False))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay EventLog for a run_id")
    parser.add_argument("run_id")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_main(args.run_id)))


if __name__ == "__main__":
    main()
