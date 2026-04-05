# Veles (AKS) — dependency inventory

This document lists every **declared** Python dependency from `pyproject.toml`, why the project needs it, and where it shows up in the codebase. Standard-library modules are not listed.

Sources: `pyproject.toml`, `src/aks/**/*.py`, `tests/**/*.py`.

---

## Runtime dependencies (`[project].dependencies`)

| Package | Role in this project | Where it is used |
|--------|----------------------|------------------|
| **google-genai** | Official Google SDK for **Gemini**: non-streaming and streaming chat, and **text embeddings** for the vector index. | `src/aks/models/llm.py` — `genai.Client`, `types` for `generate_content`, `generate_content_stream`, `embed_content`. |
| **openai** | **OpenAI-compatible HTTP client** used against Cerebras’ API (`base_url=https://api.cerebras.ai/v1`) for chat completions and streaming with token usage. | `src/aks/models/llm.py` — `OpenAI`, `chat.completions.create` (non-stream and stream). |
| **chromadb** | **Embedded vector database** (persistent on disk) for semantic search over notes: stores embeddings, runs similarity queries (cosine). | `src/aks/knowledge/store.py` — `PersistentClient`, collection `add` / `update` / `delete` / `query` when `embeddings_enabled`. |
| **click** | **CLI framework**: command groups, arguments, options, prompts, confirmations, and terminal output for the `aks` entry point. | `src/aks/main.py` — `@click.group`, commands (`ask`, `chat`, `save`, `search`, `import`, `serve`, etc.). |
| **pyyaml** (import: `yaml`) | **YAML parsing and serialization** for app config and note frontmatter. | `src/aks/utils/config.py` — `yaml.safe_load` for `system.yaml`, `models.yaml`, agent YAMLs. `src/aks/knowledge/store.py` — frontmatter in `_parse_note`, `yaml.dump` in `save_note`. Tests: `tests/test_config_files.py`. |
| **python-dotenv** (import: `dotenv`) | Loads **`.env`** so API keys and optional `AKS_HOME` are available without exporting variables manually. | `src/aks/main.py` — `load_dotenv` for `AKS_HOME/.env`. `src/aks/web/app.py` — `load_dotenv()` at startup. |
| **trafilatura** | **Main-content extraction from HTML**: fetch (CLI) or parse downloaded HTML (web UI) into clean text and metadata (title) when importing URLs into notes. | `src/aks/main.py` — `_import_url` (`fetch_url`, `extract`, `extract_metadata`). `src/aks/web/app.py` — `/import` after `_safe_fetch` (`extract`, `extract_metadata`). |
| **lxml_html_clean** | Not imported directly in application code; pinned so the **HTML parsing/cleaning stack** used alongside trafilatura/lxml stays on a maintained cleaner (avoids relying on deprecated or split pieces of older lxml HTML APIs). | Declared in `pyproject.toml` as a first-class dependency for reproducible installs. |
| **pypdf** | **PDF text extraction** and chunked splitting for large documents when importing `.pdf` files as one or more notes. | `src/aks/main.py` — `_import_pdf` (`PdfReader`, per-page text). `src/aks/web/app.py` — `/import/pdf` (`PdfReader` on uploaded bytes). |
| **fastapi** | **Web UI (Phase 5)**: HTTP routes, HTML responses, static files, cookies, form handling, and integration with Jinja2 templates. | `src/aks/web/app.py` — `FastAPI`, `Request`/`Response`, `Form`, `Cookie`, `StaticFiles`, `Jinja2Templates`, etc. |
| **uvicorn** `[standard]` | **ASGI server** that runs the FastAPI app. The `[standard]` extra adds **watchfiles** (reload), **uvloop** (event loop on supported platforms), **httptools**, and **websockets** for a production-leaning dev and serve experience. | `src/aks/main.py` — `serve` command calls `uvicorn.run("aks.web.app:app", ...)`. |
| **jinja2** | **Server-side HTML templates** for the web UI (layouts, partials). | `src/aks/web/app.py` — `fastapi.templating.Jinja2Templates` (requires Jinja2). |
| **python-multipart** | **Multipart form parsing** required by FastAPI for `Form(...)` fields and file uploads (`request.form()` / upload fields). | Needed whenever `app.py` accepts `Form(...)` or reads uploaded files (e.g. `/chat`, `/import`, `/import/pdf`). |
| **sse-starlette** | **Server-Sent Events (SSE)** helper for streaming chat updates over HTTP (`EventSourceResponse`). | `src/aks/web/app.py` — `/chat/stream/{task_id}` returns `EventSourceResponse(generator())`. |

---

## Development dependencies (`[tool.uv].dev-dependencies`)

| Package | Role in this project | Where it is used |
|--------|----------------------|------------------|
| **pytest** | Test runner and assertions for unit and integration-style tests. | All files under `tests/`. |
| **pytest-asyncio** | Enables **async test** support; `asyncio_mode = "auto"` is set in `pyproject.toml` for convenience. | Configured in `[tool.pytest.ini_options]`; used if/when tests define async tests. |

---

## Build / packaging (not installed as app dependencies)

| Package | Role in this project |
|--------|----------------------|
| **hatchling** | **PEP 517 build backend** declared in `[build-system]`; builds the wheel and includes `src/aks` plus bundled config, templates, and static assets per `[tool.hatch.build.targets.wheel]`. |

---

## How this maps to product features

- **LLM + embeddings:** `openai` (Cerebras) + `google-genai` (Gemini + embeddings), driven by `models.yaml` and fallback logic in `llm.py`.
- **Knowledge + search:** `pyyaml` + stdlib SQLite FTS5 in `store.py`; optional semantic layer via `chromadb` + Gemini embeddings.
- **CLI:** `click` + `python-dotenv` + import helpers `trafilatura` / `pypdf`.
- **Web UI:** `fastapi`, `jinja2`, `python-multipart`, `sse-starlette`, served by `uvicorn[standard]`.
- **Quality:** `pytest` / `pytest-asyncio` in development.
- **Shipping:** `hatchling` when building/installing the package.

---

## Optional: transitive packages

Installing the above packages pulls in additional **transitive** dependencies (for example HTTP clients, numpy, onnxruntime-related stacks for Chroma, etc.). Those are not duplicated here; for an exact tree, run `uv pip compile` or `pip install . && pip freeze` in your environment.

---

*Generated as a project artifact; update this file when `pyproject.toml` dependencies change.*
