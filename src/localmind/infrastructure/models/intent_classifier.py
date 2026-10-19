"""Offline sentence-embedding intent retrieval using the verified ONNX pack."""

from __future__ import annotations

import threading

from localmind.application.ports import LocalModelInstaller
from localmind.domain.assistant import AssistantError, IntentPrediction, TaskCancelled

# These are semantic examples, not a command grammar. Novel phrasing is embedded
# and compared by meaning; the application independently validates its slots.
INTENT_EXAMPLES = {
    "organize_photos": (
        "Please sort and organize the images in this folder.",
        "My photo collection is a mess, could you tidy it up?",
        "Arrange my pictures into folders by the month they were taken.",
        "There are thousands of photos here. Can you put them in order?",
        "Group all these photographs by year.",
        "Separate my images by their file format.",
        "Help me clean up this folder full of unsorted snapshots.",
        "Make monthly folders for my camera roll.",
        "I would like to organize my image library.",
        "Sort my screenshots into dated folders.",
    ),
    "list_files": (
        "Show me what files are in this folder.",
        "What's inside my workspace?",
        "Can I see everything stored here?",
        "Give me an overview of the files in this directory.",
        "List all files under the selected folder.",
    ),
    "search_files": (
        "Can you help me locate a file called report?",
        "I can't find my invoice, look for its filename.",
        "Find documents with proposal in the name.",
        "Where is the file named budget?",
        "Search this folder for my resume.",
        "Look for files related to my project.",
    ),
    "find_pdfs": (
        "Could you show me all the PDF documents here?",
        "Find the PDFs in this folder.",
        "I'm looking for a PDF called invoice.",
        "Gather a list of portable document format files.",
        "Where are my PDF reports?",
    ),
    "open_vscode": (
        "Open this project in Visual Studio Code.",
        "Launch VS Code with my current workspace.",
        "I'd like to work on this folder in my code editor.",
        "Start coding in VS Code using this project.",
        "Bring up my Python workspace in Visual Studio Code.",
    ),
    "unknown": (
        "What will the weather be tomorrow?",
        "Write a Python program for me.",
        "Send an email to my colleague.",
        "Find duplicate photos and delete them.",
        "Sort pictures by faces, people and objects.",
        "Rename every file in this folder.",
        "Play some music.",
    ),
}

INTENT_EXAMPLES.update({
    "folder_analysis": (
        "Analyze my Downloads folder and give me a short summary.",
        "How many files and subfolders are here and how much space do they use?",
        "Give me an inventory of this directory.",
        "Can you check what is taking up space in my documents?",
    ),
    "largest_files": (
        "Show the biggest files in this directory.", "Which items here consume the most disk space?",
        "Track down the ten heaviest files.", "What are the storage hogs in here?",
    ),
    "file_types": (
        "Which file type uses the most space?", "Break down this directory by extension.",
        "What kinds of documents are stored here?",
    ),
    "recent_files": (
        "Show me the files that changed this week.", "Which items were updated lately?",
        "List the most recently modified documents.",
    ),
    "project_analysis": (
        "Explain this software project's structure and programming language.",
        "What frameworks and libraries does this app use?", "Inspect this codebase without running it.",
        "Where does this application begin execution?",
    ),
    "file_preview": (
        "Read this text document and show me an excerpt.", "Inspect the JSON configuration file.",
        "Show the columns in this CSV.", "Count words and lines in this file.",
        "What headings are in this markdown document?",
    ),
    "system_info": (
        "Tell me about my computer's hardware and operating system.", "How much memory is free?",
        "What is my CPU utilization?", "Check available disk storage.",
    ),
    "organize_files": (
        "Tidy this directory into folders by file type.", "Separate PDFs, images and videos.",
        "Help me organize my downloaded documents.", "Put the PDFs in their own folder.",
    ),
})


class OnnxIntentClassifier:
    def __init__(self, installer: LocalModelInstaller) -> None:
        self._installer = installer
        self._session = None
        self._tokenizer = None
        self._examples = None
        self._labels: list[str] = []

    def _load(self, cancel_event: threading.Event) -> None:
        if self._session is not None:
            return
        if cancel_event.is_set():
            raise TaskCancelled("Request cancelled.")
        if not self._installer.is_installed():
            raise AssistantError("Download the local language model in Settings so I can understand requests in your own words.")
        try:
            import onnxruntime as ort
            from tokenizers import Tokenizer
            ort.disable_telemetry_events()
            options = ort.SessionOptions()
            options.intra_op_num_threads = 2
            options.inter_op_num_threads = 1
            session = ort.InferenceSession(
                str(self._installer.install_path / "onnx/model_O4.onnx"),
                sess_options=options, providers=["CPUExecutionProvider"],
            )
            tokenizer = Tokenizer.from_file(str(self._installer.install_path / "tokenizer.json"))
            tokenizer.enable_truncation(max_length=256)
            tokenizer.enable_padding()
            self._session = session
            self._tokenizer = tokenizer
            phrases = []
            for label, examples in INTENT_EXAMPLES.items():
                phrases.extend(examples)
                self._labels.extend([label] * len(examples))
            self._examples = self._embed(phrases, cancel_event)
        except TaskCancelled:
            self._session = None
            self._labels = []
            raise
        except Exception as exc:
            self._session = None
            self._labels = []
            raise AssistantError(
                "The local language model couldn't load. Run “python -m pip install -e .” "
                "in the app environment and check Settings. No request was sent online."
            ) from exc

    def _embed(self, texts: list[str], cancel_event: threading.Event):
        import numpy as np
        vectors = []
        for offset in range(0, len(texts), 8):
            if cancel_event.is_set():
                raise TaskCancelled("Request cancelled.")
            tokens = self._tokenizer.encode_batch(texts[offset:offset + 8])
            inputs = {
                "input_ids": np.asarray([item.ids for item in tokens], dtype=np.int64),
                "attention_mask": np.asarray([item.attention_mask for item in tokens], dtype=np.int64),
                "token_type_ids": np.asarray([item.type_ids for item in tokens], dtype=np.int64),
            }
            feed = {item.name: inputs[item.name] for item in self._session.get_inputs()}
            output = self._session.run(None, feed)[0].astype(np.float32)
            if output.ndim != 3 or output.shape[-1] != 384:
                raise AssistantError("The installed model returned an incompatible embedding shape.")
            mask = inputs["attention_mask"][..., None].astype(np.float32)
            pooled = (output * mask).sum(axis=1) / np.maximum(mask.sum(axis=1), 1e-9)
            pooled /= np.maximum(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-9)
            vectors.append(pooled)
        return np.concatenate(vectors, axis=0)

    def classify(self, text: str, cancel_event: threading.Event) -> IntentPrediction:
        import numpy as np
        self._load(cancel_event)
        try:
            vector = self._embed([text], cancel_event)[0]
            similarities = self._examples @ vector
            scores = {
                label: float(np.max(similarities[[i for i, value in enumerate(self._labels) if value == label]]))
                for label in INTENT_EXAMPLES
            }
            ranked = sorted(scores, key=scores.get, reverse=True)
            best, second = ranked[:2]
            return IntentPrediction(best, scores[best], scores[best] - scores[second], "MiniLM · ONNX local")
        except TaskCancelled:
            raise
        except Exception as exc:
            raise AssistantError("Local language understanding failed. No files were changed; please retry.") from exc
