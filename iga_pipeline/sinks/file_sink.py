"""File-based sink for snapshotting pipeline results."""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Dict, List


class FileSink:
    def __init__(
        self,
        root: str,
        environment: str,
        tenant_id: int,
        customer_id: str,
        timestamp: str | None = None,
    ):
        self.timestamp = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
        tenant_folder = f"tenant_{tenant_id}_customer_{customer_id}"
        self.base_path = os.path.join(root, environment, tenant_folder, f"backup_{self.timestamp}")
        os.makedirs(self.base_path, exist_ok=True)

    def write(self, resource: str, records: List[Dict]):
        if not records:
            return
        path = os.path.join(self.base_path, f"{resource}.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(records, fh, indent=2, ensure_ascii=False)
        return path


class LoggingSink:
    def write(self, resource: str, records: List[Dict]):
        print(f"[LOG] {resource}: {len(records)} records")
        if records:
            preview = records[0]
            print(f"       sample external_id={preview.get('external_id')} display_name={preview.get('display_name')}")
        return None
