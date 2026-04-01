"""Markdown note store with SQLite FTS5 keyword search."""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import yaml

from src.utils.config import system_config


@dataclass
class Note:
    path: Path
    title: str
    body: str
    metadata: dict


@dataclass
class SearchResult:
    note: Note
    snippet: str
    score: float


def _parse_note(path: Path) -> Note:
    text = path.read_text(encoding="utf-8")
    metadata: dict = {}
    body = text

    # Strip YAML frontmatter
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            try:
                metadata = yaml.safe_load(text[3:end]) or {}
            except yaml.YAMLError:
                pass
            body = text[end + 3:].lstrip()

    title = metadata.get("title") or path.stem.replace("-", " ").replace("_", " ").title()
    return Note(path=path, title=title, body=body, metadata=metadata)


class KnowledgeStore:
    def __init__(self) -> None:
        cfg = system_config()
        self.notes_dir = Path(cfg["notes_dir"])
        self.index_dir = Path(cfg["index_dir"])
        self.index_dir.mkdir(parents=True, exist_ok=True)
        self._db = self._open_db()
        self._sync()

    def _open_db(self) -> sqlite3.Connection:
        db_path = self.index_dir / "fts.db"
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS notes USING fts5("
            "path UNINDEXED, title, body, tokenize='porter unicode61')"
        )
        conn.commit()
        return conn

    def _sync(self) -> None:
        """Index any new or modified notes."""
        indexed: set[str] = {
            row[0]
            for row in self._db.execute("SELECT path FROM notes").fetchall()
        }
        for md_file in self.notes_dir.rglob("*.md"):
            key = str(md_file)
            if key not in indexed:
                note = _parse_note(md_file)
                self._db.execute(
                    "INSERT INTO notes(path, title, body) VALUES (?, ?, ?)",
                    (key, note.title, note.body),
                )
        self._db.commit()

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        # Sanitize query for FTS5
        safe_query = re.sub(r'[^\w\s]', ' ', query).strip()
        if not safe_query:
            return []

        rows = self._db.execute(
            "SELECT path, snippet(notes, 2, '[', ']', '...', 16), "
            "bm25(notes) AS score "
            "FROM notes WHERE notes MATCH ? "
            "ORDER BY score LIMIT ?",
            (safe_query, limit),
        ).fetchall()

        results = []
        for path_str, snippet, score in rows:
            note = _parse_note(Path(path_str))
            results.append(SearchResult(note=note, snippet=snippet, score=abs(score)))
        return results

    def save_note(self, title: str, body: str, metadata: dict | None = None) -> Path:
        """Write a new note to the notes directory and index it."""
        slug = re.sub(r"[^\w\s-]", "", title.lower()).strip()
        slug = re.sub(r"[\s_]+", "-", slug)
        path = self.notes_dir / f"{slug}.md"

        meta = metadata or {}
        meta.setdefault("title", title)

        frontmatter = yaml.dump(meta, allow_unicode=True).strip()
        content = f"---\n{frontmatter}\n---\n\n{body}\n"
        path.write_text(content, encoding="utf-8")

        self._db.execute(
            "INSERT INTO notes(path, title, body) VALUES (?, ?, ?)",
            (str(path), title, body),
        )
        self._db.commit()
        return path
