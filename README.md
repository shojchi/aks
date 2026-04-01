# AKS — Agent Knowledge System

Personal AI assistant that routes queries to specialized agents, grounded in your Markdown notes.

## Quick Start

```bash
# 1. Install dependencies
uv sync

# 2. Set your API key
cp .env.example .env
# edit .env and add ANTHROPIC_API_KEY

# 3. Ask a question
uv run python src/main.py "why is my Python code slow?"

# 4. Force a specific agent
uv run python src/main.py --agent code "explain this decorator pattern"

# 5. Save a note
uv run python src/main.py save "Redis Caching" "Use SETEX for TTL-based caching..."

# 6. Search notes
uv run python src/main.py search "caching"

# 7. Show system status
uv run python src/main.py status
```

## Architecture

```
Query → Orchestrator (Haiku) → Code Agent (Sonnet) → Response
                ↑
         Knowledge Store (SQLite FTS5)
```

**Phase 1 (current):** CLI + Code agent + keyword search
**Phase 2:** Hybrid search (FTS + ChromaDB vector embeddings)
**Phase 3:** All 4 agents (Code, PKM, Writing, Planning) + smart routing
**Phase 4:** Conversation memory, `/save` auto-capture, document import
**Phase 5:** Web UI (FastAPI + HTMX)

## Project Structure

```
config/          YAML configs for system, models, and agent prompts
src/
  main.py        CLI entry point (Click)
  orchestrator/  Intent classification and agent routing
  agents/        Specialist agents (code, pkm, writing, planning)
  retrieval/     Context assembly from knowledge store
  knowledge/     Note I/O and SQLite FTS5 index
  models/        Anthropic SDK wrapper
  utils/         Config loader
knowledge/
  notes/         Your Markdown notes (add .md files here)
  documents/     Imported PDFs and URLs (Phase 4)
  conversations/ Archived conversations (Phase 4)
  .index/        Auto-generated index (gitignored)
tests/
```

## Adding Notes

Drop any `.md` file into `knowledge/notes/`. YAML frontmatter is optional:

```markdown
---
title: My Note
tags: [python, performance]
---

Content here...
```

The index rebuilds automatically on next query.
