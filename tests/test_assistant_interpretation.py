import threading
import unittest
from unittest.mock import patch

from localmind.application.use_cases.interpret_request import (
    InterpretAssistantRequest,
    organization_strategy,
)
from localmind.domain.assistant import AssistantError, IntentPrediction, TaskCancelled
from localmind.infrastructure.models.installer import PinnedHuggingFaceModelInstaller
from localmind.infrastructure.models.intent_classifier import OnnxIntentClassifier


class FakeClassifier:
    def __init__(self, intent="organize_photos", similarity=0.8, margin=0.2):
        self.prediction = IntentPrediction(intent, similarity, margin, "test")

    def classify(self, text, cancel_event):
        return self.prediction


class InterpretationPolicyTests(unittest.TestCase):
    def test_low_similarity_and_ambiguous_intent_ask_instead_of_acting(self):
        for similarity, margin in [(0.2, 0.3), (0.8, 0.01)]:
            service = InterpretAssistantRequest(FakeClassifier(similarity=similarity, margin=margin))
            result = service.execute("Help with this folder", threading.Event())
            self.assertEqual(result.capability, "unknown")
            self.assertTrue(result.message)

    def test_organization_without_strategy_asks_follow_up(self):
        result = InterpretAssistantRequest(FakeClassifier()).execute("My photos need tidying", threading.Event())
        self.assertTrue(result.needs_strategy)

    def test_strategy_preserves_explicit_year_despite_date_word(self):
        self.assertEqual(organization_strategy("group by the year of the date taken"), "year")
        self.assertEqual(organization_strategy("by month please"), "month")
        self.assertEqual(organization_strategy("separate by file format"), "type")

    def test_destructive_negated_visual_and_compound_requests_do_not_get_actions(self):
        service = InterpretAssistantRequest(FakeClassifier())
        for text in [
            "Organize photos and delete the originals", "Don't move my photos by month",
            "Group photos by faces", "Organize photos and then open VS Code",
            "Find duplicates and remove them",
        ]:
            with self.subTest(text=text):
                self.assertEqual(service.execute(text, threading.Event()).capability, "unknown")

    def test_unsupported_non_photo_organization_is_not_reinterpreted_as_photos(self):
        result = InterpretAssistantRequest(FakeClassifier()).execute("Organize my documents by month", threading.Event())
        self.assertEqual(result.capability, "unknown")

    def test_another_app_cannot_be_reinterpreted_as_vscode(self):
        result = InterpretAssistantRequest(FakeClassifier("open_vscode")).execute("Open Safari", threading.Event())
        self.assertEqual(result.capability, "task_pipeline")
        self.assertEqual(result.tasks[0].task_id, "A01")
        self.assertEqual(result.tasks[0].parameters["target"], "safari")

    def test_filename_slot_and_followup(self):
        service = InterpretAssistantRequest(FakeClassifier("search_files"))
        result = service.execute("Could you locate a document called proposal?", threading.Event())
        self.assertEqual(result.query, "proposal")
        self.assertTrue(service.execute("Help me find a file", threading.Event()).message)

    def test_missing_model_keeps_basic_tools_but_never_pretends_to_understand(self):
        classifier = FakeClassifier()
        classifier.classify = lambda *args: (_ for _ in ()).throw(AssistantError("model missing"))
        service = InterpretAssistantRequest(classifier)
        self.assertEqual(service.execute("list files", threading.Event()).capability, "list_files")
        with self.assertRaises(AssistantError):
            service.execute("Tidy my photo collection", threading.Event())

    def test_cancellation_never_falls_back_to_executing_basic_tool(self):
        classifier = FakeClassifier()
        classifier.classify = lambda *args: (_ for _ in ()).throw(TaskCancelled("cancelled"))
        event = threading.Event()
        event.set()
        with self.assertRaises(TaskCancelled):
            InterpretAssistantRequest(classifier).execute("list files", event)


class RealOfflineSemanticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        installer = PinnedHuggingFaceModelInstaller()
        if not installer.is_installed():
            raise unittest.SkipTest("Explicitly provision the pinned model in Setup before real inference tests.")
        cls.classifier = OnnxIntentClassifier(installer)
        cls.service = InterpretAssistantRequest(cls.classifier)

    def test_held_out_paraphrases_use_real_model_without_network(self):
        cases = {
            "My pictures are all over the place. Can you tidy them into monthly folders?": ("organize_photos", "month"),
            "There are thousand of photos in a folder can you sort and organize the images": ("organize_photos", None),
            "Can you put all my snapshots in order?": ("organize_photos", None),
            "Please arrange these images according to the year they were captured": ("organize_photos", "year"),
            "Could you track down a document called proposal?": ("search_files", None),
            "I'd like to see the files stored in this directory": ("list_files", None),
            "Could you bring up this project in my code editor?": ("open_vscode", None),
            "Would you locate the PDF files in this directory?": ("find_pdfs", None),
        }
        with patch("socket.socket.connect", side_effect=AssertionError("Inference attempted network access")):
            for text, (capability, strategy) in cases.items():
                with self.subTest(text=text):
                    result = self.service.execute(text, threading.Event())
                    self.assertEqual(result.capability, capability, result)
                    self.assertEqual(result.strategy, strategy, result)
                    self.assertIn("ONNX", result.model_version)

    def test_unknown_request_gets_no_executable_capability(self):
        for text in ["What is the weather like?", "Send an email to my manager", "Rename my files"]:
            with self.subTest(text=text):
                self.assertEqual(self.service.execute(text, threading.Event()).capability, "unknown")

    def test_new_catalog_paraphrases_use_actual_onnx_offline(self):
        cases = {
            "What are the storage hogs around here?": "F05",
            "Could you look over the source tree without executing anything?": "P15",
            "Can you show me an excerpt from this document?": "C01",
            "Could you put these downloads in order?": "FM05",
            "Which items have been edited lately?": "F06",
            "How is space distributed among different kinds of files?": "F04",
            "How's my machine performing right now?": "S04",
        }
        with patch("socket.socket.connect", side_effect=AssertionError("Inference attempted a network connection")):
            for text, expected in cases.items():
                with self.subTest(text=text):
                    result = self.service.execute(text, threading.Event())
                    self.assertEqual(result.capability, "task_pipeline", result)
                    self.assertEqual(result.tasks[0].task_id, expected, result)
                    self.assertIn("ONNX", result.model_version)


if __name__ == "__main__":
    unittest.main()
