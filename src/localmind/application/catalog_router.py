"""Extract bounded task slots from ordinary language before semantic fallback."""

import re

from localmind.domain.tasks import TaskRequest


def scope_hint(text: str) -> str:
    match = re.search(r"\b(downloads|documents|pictures|desktop|movies|music)\b", text, re.IGNORECASE)
    return match.group(1).casefold() if match else ""


def requests_for(text: str) -> tuple[TaskRequest, ...]:
    lower = text.casefold()
    params = {"text": text, "scope": scope_hint(text)}
    found: list[TaskRequest] = []

    def add(task_id: str, **slots: str) -> None:
        if not any(item.task_id == task_id for item in found):
            found.append(TaskRequest(task_id, {**params, **slots}))

    organizing = bool(re.search(r"\b(organiz\w*|organis\w*|separate|sort|tidy|arrange|group)\b", lower))
    photo = bool(re.search(r"\b(photos?|photographs?|pictures?|images?|snapshots?|screenshots?)\b", lower))
    if re.search(r"\b(cpu|ram|memory|battery|uptime|operating system|system stats|system info|computer|storage available|disk usage|free (?:disk|space|storage)|storage is available|pc been running)\b", lower):
        task = "S01" if "cpu" in lower else "S06" if re.search(r"most (?:ram|memory)", lower) else "S02" if re.search(r"\b(ram|memory)\b", lower) else "S08" if "battery" in lower else "S11" if re.search(r"uptime|been running", lower) else "S03" if re.search(r"storage|disk|free space", lower) else "S05" if "operating system" in lower else "S04"
        add(task)
        return tuple(found)
    if re.search(r"\b(project|framework|dependencies|libraries|django|flask|entry point|entrypoint|app start|pytest|readme|codebase|repository)\b|\b(?:this|the|my) app\b", lower) and not re.search(r"\b(open|launch|create|write|rename|move|copy|bring up|start coding)\b", lower):
        task = "P04" if "readme" in lower else "P06" if re.search(r"dependencies|libraries", lower) else "P02" if re.search(r"framework|django|flask", lower) else "P05" if re.search(r"entry.?point|app start", lower) else "P07" if "pytest" in lower else "P01" if "language" in lower else "P03" if "structure" in lower else "P15"
        add(task)
        return tuple(found)
    if re.search(r"\b(create|make|new)\b.*\b(folder|directory)\b", lower):
        match = re.search(r'(?:named|called)\s+["“]?(.+?)["”]?[.!?]*$', text, re.IGNORECASE) or re.search(r'\b(?:folder|directory)\s+["“]?(.+?)["”]?[.!?]*$', text, re.IGNORECASE)
        add("FM01", destination=match.group(1).strip(' "“”') if match else "")
        return tuple(found)
    if re.search(r"\b(create|write|make)\b.*\b(readme|text file|file named|file called)\b", lower):
        match = re.search(r'(?:named|called)\s+(?:["“]([^"”]+)["”]|([^\s]+))', text, re.IGNORECASE)
        content = re.search(r'\b(?:containing|with (?:the )?text|with content)\s+(.+)$', text, re.IGNORECASE)
        add("FM13", destination=(match.group(1) or match.group(2)).rstrip(".!?") if match else "README.md" if "readme" in lower else "",
            content=content.group(1).strip(' "“”') if content else "")
        return tuple(found)
    if re.search(r"\b(rename|move|copy)\b", lower) and not organizing:
        match = re.search(r'\b(rename|move|copy)\s+(.+?)\s+(?:to|into)\s+(.+?)[.!?]*$', text, re.IGNORECASE)
        if match:
            add({"rename": "FM02", "move": "FM03", "copy": "FM04"}[match.group(1).casefold()], source=match.group(2).strip(' "“”'), destination=match.group(3).strip(' "“”'))
            return tuple(found)
    if re.search(r"\b(open|launch|start|bring up)\b", lower) and not organizing:
        if re.search(r"https?://|\b(github|google|website)\b", lower):
            match = re.search(r'https?://[^\s<>"“”]+', text, re.IGNORECASE)
            browser = re.search(r"\b(safari|chrome|firefox)\b", lower)
            add("A04", target=match.group(0).rstrip(".,!?") if match else "https://github.com" if "github" in lower else "https://www.google.com" if "google" in lower else "",
                browser=browser.group(1) if browser else "")
        elif re.search(r"\b(vs ?code|vscode|visual studio code)\b", lower):
            add("A01", target="vscode")
        elif re.search(r"\b(safari|chrome|firefox|calculator|notepad|textedit)\b", lower):
            add("A01", target=re.search(r"\b(safari|chrome|firefox|calculator|notepad|textedit)\b", lower).group(1))
        elif re.search(r"\b(folder|directory|downloads|documents|pictures|desktop)\b", lower) and not re.search(r"code|project|workspace", lower):
            add("A03")
        elif re.search(r"\b(file|pdf|image|document)\b|\.(?:pdf|txt|md|json|png|jpg)\b", lower):
            add("A02")
        return tuple(found)
    if re.search(r"\b(preview|read|inspect|encoding|headings|outline|words|lines|modified|configuration|columns|how long|show this|show that)\b", lower) and re.search(r"\b(file|document|json|csv|text|markdown|configuration|log)\b|\.[a-z0-9]{1,8}\b", lower) and not organizing and not re.search(r"recent|this week|changed", lower):
        task = "C03" if "json" in lower or "configuration" in lower else "C04" if "csv" in lower else "C09" if re.search(r"words|lines|how long", lower) else "C10" if "encoding" in lower else "C13" if re.search(r"headings|outline", lower) else "C14" if "modified" in lower else "C02" if "markdown" in lower else "C01"
        add(task)
        return tuple(found)
    if re.search(r"\b(analy[sz]e|check|overview|summary|summarize|what.s inside|taking up space|how (?:many|much)|file types|count|space does|explain this folder)\b", lower) and not (photo and organizing):
        add("F04" if "file types" in lower else "F02" if re.search(r"how many|count", lower) else "F03" if re.search(r"how much|space does", lower) else "F01")
    if re.search(r"\b(largest|biggest|very large|most space|type is largest)\b", lower):
        task = "F11" if re.search(r"which (?:sub)?folder", lower) else "F04" if "type" in lower else "F05"
        limit = re.search(r"\b(\d{1,3})\s+(?:largest|biggest)\b", lower)
        add(task, limit=limit.group(1) if limit else "1" if re.search(r"\b(?:largest|biggest) file\b", lower) else "10")
    if re.search(r"\b(recent|recently|this week|changed today|modified today|newest)\b", lower):
        extension = re.search(r"\b(pdf|png|jpg|jpeg|csv|json|txt|docx|mp4|py)s?\b", lower)
        add("F06", extension=extension.group(1) if extension else "")
    if re.search(r"\bempty (?:folders|directories)\b", lower):
        add("F07")
    if re.search(r"\b(inaccessible|couldn.t be scanned|skipped)\b", lower):
        add("F15")
    if organizing:
        if photo and not re.search(r"\b(pdfs?|videos?|documents?|extensions?)\b", lower):
            return ()  # Existing EXIF-aware photo planner handles date/type clarification.
        extension = "pdf" if re.search(r"\bpdfs?\b", lower) and not re.search(r"images|videos", lower) else ""
        if re.search(r"\b(month|year|date)\b", lower):
            return ()  # No guessed document date organization.
        add("FM05", extension=extension)
    elif not found:
        extensions = re.search(r"\b(pdf|png|jpg|jpeg|gif|csv|json|txt|docx|mp4|py)s?\b", lower)
        if extensions and re.search(r"find|locate|show|list|look for", lower) and (extensions.group(1) != "pdf" or params["scope"]):
            add("F14", extension=extensions.group(1))
        match = re.search(r"\b(?:with|containing)\s+(.+?)\s+in (?:the |their )?name", text, re.IGNORECASE)
        if match:
            add("C15", query=match.group(1).strip(' "“”'))
    return tuple(found[:6])
