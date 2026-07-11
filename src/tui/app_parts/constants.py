"""Constants shared by the Textual TUI app modules."""

from __future__ import annotations

import re

PAGE_ENTRY = "entry"
PAGE_DETAIL = "detail"
PAGE_TASKS = "tasks"
PAGE_CONFIG = "config"
ZOTERO_SELECTION_COLUMN_WIDTH = 4
ZOTERO_MIN_TITLE_COLUMN_WIDTH = 20
ZOTERO_MIN_LIBRARY_COLUMN_WIDTH = 10
ZOTERO_MAX_LIBRARY_COLUMN_WIDTH = 18
ZOTERO_MIN_COLLECTION_COLUMN_WIDTH = 12
ZOTERO_MAX_COLLECTION_COLUMN_WIDTH = 24
ERROR_POSITION_COLUMN_WIDTH = 10
ERROR_TYPE_COLUMN_WIDTH = 5
ERROR_PROBLEM_COLUMN_WIDTH = 24
ERROR_STATUS_COLUMN_WIDTH = 8
ERROR_MIN_CONTENT_COLUMN_WIDTH = 6
PROGRESS_LOG_LINE_RE = re.compile(r"^\[[#-]+\]\s+\d{1,3}(?:\.\d+)?%")
APP_TITLE_PLAIN = "LaTeXTransPlus"
APP_TITLE_ART = "\n".join(
    (
        "  ██╗      █████╗ ████████╗███████╗██╗  ██╗████████╗██████╗  █████╗ ███╗   ██╗███████╗      ██╗",
        "  ██║     ██╔══██╗╚══██╔══╝██╔════╝╚██╗██╔╝╚══██╔══╝██╔══██╗██╔══██╗████╗  ██║██╔════╝    ██████╗",
        "  ██║     ███████║   ██║   █████╗   ╚███╔╝    ██║   ██████╔╝███████║██╔██╗ ██║███████╗    ╚═██╔═╝",
        "  ██║     ██╔══██║   ██║   ██╔══╝   ██╔██╗    ██║   ██╔══██╗██╔══██║██║╚██╗██║╚════██║      ╚═╝",
        "  ███████╗██║  ██║   ██║   ███████╗██╔╝ ██╗   ██║   ██║  ██║██║  ██║██║ ╚████║███████║",
        "  ╚══════╝╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝╚══════╝",
    )
)
APP_TITLE_ART_COMPACT = "\n".join(
    (
        "  ██╗      █████╗ ████████╗███████╗██╗  ██╗████████╗      ██╗",
        "  ██║     ██╔══██╗╚══██╔══╝██╔════╝╚██╗██╔╝╚══██╔══╝    ██████╗",
        "  ██║     ███████║   ██║   █████╗   ╚███╔╝    ██║       ╚═██╔═╝",
        "  ██║     ██╔══██║   ██║   ██╔══╝   ██╔██╗    ██║         ╚═╝",
        "  ███████╗██║  ██║   ██║   ███████╗██╔╝ ██╗   ██║",
        "  ╚══════╝╚═╝  ╚═╝   ╚═╝   ╚══════╝╚═╝  ╚═╝   ╚═╝",
    )
)
APP_TITLE_LINE_STYLES = (
    "bold bright_white",
    "bold #dbeafe",
    "bold #93c5fd",
    "bold #60a5fa",
    "bold #3b82f6",
    "bold #1d4ed8",
)
