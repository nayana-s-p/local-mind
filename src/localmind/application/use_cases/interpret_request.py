"""Resolve semantic intent into an allowlisted capability and typed slots."""

from __future__ import annotations

import re
import threading

from localmind.application.catalog_router import requests_for, scope_hint
from localmind.application.command_router import CommandRouter
from localmind.application.ports import IntentClassifier
from localmind.domain.assistant import (
    AssistantDecision,
    AssistantError,
    OrganizationStrategy,
    TaskCancelled,
)
from localmind.domain.tasks import TaskRequest


def organization_strategy(text: str) -> OrganizationStrategy | None:
    text = text.casefold()
    if re.search(r"\b(month|monthly|months)\b", text):
        return "month"
    if re.search(r"\b(year|yearly|years|annual|annually)\b", text):
        return "year"
    if re.search(r"\b(type|types|format|formats|extension|extensions|jpeg|jpg|png)\b", text):
        return "type"
    if re.search(r"\b(date|dates|chronological|chronologically|timeline|taken)\b", text):
        return "month"
    return None


class InterpretAssistantRequest:
    """Deterministic slot extraction first; semantic retrieval for novel phrasing.

    Neither route authorizes file changes. Write handlers only create previews.
    """

    CAPABILITIES = frozenset({"organize_photos", "list_files", "search_files", "find_pdfs", "open_vscode"})

    def __init__(self, classifier: IntentClassifier) -> None:
        self._classifier = classifier
        self._legacy = CommandRouter()

    def execute(self, text: str, cancel_event: threading.Event) -> AssistantDecision:
        text = text.strip()
        if not text or len(text) > 2000:
            return AssistantDecision(message="Please describe your task in between 1 and 2,000 characters.")
        if cancel_event.is_set():
            raise TaskCancelled("Request cancelled.")
        lower = text.casefold()
        if re.search(r"\b(?:send (?:an? |the )?(?:email|message)|email|schedule|uninstall|install software|sudo|powershell|run .{0,100}tests|execute .{0,100}(?:script|command)|shut down)\b", lower):
            return AssistantDecision(message="That automation isn't installed. I can inspect folders/projects/files, prepare supported file changes, open known targets, and report local system metrics. No action was taken.")
        if re.search(r"\b(delete|erase|remove|trash|wipe|overwrite|deduplicat\w*|duplicate\w*|compress|resize|encrypt)\b", lower):
            return AssistantDecision(message=(
                "That request includes an unavailable operation. Duplicate detection, deletion, "
                "compression, encryption and overwriting are not installed. No action was taken. "
                "I can analyze folders, inspect projects/files, prepare organization previews, and show system metrics."
            ))
        if re.search(r"\b(don't|do not|never|without moving|do nothing|not now)\b", lower):
            return AssistantDecision(message="I haven't changed anything. Tell me which task you'd like me to prepare.")
        if (re.search(r"\b(photos?|images?|pictures?|photographs?)\b", lower)
                and re.search(r"\b(people|faces|person|animals|scenery|beaches|beach|objects|pets|selfies|landscapes|similarity|visually|content)\b", lower)):
            return AssistantDecision(message=(
                "Grouping photos by what is in them needs a vision model, which isn't available yet. "
                "I can group them by the date taken, year, or file format. Which would you like?"
            ))
        if re.search(r"\b(documents?|pdfs?|videos?|files)\b", lower) and re.search(r"\b(month|year|date)\b", lower) and re.search(r"\b(organiz\w*|organis\w*|group|arrange|sort)\b", lower) and not re.search(r"\b(photos?|images?|pictures?)\b", lower):
            return AssistantDecision(message="Date-based grouping is available for photos. For other files, I can prepare an organization preview by file type.")
        if re.search(r"\b(organiz\w*|organis\w*|group|arrange|sort)\b", lower) and re.search(r"\b(topic|meaning|content|subject|color|colour|size|alphabetical|alphabetically)\b", lower):
            return AssistantDecision(message="That grouping method isn't available. I can prepare a preview by file extension, or group photos by month/year from date metadata. Which would you prefer?")
        if re.search(r"\bhow (?:can|do|should) i\b|\b(?:show me|give me) (?:some )?examples\b", lower):
            return AssistantDecision(message="Choose a workspace and describe what you need. Try “Analyze this folder”, “Show the largest files”, “Explain this project”, “Read notes.md”, “Organize the PDFs”, or “Show system information”. I show factual results and preview file changes before approval.")
        catalog_tasks = requests_for(text)
        if catalog_tasks:
            clauses = re.split(r"\b(?:and|then)\s+(?:then\s+)?(?=(?:open|launch|create|rename|move|copy|read|inspect|analy[sz]e|check|show|find|explain|count)\b)|,\s*(?=(?:open|launch|create|rename|move|copy|read|inspect|analy[sz]e|check|show|find|explain|count)\b)", lower)
            if len(clauses) > len(catalog_tasks):
                return AssistantDecision(message="I need those steps separately to avoid dropping an action. I can combine a folder overview, largest-file report and organization preview; other combinations need separate requests.")
            return AssistantDecision(capability="task_pipeline", tasks=catalog_tasks,
                                     model_version="Local tools · deterministic routing · no generative model")
        if re.search(r"\b(?:and|then)\s+(?:then\s+)?(?:open|launch|find|search|rename|delete)\b", lower):
            return AssistantDecision(message=(
                "I need clarification before combining those actions. I can combine a folder analysis, "
                "largest-file report and file-type organization preview. Please ask for other launches separately."
            ))
        if lower.rstrip(" .!?") in {"hi", "hello", "hey", "help", "what can you do", "how can you help me"} or re.fullmatch(r"(?:hi|hello|hey)[, ]+localmind[.!?]*", lower):
            return AssistantDecision(message=(
                "I can analyze folders (sizes, types, largest/recent files), inspect projects and dependencies, "
                "preview text/JSON/CSV, prepare file creation/rename/move/copy/type-organization previews, "
                "organize photos by date, open supported apps/files/folders/websites, and show system metrics. "
                "Try: “Check my Downloads folder, show the biggest files, and help me organize the PDFs.” "
                "File changes always wait for your approval."
            ))
        legacy = self._legacy.parse(text)
        if legacy and legacy.kind == "unsupported":
            return AssistantDecision(message=legacy.reason)
        if legacy:
            return AssistantDecision(capability=legacy.kind, query=legacy.query,
                                     model_version="Local tools · deterministic routing")
        try:
            prediction = self._classifier.classify(text, cancel_event)
        except TaskCancelled:
            raise
        except AssistantError:
            if not legacy:
                raise
            return AssistantDecision(
                capability=legacy.kind, query=legacy.query, model_version="Basic tools · model unavailable"
            )
        semantic_tasks = {"folder_analysis": "F01", "largest_files": "F05", "file_types": "F04",
                          "recent_files": "F06", "project_analysis": "P15", "file_preview": "C01",
                          "system_info": "S04", "organize_files": "FM05"}
        if prediction.intent in semantic_tasks and prediction.similarity >= 0.43 and prediction.margin >= 0.035:
            return AssistantDecision(capability="task_pipeline", model_version=prediction.model_version,
                                     tasks=(TaskRequest(semantic_tasks[prediction.intent], {"text": text, "scope": scope_hint(text)}),))
        if prediction.intent not in self.CAPABILITIES or prediction.similarity < 0.43 or prediction.margin < 0.035:
            return AssistantDecision(
                message="I'm not sure what action you want. I can analyze a folder or project, preview a file, "
                        "find files, prepare organization changes, open supported targets, or show system metrics. Which task did you mean?",
                model_version=prediction.model_version,
            )
        capability = prediction.intent
        if capability == "organize_photos":
            if (re.search(r"\b(documents?|pdfs?|music|videos?)\b", lower)
                    and not re.search(r"\b(photos?|images?|pictures?|photographs?|screenshots?)\b", lower)):
                return AssistantDecision(message="I can organize images by date or format. Organization of other file types isn't available yet.")
            strategy = organization_strategy(text)
            return AssistantDecision(
                capability=capability,
                strategy=strategy,
                needs_strategy=strategy is None,
                message="" if strategy else (
                    "How would you like the images grouped: by month taken, year taken, or file type? "
                    "I'll prepare a preview first. If a photo has no date metadata, I'll use its file modification date."
                ),
                model_version=prediction.model_version,
            )
        if capability == "open_vscode" and not re.search(r"\b(vs ?code|vscode|visual studio code|code editor|coding|code|python|project|workspace)\b", lower):
            return AssistantDecision(message="Which supported app did you mean? I can open VS Code, Safari, Chrome, Firefox, Calculator, Notepad or TextEdit when available on this platform.")
        query = ""
        if capability in {"search_files", "find_pdfs"}:
            query = self._query(text)
            if capability == "find_pdfs" and not re.search(r'["“]|\b(named|called|matching|containing|about|related to)\b', text, re.IGNORECASE):
                query = ""
            if legacy and legacy.kind in {"search_files", "find_pdfs"}:
                query = legacy.query
            if capability == "search_files" and not query:
                return AssistantDecision(
                    message="What filename, or part of a filename, should I look for?",
                    capability="search_files", model_version=prediction.model_version,
                )
        return AssistantDecision(capability=capability, query=query, model_version=prediction.model_version)

    @staticmethod
    def _query(text: str) -> str:
        quoted = re.search(r'["“]([^"”]+)["”]', text)
        if quoted:
            return quoted.group(1).strip()
        named = re.search(
            r"\b(?:named|called|matching|containing|about|related to|for)\s+(.+?)(?:\s+in (?:my|the|this|our)\b.*)?[.?!]*$",
            text, re.IGNORECASE,
        )
        if named:
            query = re.sub(r"\s+(?:please|for me)$", "", named.group(1), flags=re.IGNORECASE)
            return query.strip(" .?!")
        return ""
