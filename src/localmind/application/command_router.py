"""Small deterministic router for the prototype's supported command grammar."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

CommandKind = Literal["list_files", "search_files", "find_pdfs", "open_vscode", "unsupported"]


@dataclass(frozen=True, slots=True)
class RoutedCommand:
    kind: CommandKind
    query: str = ""
    reason: str = ""


class CommandRouter:
    """Recognize a small allowlist of commands without a model or shell."""

    _list_files = re.compile(
        r"(?:please )?(?:list|show)(?: all)? (?:the )?files"
        r"(?: in (?:the )?(?:selected )?(?:workspace|folder))?"
    )
    _find_pdfs = re.compile(
        r"(?:please )?(?:find|search for|list|show) (?:all )?pdfs?"
        r"(?: files)?(?: (?:named|matching|containing) (.+))?"
    )
    _search_files = re.compile(
        r"(?:please )?(?:search(?: for)?|find) (?:the )?(?:file|files|filename|filenames)"
        r"(?: named| matching| containing| for)? (.+)"
    )
    _search_for = re.compile(r"(?:please )?(?:search for|find) (.+)")
    _open_vscode = re.compile(
        r"(?:please )?open (?:my )?(?:(?:python )?(?:project|workspace) in )?"
        r"(?:microsoft )?(?:visual studio code|vs code|vscode)"
        r"(?: (?:with|in) (?:the )?(?:selected )?(?:project|workspace))?"
    )
    _open_project_in_vscode = re.compile(
        r"(?:please )?open (?:my )?(?:python )?(?:project|workspace) in "
        r"(?:microsoft )?(?:visual studio code|vs code|vscode)"
    )
    _time_filter = re.compile(
        r"\b(?:today|yesterday|recently)\b|"
        r"\b(?:this|last|past|previous)\s+(?:day|week|month|year)\b|"
        r"\b(?:downloaded|created|modified|changed|updated)\s+"
        r"(?:today|yesterday|this|last|past|previous|in|within|during|before|after|since)\b"
    )

    def parse(self, text: str) -> RoutedCommand | None:
        normalized = " ".join(text.strip().casefold().rstrip(".!?").split())
        if not normalized:
            return None

        # Do not silently reinterpret date-aware requests as filename searches.
        # The current scanner only reads names and has no file timestamp index.
        if self._time_filter.search(normalized):
            return RoutedCommand(
                "unsupported",
                reason=(
                    "Time-based file filters are not available yet. Try “find PDFs” "
                    "or search by a filename, such as “search for report”."
                ),
            )

        # The prototype deliberately executes one action per command.
        if " and " in normalized:
            return None

        if self._list_files.fullmatch(normalized):
            return RoutedCommand("list_files")

        pdf_match = self._find_pdfs.fullmatch(normalized)
        if pdf_match:
            return RoutedCommand("find_pdfs", (pdf_match.group(1) or "").strip())

        if self._open_project_in_vscode.fullmatch(normalized) or self._open_vscode.fullmatch(normalized):
            return RoutedCommand("open_vscode")

        file_match = self._search_files.fullmatch(normalized)
        if file_match:
            return RoutedCommand("search_files", file_match.group(1).strip())

        search_match = self._search_for.fullmatch(normalized)
        if search_match:
            return RoutedCommand("search_files", search_match.group(1).strip())

        return None

