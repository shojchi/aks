"""Unit tests for KnowledgeStore list and delete operations."""
from __future__ import annotations

import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from aks.knowledge.store import KnowledgeStore, Note


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def store(tmp_path, monkeypatch):
    """Return a KnowledgeStore wired to a temp directory with embeddings off."""
    notes_dir = tmp_path / "notes"
    index_dir = tmp_path / ".index"
    notes_dir.mkdir()
    index_dir.mkdir()

    cfg = {
        "notes_dir": "notes",
        "index_dir": ".index",
        "retrieval": {"embeddings_enabled": False},
    }

    monkeypatch.setattr("aks.knowledge.store.system_config", lambda: cfg)
    monkeypatch.setattr("aks.knowledge.store.DATA_DIR", tmp_path)

    return KnowledgeStore()


@pytest.fixture()
def populated_store(store):
    """Store pre-loaded with three notes."""
    store.save_note("Alpha Note", "Body of alpha.")
    store.save_note("Beta Note", "Body of beta.")
    store.save_note("Gamma Note", "Body of gamma.")
    return store


# ---------------------------------------------------------------------------
# list_notes
# ---------------------------------------------------------------------------

class TestListNotes:
    def test_empty_store_returns_empty_list(self, store):
        assert store.list_notes() == []

    def test_returns_all_saved_notes(self, populated_store):
        notes = populated_store.list_notes()
        assert len(notes) == 3

    def test_results_are_note_instances(self, populated_store):
        notes = populated_store.list_notes()
        assert all(isinstance(n, Note) for n in notes)

    def test_sorted_by_title(self, populated_store):
        titles = [n.title for n in populated_store.list_notes()]
        assert titles == sorted(titles)

    def test_titles_match_saved(self, populated_store):
        titles = {n.title for n in populated_store.list_notes()}
        assert titles == {"Alpha Note", "Beta Note", "Gamma Note"}

    def test_skips_missing_files(self, populated_store):
        """Notes whose files were removed externally are silently skipped."""
        notes = populated_store.list_notes()
        notes[0].path.unlink()
        remaining = populated_store.list_notes()
        assert len(remaining) == 2


# ---------------------------------------------------------------------------
# delete_note
# ---------------------------------------------------------------------------

class TestDeleteNote:
    def test_file_is_removed(self, populated_store):
        note = populated_store.list_notes()[0]
        populated_store.delete_note(note.path)
        assert not note.path.exists()

    def test_removed_from_fts_index(self, populated_store):
        note = populated_store.list_notes()[0]
        populated_store.delete_note(note.path)
        results = populated_store.search(note.title)
        assert all(r.note.path != note.path for r in results)

    def test_list_reflects_deletion(self, populated_store):
        notes_before = populated_store.list_notes()
        populated_store.delete_note(notes_before[0].path)
        notes_after = populated_store.list_notes()
        assert len(notes_after) == len(notes_before) - 1

    def test_delete_nonexistent_file_does_not_raise(self, populated_store):
        note = populated_store.list_notes()[0]
        note.path.unlink()  # remove from disk manually first
        populated_store.delete_note(note.path)  # should not raise

    def test_delete_all_notes(self, populated_store):
        for note in populated_store.list_notes():
            populated_store.delete_note(note.path)
        assert populated_store.list_notes() == []


# ---------------------------------------------------------------------------
# save → list → delete round-trip
# ---------------------------------------------------------------------------

class TestRoundTrip:
    def test_save_list_delete_cycle(self, store):
        path = store.save_note("Round Trip", "Some content.")
        assert any(n.path == path for n in store.list_notes())
        store.delete_note(path)
        assert not any(n.path == path for n in store.list_notes())

    def test_deleted_note_not_returned_by_search(self, store):
        store.save_note("Searchable Note", "unique keyword xylophone")
        note = next(n for n in store.list_notes() if n.title == "Searchable Note")
        store.delete_note(note.path)
        results = store.search("xylophone")
        assert results == []

    def test_save_duplicate_slug_overwrites_on_disk(self, store):
        p1 = store.save_note("Dup Note", "first body")
        p2 = store.save_note("Dup Note", "second body")
        assert p1 == p2
        assert p2.read_text(encoding="utf-8").count("second body") == 1
