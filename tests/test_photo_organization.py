"""Real filesystem acceptance tests; every operation is isolated in temp folders."""

import os
import tempfile
import threading
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from localmind.application.use_cases.organize_photos import OrganizePhotos
from localmind.domain.assistant import TaskCancelled
from localmind.domain.organization import OrganizationError
from localmind.infrastructure.filesystem.photo_organizer import FilesystemPhotoOrganizer


class PhotoOrganizationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "photos"
        self.root.mkdir()
        self.adapter = FilesystemPhotoOrganizer(self.base / "journal")
        self.service = OrganizePhotos(self.adapter)
        self.event = threading.Event()
        self.progress = lambda text: None

    def photo(self, name="camera.jpg", taken="2022:03:04 12:30:00"):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        exif = Image.Exif()
        if taken:
            exif[34665] = {36867: taken}
        Image.new("RGB", (8, 8), (30, 40, 50)).save(path, exif=exif)
        if not taken:
            os.utime(path, (1655294400, 1655294400))  # 2022-06-15, away from midnight.
        return path

    def preview(self, strategy="month"):
        return self.service.preview(str(self.root), strategy, self.event, self.progress)

    def apply(self, plan):
        return self.service.apply(plan, plan.id, self.event, self.progress)

    def undo(self):
        return self.service.undo(str(self.root), threading.Event(), self.progress)

    def test_preview_reads_exif_without_changing_any_paths(self):
        source = self.photo()
        before = source.read_bytes()
        plan = self.preview()
        self.assertEqual(plan.moves[0].destination, "Organized Photos/2022/03/camera.jpg")
        self.assertEqual(plan.fallback_dates, 0)
        self.assertEqual(source.read_bytes(), before)
        self.assertFalse((self.root / "Organized Photos").exists())
        self.assertFalse((self.base / "journal").exists())

    def test_missing_metadata_uses_file_date_and_reports_fallback(self):
        self.photo(taken=None)
        plan = self.preview()
        self.assertEqual(plan.fallback_dates, 1)
        self.assertEqual(plan.moves[0].destination, "Organized Photos/2022/06/camera.jpg")

    def test_move_and_undo_after_service_restart_preserve_bytes_and_non_images(self):
        source = self.photo("nested/one.jpg")
        original = source.read_bytes()
        notes = self.root / "notes.txt"
        notes.write_text("leave this alone")
        plan = self.preview()
        result = self.apply(plan)
        destination = self.root / plan.moves[0].destination
        self.assertEqual(result.completed, 1)
        self.assertFalse(source.exists())
        self.assertEqual(destination.read_bytes(), original)
        self.adapter = FilesystemPhotoOrganizer(self.base / "journal")
        self.service = OrganizePhotos(self.adapter)
        self.assertEqual(self.undo().completed, 1)
        self.assertEqual(source.read_bytes(), original)
        self.assertFalse(destination.exists())
        self.assertFalse((self.root / "Organized Photos").exists())
        self.assertEqual(notes.read_text(), "leave this alone")

    def test_collision_names_are_unique_case_insensitively_and_existing_file_is_preserved(self):
        self.photo("one/image.jpg")
        self.photo("two/image.jpg")
        existing = self.photo("Organized Photos/2022/03/IMAGE.JPG")
        before = existing.read_bytes()
        plan = self.preview()
        self.assertEqual(len(plan.moves), 2)
        self.assertEqual(len({m.destination.casefold() for m in plan.moves}), 2)
        self.assertTrue(all("(2)" in m.destination or "(3)" in m.destination for m in plan.moves))
        self.assertEqual(self.apply(plan).completed, 2)
        self.assertEqual(existing.read_bytes(), before)
        self.assertEqual(self.undo().completed, 2)
        self.assertEqual(existing.read_bytes(), before)

    def test_exact_approval_is_required(self):
        source = self.photo()
        plan = self.preview()
        with self.assertRaises(OrganizationError):
            self.service.apply(plan, "other-plan", self.event, self.progress)
        self.assertTrue(source.exists())

    def test_changed_source_invalidates_whole_preview_before_any_moves(self):
        self.photo("first.jpg")
        changed = self.photo("second.jpg")
        plan = self.preview()
        changed.write_bytes(changed.read_bytes() + b"changed")
        with self.assertRaises(OrganizationError):
            self.apply(plan)
        self.assertTrue((self.root / "first.jpg").exists())
        self.assertFalse((self.root / "Organized Photos").exists())

    def test_new_destination_invalidates_preview_without_replacing_file(self):
        source = self.photo()
        plan = self.preview()
        occupied = self.root / plan.moves[0].destination
        occupied.parent.mkdir(parents=True)
        occupied.write_bytes(b"someone else's file")
        with self.assertRaises(OrganizationError):
            self.apply(plan)
        self.assertTrue(source.exists())
        self.assertEqual(occupied.read_bytes(), b"someone else's file")

    def test_symlink_entries_are_skipped_and_output_symlink_is_rejected(self):
        external = self.base / "outside"
        external.mkdir()
        (external / "private.jpg").write_bytes(b"private")
        (self.root / "linked").symlink_to(external, target_is_directory=True)
        self.photo()
        plan = self.preview()
        self.assertEqual(len(plan.moves), 1)
        self.assertEqual(plan.skipped, 1)
        (self.root / "Organized Photos").symlink_to(external, target_is_directory=True)
        with self.assertRaises(OrganizationError):
            self.apply(plan)
        self.assertEqual((external / "private.jpg").read_bytes(), b"private")
        self.assertFalse((external / "2022").exists())

    def test_relative_path_escape_is_rejected(self):
        self.photo()
        plan = self.preview()
        unsafe = replace(plan, moves=(replace(plan.moves[0], source="../outside.jpg"),))
        with self.assertRaises(OrganizationError):
            self.apply(unsafe)

    def test_cancelled_preview_changes_nothing(self):
        source = self.photo()
        self.event.set()
        with self.assertRaises(TaskCancelled):
            self.preview()
        self.assertTrue(source.exists())

    def test_cancelled_batch_keeps_journal_and_can_be_undone(self):
        data = self.photo("000.jpg").read_bytes()
        for i in range(1, 60):
            (self.root / f"{i:03}.jpg").write_bytes(data)
        plan = self.preview("type")
        def stop_after_first_progress(text):
            self.event.set()
        result = self.service.apply(plan, plan.id, self.event, stop_after_first_progress)
        self.assertTrue(result.cancelled)
        self.assertEqual(result.completed, 20)
        self.assertEqual(self.undo().completed, 20)
        self.assertEqual(len(list(self.root.glob("*.jpg"))), 60)

    def test_crash_between_link_and_unlink_can_be_recovered(self):
        source = self.photo()
        original = source.read_bytes()
        plan = self.preview()
        def simulate_interruption(src, dst, expected):
            os.link(src, dst)
            raise OSError("interrupted after link")
        with patch.object(self.adapter, "_move_without_replacing", simulate_interruption):
            result = self.apply(plan)
        self.assertTrue(result.error)
        self.assertEqual(result.completed, 0)
        self.assertTrue(source.exists())
        self.assertTrue((self.root / plan.moves[0].destination).exists())
        self.assertEqual(self.undo().completed, 1)
        self.assertEqual(source.read_bytes(), original)
        self.assertFalse((self.root / plan.moves[0].destination).exists())

    def test_unsupported_hard_links_fail_without_losing_source_and_can_be_cleared_by_undo(self):
        source = self.photo()
        before = source.read_bytes()
        plan = self.preview()
        with patch("localmind.infrastructure.filesystem.photo_organizer.os.link", side_effect=OSError("not supported")):
            result = self.apply(plan)
        self.assertTrue(result.error)
        self.assertEqual(source.read_bytes(), before)
        self.assertEqual(self.undo().completed, 1)
        self.assertEqual(source.read_bytes(), before)
        self.assertFalse((self.root / "Organized Photos").exists())

    def test_workspace_lock_prevents_a_second_mutating_operation(self):
        self.photo()
        plan = self.preview()
        with self.adapter._locked_journal(self.root), self.assertRaisesRegex(OrganizationError, "Another photo operation"):
            self.apply(plan)
        self.assertTrue((self.root / "camera.jpg").exists())

    def test_undo_does_not_replace_new_file_at_original_path(self):
        source = self.photo()
        plan = self.preview()
        self.apply(plan)
        source.write_bytes(b"new file at old name")
        result = self.undo()
        self.assertTrue(result.error)
        self.assertEqual(source.read_bytes(), b"new file at old name")
        self.assertTrue((self.root / plan.moves[0].destination).exists())
        source.unlink()
        self.assertEqual(self.undo().completed, 1)

    def test_undo_preserves_images_edited_after_organization(self):
        self.photo()
        plan = self.preview()
        self.apply(plan)
        destination = self.root / plan.moves[0].destination
        destination.write_bytes(b"edited after organization")
        result = self.undo()
        self.assertTrue(result.error)
        self.assertEqual(destination.read_bytes(), b"edited after organization")

    def test_thousand_images_are_not_limited_by_discovery_result_cap(self):
        data = self.photo("0000.jpg").read_bytes()
        for i in range(1, 1200):
            (self.root / f"{i:04}.jpg").write_bytes(data)
        plan = self.preview("type")
        self.assertEqual(len(plan.moves), 1200)
        self.assertEqual(self.apply(plan).completed, 1200)
        self.assertEqual(self.undo().completed, 1200)
        self.assertEqual(len(list(self.root.glob("*.jpg"))), 1200)


if __name__ == "__main__":
    unittest.main()
