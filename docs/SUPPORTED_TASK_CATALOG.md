# LocalMind — Complete Supported Task Catalog

This is a proposed task catalog for your lightweight offline Python desktop AI assistant, organized by feature, with example natural-language commands and implementation priorities.

The goal is for users to type ordinary messages such as:

> "Analyze my Downloads folder, tell me what's taking up space, and help me organize it."

LocalMind should understand the request, perform supported operations using Python, and reply with a short, useful explanation.

Priority: P0 = MVP, P1 = next release, P2 = advanced.

## 1. Folder Analysis

| ID  | Task                            | Example command                            | Priority |
| --- | ------------------------------- | ------------------------------------------ | -------- |
| F01 | Analyze folder overview         | "What's inside my Downloads folder?"       | P0       |
| F02 | Count files and subfolders      | "How many files are in this folder?"       | P0       |
| F03 | Calculate folder size           | "How much space does this folder use?"     | P0       |
| F04 | Group files by type             | "Show me the file types in Downloads."     | P0       |
| F05 | Find largest files              | "Find the 10 largest files."               | P0       |
| F06 | Find recently modified files    | "What changed this week?"                  | P0       |
| F07 | Find empty folders              | "Find empty directories."                  | P0       |
| F08 | Detect duplicate files          | "Find duplicate images."                   | P1       |
| F09 | Find old files                  | "Show files older than one year."          | P1       |
| F10 | Compare folders                 | "Compare these two directories."           | P1       |
| F11 | Analyze disk usage by subfolder | "Which folder takes the most space?"       | P1       |
| F12 | Detect unusual files            | "Are there any very large files?"          | P1       |
| F13 | Generate folder summary         | "Give me a short overview of this folder." | P0       |
| F14 | Find files by extension         | "Find all PDF files."                      | P0       |
| F15 | Identify inaccessible files     | "Which files couldn't be scanned?"         | P1       |

## 2. File Management and Organization

| ID   | Task                             | Example command                            | Priority |
| ---- | -------------------------------- | ------------------------------------------ | -------- |
| FM01 | Create folder                    | "Create a folder named Reports."           | P0       |
| FM02 | Rename file                      | "Rename this file to notes.md."            | P0       |
| FM03 | Move file                        | "Move this PDF to Documents."              | P0       |
| FM04 | Copy file                        | "Copy this image to Pictures."             | P0       |
| FM05 | Organize by extension            | "Separate images, PDFs, and videos."       | P0       |
| FM06 | Organize by date                 | "Arrange photos by month."                 | P1       |
| FM07 | Batch rename files               | "Rename these images sequentially."        | P1       |
| FM08 | Create ZIP archive               | "Compress this folder."                    | P1       |
| FM09 | Extract ZIP archive              | "Extract this archive."                    | P1       |
| FM10 | Move duplicates to review folder | "Collect duplicate files."                 | P1       |
| FM11 | Delete file to trash             | "Remove these old files."                  | P1       |
| FM12 | Restore supported trashed files  | "Restore my deleted document."             | P2       |
| FM13 | Create text file                 | "Create a README file."                    | P0       |
| FM14 | Find and replace text            | "Replace this word in these files."        | P1       |
| FM15 | Preview file changes             | "Show what will change before organizing." | P0       |

All write operations must validate paths and permissions. Batch moves, overwrites, deletions, and replacements should display a preview and require confirmation.

## 3. Project and Source Code Analysis

| ID  | Task                              | Example command                             | Priority |
| --- | --------------------------------- | ------------------------------------------- | -------- |
| P01 | Detect project language           | "What language is this project written in?" | P0       |
| P02 | Detect frameworks                 | "Does this project use Django or Flask?"    | P0       |
| P03 | Explain project structure         | "Explain this Python project."              | P0       |
| P04 | Read README                       | "Summarize the README."                     | P0       |
| P05 | Identify entry point              | "Where does this app start?"                | P0       |
| P06 | List dependencies                 | "What libraries does it use?"               | P0       |
| P07 | Detect test framework             | "Does this project use pytest?"             | P1       |
| P08 | Find TODO/FIXME comments          | "Find unfinished work."                     | P1       |
| P09 | Show Git status                   | "Are there uncommitted changes?"            | P1       |
| P10 | Show recent Git commits           | "What changed recently?"                    | P1       |
| P11 | Detect large source files         | "Which files are unusually large?"          | P1       |
| P12 | Explain Python function           | "What does this function do?"               | P1       |
| P13 | Find unused dependencies          | "Which packages might be unused?"           | P2       |
| P14 | Identify potential project issues | "Check for missing configuration."          | P1       |
| P15 | Generate project overview         | "Give me a brief summary of this app."      | P0       |

Project detection should use actual files such as `pyproject.toml`, `requirements.txt`, `package.json`, `pubspec.yaml`, and relevant source code rather than guessing from folder names.

## 4. File Reading and Content Analysis

| ID  | Task                        | Example command                            | Priority |
| --- | --------------------------- | ------------------------------------------ | -------- |
| C01 | Preview text file           | "Show this text file."                     | P0       |
| C02 | Read Markdown               | "What's in this README?"                   | P0       |
| C03 | Inspect JSON                | "Explain this configuration."              | P0       |
| C04 | Inspect CSV                 | "What columns are in this CSV?"            | P1       |
| C05 | Extract PDF text            | "Read this PDF."                           | P1       |
| C06 | Extract DOCX text           | "Read this Word document."                 | P1       |
| C07 | Summarize supported content | "Give me a short summary."                 | P1       |
| C08 | Search text within files    | "Find files mentioning authentication."    | P1       |
| C09 | Count words and lines       | "How long is this document?"               | P0       |
| C10 | Detect file encoding        | "What encoding is this file?"              | P1       |
| C11 | Compare two text files      | "What's different between these files?"    | P1       |
| C12 | Explain error logs          | "What errors appear in this log?"          | P1       |
| C13 | Extract headings            | "Show the document outline."               | P1       |
| C14 | Extract metadata            | "When was this file modified?"             | P0       |
| C15 | Find matching filenames     | "Find documents with invoice in the name." | P0       |

Without a generative model, summaries should be based on extracted facts, headings, keywords, and templates. LocalMind must not pretend it fully understands arbitrary document content.

## 5. Desktop and Application Control

| ID  | Task                             | Example command                     | Priority |
| --- | -------------------------------- | ----------------------------------- | -------- |
| A01 | Open installed application       | "Open VS Code."                     | P0       |
| A02 | Open file                        | "Open this PDF."                    | P0       |
| A03 | Open folder                      | "Open Downloads."                   | P0       |
| A04 | Open website                     | "Open GitHub."                      | P0       |
| A05 | Find installed applications      | "Is Firefox installed?"             | P1       |
| A06 | List running processes           | "What's running?"                   | P1       |
| A07 | Close supported application      | "Close Calculator."                 | P1       |
| A08 | Open system settings             | "Open display settings."            | P1       |
| A09 | Launch project workspace         | "Open my Python workspace."         | P1       |
| A10 | Open terminal in folder          | "Open terminal here."               | P1       |
| A11 | Locate application executable    | "Where is Python installed?"        | P1       |
| A12 | List recent application launches | "What did LocalMind open recently?" | P1       |

Application launching should use platform-specific adapters and trusted application resolution, not unrestricted shell execution.

## 6. System Information and Monitoring

| ID  | Task                                | Example command                     | Priority |
| --- | ----------------------------------- | ----------------------------------- | -------- |
| S01 | Show CPU usage                      | "What's my CPU usage?"              | P0       |
| S02 | Show RAM usage                      | "How much memory is free?"          | P0       |
| S03 | Show disk usage                     | "How much storage is available?"    | P0       |
| S04 | Show system information             | "Tell me about my computer."        | P0       |
| S05 | Show OS version                     | "What operating system am I using?" | P0       |
| S06 | Show top memory-consuming processes | "What's using the most RAM?"        | P1       |
| S07 | Show top CPU-consuming processes    | "Which process uses the most CPU?"  | P1       |
| S08 | Show battery status                 | "What's my battery percentage?"     | P1       |
| S09 | Show network status                 | "Am I connected to a network?"      | P1       |
| S10 | Show disk partitions                | "List my drives."                   | P1       |
| S11 | Show system uptime                  | "How long has my PC been running?"  | P1       |
| S12 | Refresh monitoring dashboard        | "Update system stats."              | P0       |

## 7. Conversational Commands and Follow-ups

| ID   | Task                    | Example                        |
| ---- | ----------------------- | ------------------------------ |
| CH01 | Greetings               | "Hello, LocalMind."            |
| CH02 | Capability questions    | "What can you do?"             |
| CH03 | Explain results         | "What does that mean?"         |
| CH04 | Follow-up reference     | "Open that folder."            |
| CH05 | Context retention       | "Show the largest file in it." |
| CH06 | Clarification           | "Which folder did you mean?"   |
| CH07 | Task confirmation       | "Yes, organize those files."   |
| CH08 | Task cancellation       | "Cancel that operation."       |
| CH09 | Task status             | "Has the scan finished?"       |
| CH10 | Recent activity         | "What did you do earlier?"     |
| CH11 | Error explanation       | "Why did that fail?"           |
| CH12 | Suggest next action     | "What should I do next?"       |
| CH13 | Help and examples       | "How can I analyze a project?" |
| CH14 | Conversation reset      | "Start a new conversation."    |
| CH15 | Basic factual responses | "How many files did you find?" |

For reliable follow-ups, store structured context such as the last selected folder, file list, task result, and pending approval. Do not depend entirely on free-form conversation history.

## 8. Action Suggestions

After completing a task, LocalMind can suggest relevant next actions.

| Completed task     | Suggested actions                                      |
| ------------------ | ------------------------------------------------------ |
| Folder analysis    | Find large files, organize by type, inspect duplicates |
| Project analysis   | Read README, show dependencies, inspect entry point    |
| File preview       | Open file, find related files, compare versions        |
| Disk analysis      | Inspect largest folders, find old files                |
| Duplicate scan     | Review duplicate groups, export report                 |
| Git status         | Show changed files, inspect diff                       |
| Error log analysis | Show error locations, find related source files        |

Suggestions should only include actions supported by the installed application.

## 9. Task permissions

Every task should have a defined risk level.

| Level       | Examples                                 | Execution policy                          |
| ----------- | ---------------------------------------- | ----------------------------------------- |
| Read-only   | Analyze folder, inspect system           | Run within authorized scope               |
| Low-impact  | Open app, open folder                    | Usually execute directly                  |
| Write       | Create, rename, move, copy               | Validate and preview changes              |
| Destructive | Delete, overwrite, bulk replace          | Explicit confirmation                     |
| Elevated    | Install software, modify system settings | Outside MVP; require specialized handling |

Never allow model-generated text to bypass permission checks.

## 10. Suggested MVP scope

First release

Recommended

Build approximately 35–45 reliable tasks first, focusing on folder analysis, project inspection, file preview, simple file operations, application launching, system information, and basic conversations.

Avoid implementing every task simultaneously. Several tasks can reuse the same core tools with different parameters.

For example, "find PDFs," "find large files," and "find recently modified files" can all use one file-query engine with different filters.

## 11. Standard task definition for Codex

Every task should have a machine-readable contract.

```
from dataclasses import dataclassfrom enum import Enumfrom typing import Anyclass RiskLevel(str, Enum):    READ_ONLY = "read_only"    LOW = "low"    WRITE = "write"    DESTRUCTIVE = "destructive"@dataclass(frozen=True)class TaskDefinition:    task_id: str    name: str    description: str    risk: RiskLevel    requires_confirmation: bool    parameters: dict[str, Any]@dataclassclass TaskResult:    success: bool    message: str    data: dict[str, Any]    error_code: str | None = None
```

Example:

```
folder_analysis = TaskDefinition(    task_id="F01",    name="Analyze Folder",    description="Analyze a local folder",    risk=RiskLevel.READ_ONLY,    requires_confirmation=False,    parameters={"path": "directory"},)
```

Codex should implement a centralized Task Registry that maps recognized intents to validated task definitions, executes the correct Python service, and returns structured results for the chat interface.

### Final target

LocalMind should feel like a small, intelligent desktop companion that can understand requests such as:

> "Check my Downloads folder, give me a quick summary, show the biggest files, and help me organize the PDFs."

It should perform the analysis, present verified findings, suggest a safe organization plan, request approval for file moves, execute the approved operations, and report exactly what changed.

That is the right level of intelligence and automation for your lightweight offline application.