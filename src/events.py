"""事件输出相关工具。"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, TextIO

SCHEMA_VERSION = 1
_RESERVED_EVENT_KEYS = frozenset({"schema_version", "type", "timestamp"})


def build_event(event_type: str, **payload: Any) -> dict[str, Any]:
    """构建带标准元数据的事件对象。"""

    conflicting_keys = sorted(_RESERVED_EVENT_KEYS.intersection(payload))
    if conflicting_keys:
        conflict_text = ", ".join(conflicting_keys)
        raise ValueError(f"payload 包含保留字段：{conflict_text}")

    timestamp = datetime.now().astimezone().isoformat(timespec="milliseconds")
    return {
        "schema_version": SCHEMA_VERSION,
        "type": event_type,
        "timestamp": timestamp,
        **payload,
    }


class JsonLinesEventSink:
    """将事件写入 stdout 和/或 UTF-8 JSON Lines 文件。"""

    def __init__(
        self,
        *,
        stdout: bool = False,
        file_path: str | None = None,
        stdout_stream: TextIO | None = None,
    ) -> None:
        """初始化事件 sink，并按需准备输出目标。"""

        self._stdout_enabled = stdout
        self._stdout_stream = stdout_stream if stdout_stream is not None else sys.stdout
        self._file_stream: TextIO | None = None
        self._closed = False

        if file_path is not None:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            self._file_stream = path.open("a", encoding="utf-8", buffering=1)

    def __enter__(self) -> "JsonLinesEventSink":
        """进入上下文管理器。"""

        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        """离开上下文管理器时关闭文件句柄。"""

        self.close()

    def write(self, event: dict[str, Any]) -> None:
        """将单个事件写为一行 JSON，并立即 flush。"""

        if self._closed:
            raise ValueError("event sink is closed")

        line = json.dumps(event, ensure_ascii=False) + "\n"
        if self._stdout_enabled:
            self._stdout_stream.write(line)
            self._stdout_stream.flush()
        if self._file_stream is not None:
            self._file_stream.write(line)
            self._file_stream.flush()

    def close(self) -> None:
        """关闭文件输出目标。"""

        if self._closed:
            return

        self._closed = True
        if self._file_stream is not None:
            self._file_stream.close()
            self._file_stream = None
