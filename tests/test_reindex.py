"""Unit tests for KnowledgeStore stale-detection and reindex."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from aks.knowledge.store import KnowledgeStore, ReindexStats


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def store(tmp_path, monkeypatch):
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
    monkeypatch.setattr("aks.knowledge.store.PROJECT_ROOT", tmp_path)
    return KnowledgeStore()


# ---------------------------------------------------------------------------
# _sync() — new files
# ---------------------------------------------------------------------------

class TestSyncAddsNewFiles:
    def test_stats_added_count(self, store):
        store.save_note("Alpha", "body alpha")
        store.save_note("Beta", "body beta")
        # _sync() is already called in __init__; create a fresh store to trigger it
        stats = store._sync()
        # Both already indexed, mtime unchanged → nothing to add
        assert stats.added == 0

    def test_file_added_externally_is_picked_up(self, store, tmp_path, monkeypatch):
        """A .md file dropped into notes_dir without save_note() is indexed on next sync."""
        note_path = tmp_path / "notes" / "external.md"
        note_path.write_text("---\ntitle: External\n---\n\nExternal body.\n", encoding="utf-8")

        stats = store._sync()
        assert stats.added == 1
        results = store.search("External")
        assert any("external" in r.note.path.name for r in results)


# ---------------------------------------------------------------------------
# _sync() — edited files
# ---------------------------------------------------------------------------

class TestSyncDetectsEdits:
    def test_updated_count_after_body_change(self, store, tmp_path):
        path = store.save_note("Edit Me", "original content")

        # Simulate time passing so mtime changes
        new_mtime = path.stat().st_mtime + 1
        path.write_text("---\ntitle: Edit Me\n---\n\nupdated content\n", encoding="utf-8")
        import os
        os.utime(path, (new_mtime, new_mtime))

        stats = store._sync()
        assert stats.updated == 1

    def test_edited_content_is_searchable(self, store, tmp_path):
        path = store.save_note("Evolving Note", "first version content")

        new_mtime = path.stat().st_mtime + 1
        path.write_text(
            "---\ntitle: Evolving Note\n---\n\nsecond version with unique term xylograph\n",
            encoding="utf-8",
        )
        import os
        os.utime(path, (new_mtime, new_mtime))

        store._sync()
        results = store.search("xylograph")
        assert len(results) == 1
        assert results[0].note.title == "Evolving Note"

    def test_unchanged_file_not_counted_as_updated(self, store):
        store.save_note("Stable Note", "nothing changes here")
        stats = store._sync()
        assert stats.updated == 0


# ---------------------------------------------------------------------------
# _sync() — removed files
# ---------------------------------------------------------------------------

class TestSyncRemovesOrphans:
    def test_removed_count_after_external_delete(self, store):
        path = store.save_note("Doomed Note", "will be deleted")
        path.unlink()

        stats = store._sync()
        assert stats.removed == 1

    def test_orphan_not_searchable_after_sync(self, store):
        path = store.save_note("Ghost Note", "unique term poltergeist")
        path.unlink()

        store._sync()
        results = store.search("poltergeist")
        assert results == []

    def test_no_removals_when_all_files_present(self, store):
        store.save_note("Note A", "body a")
        store.save_note("Note B", "body b")
        stats = store._sync()
        assert stats.removed == 0


# ---------------------------------------------------------------------------
# reindex()
# ---------------------------------------------------------------------------

class TestReindex:
    def test_returns_reindex_stats(self, store):
        store.save_note("One", "body")
        stats = store.reindex()
        assert isinstance(stats, ReindexStats)

    def test_reindex_updates_edited_note_without_mtime_change(self, store, tmp_path):
        """reindex() forces re-read even when mtime hasn't changed (e.g. same-second edit)."""
        path = store.save_note("Force Update", "old body")
        # Overwrite content but keep identical mtime to simulate same-second write
        mtime = path.stat().st_mtime
        path.write_text(
            "---\ntitle: Force Update\n---\n\nbrand new body zeptogram\n",
            encoding="utf-8",
        )
        import os
        os.utime(path, (mtime, mtime))

        # _sync() alone would not catch this — mtime is unchanged
        sync_stats = store._sync()
        assert sync_stats.updated == 0

        # reindex() clears mtime cache → treats all files as new
        reindex_stats = store.reindex()
        assert reindex_stats.added == 1  # re-added after cache clear

        results = store.search("zeptogram")
        assert len(results) == 1

    def test_reindex_removes_missing_files(self, tmp_path, monkeypatch):
        # Use auto_sync=False to mirror the real CLI — otherwise __init__ _sync()
        # removes the orphan before reindex() gets a chance to count it.
        notes_dir = tmp_path / "notes"
        index_dir = tmp_path / ".index"
        notes_dir.mkdir()
        index_dir.mkdir()
        cfg = {"notes_dir": "notes", "index_dir": ".index", "retrieval": {"embeddings_enabled": False}}
        monkeypatch.setattr("aks.knowledge.store.system_config", lambda: cfg)
        monkeypatch.setattr("aks.knowledge.store.PROJECT_ROOT", tmp_path)

        # Save a note with a normal store (auto_sync=True)
        s = KnowledgeStore()
        path = s.save_note("Temporary", "here today")
        path.unlink()

        # Re-open without auto_sync, then reindex — should see removed=1
        store2 = KnowledgeStore(auto_sync=False)
        stats = store2.reindex()
        assert stats.removed == 1

    def test_reindex_stats_str(self):
        s = ReindexStats(added=2, updated=1, removed=0)
        assert "added=2" in str(s)
        assert "updated=1" in str(s)
        assert "removed=0" in str(s)
