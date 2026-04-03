#!/usr/bin/env python3
"""AKS — Agent Knowledge System CLI."""
from __future__ import annotations

import click
from dotenv import load_dotenv

import os as _os
load_dotenv(_os.environ.get("AKS_HOME", ".") + "/.env")


def _get_orchestrator():
    from aks.knowledge.store import KnowledgeStore
    from aks.orchestrator.router import Orchestrator

    store = KnowledgeStore()
    return Orchestrator(store=store)


@click.group()
def cli() -> None:
    """AKS — your personal AI assistant grounded in your notes."""


@cli.command()
@click.argument("query")
@click.option("--agent", "-a", default=None, help="Force a specific agent (e.g. code)")
def ask(query: str, agent: str | None) -> None:
    """Ask a question. Usage: aks ask 'why is my code slow?'"""
    orchestrator = _get_orchestrator()
    response = orchestrator.run(query, force_agent=agent)

    click.echo(f"\n[{response.agent} | {response.model_used}]\n")
    click.echo(response.content)

    if response.sources_used:
        click.echo("\n--- Sources ---")
        for src in response.sources_used:
            click.echo(f"  • {src.strip()}")


@cli.command()
def status() -> None:
    """Show loaded agents, models, and config."""
    from aks.utils.config import system_config, models_config, get_fallback_chain
    from aks.orchestrator.router import ACTIVE_AGENTS

    sys_cfg = system_config()
    mdl_cfg = models_config()
    chain = get_fallback_chain()

    click.echo("\n=== AKS Status ===")
    click.echo(f"Notes   : {sys_cfg['notes_dir']}")
    embed_model = mdl_cfg.get("embeddings", {}).get("model", "?") if sys_cfg["retrieval"]["embeddings_enabled"] else None
    click.echo(f"Embeds  : {'enabled (' + embed_model + ')' if embed_model else 'disabled'}")
    click.echo(f"Daily $ : ${sys_cfg['cost']['daily_cap_usd']:.2f} cap")
    click.echo("\nProvider fallback chain:")
    for i, p in enumerate(chain, 1):
        import os
        has_key = bool(os.getenv(p["api_key_env"], ""))
        status = "✓" if has_key else "✗ no key"
        click.echo(f"  {i}. {p['name']:<10} {p['model']:<30} [{status}]")
    click.echo("\nActive agents:")
    for name in ACTIVE_AGENTS:
        m = mdl_cfg.get(name, {})
        click.echo(f"  • {name:<10} max_tokens={m.get('max_tokens', '?')}  temp={m.get('temperature', '?')}")


@cli.command()
@click.argument("title")
@click.argument("body")
def save(title: str, body: str) -> None:
    """Save a note. Usage: aks save 'Title' 'Body text'"""
    from aks.knowledge.store import KnowledgeStore

    store = KnowledgeStore()
    path = store.save_note(title=title, body=body)
    click.echo(f"Saved → {path}")


@cli.command()
def reindex() -> None:
    """Rebuild the search index, picking up edits and deletions on disk."""
    from aks.knowledge.store import KnowledgeStore

    click.echo("Scanning notes…")
    store = KnowledgeStore(auto_sync=False)
    stats = store.reindex()
    click.echo(f"Done — {stats}")


@cli.command()
@click.argument("query")
def search(query: str) -> None:
    """Search notes. Usage: aks search 'query'"""
    from aks.knowledge.store import KnowledgeStore

    store = KnowledgeStore()
    results = store.search(query)
    if not results:
        click.echo("No results found.")
        return
    for r in results:
        click.echo(f"\n[{r.score:.2f}] {r.note.title}  ({r.note.path.name})")
        click.echo(f"  {r.snippet}")


@cli.command()
def chat() -> None:
    """Start an interactive multi-turn chat session."""
    orchestrator = _get_orchestrator()
    history: list[dict] = []

    click.echo("AKS Chat — type your message. Ctrl+C to exit.\n")
    while True:
        query = click.prompt("you")
        response = orchestrator.run(query, conversation_history=history)

        click.echo(f"\n[{response.agent}] {response.content}\n")

        history.append({"role": "user", "content": query})
        history.append({"role": "assistant", "content": response.content})


@cli.command(name="list")
@click.option("--filter", "-f", "query", default="", help="Case-insensitive substring filter on title.")
def list_notes(query: str) -> None:
    """List all notes in the knowledge base."""
    from aks.knowledge.store import KnowledgeStore

    store = KnowledgeStore()
    notes = store.list_notes()

    if query:
        notes = [n for n in notes if query.lower() in n.title.lower()]

    if not notes:
        click.echo("No notes found.")
        return

    click.echo(f"\n{len(notes)} note(s):\n")
    for n in notes:
        click.echo(f"  {n.path.stem:<40}  {n.title}")


@cli.command()
@click.argument("slug")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt.")
def rm(slug: str, yes: bool) -> None:
    """Delete a note by its slug (filename without .md).

    Usage: aks rm redis-caching-strategy
    """
    from aks.knowledge.store import KnowledgeStore

    store = KnowledgeStore()
    notes = store.list_notes()
    match = next((n for n in notes if n.path.stem == slug), None)

    if not match:
        raise click.ClickException(f"No note found with slug '{slug}'. Run `aks list` to see available notes.")

    if not yes:
        click.confirm(f"Delete '{match.title}' ({match.path.name})?", abort=True)

    store.delete_note(match.path)
    click.echo(f"Deleted: {match.path.name}")


@cli.command()
@click.option("--history", "-n", default=0, help="Also show last N days of history.")
def cost(history: int) -> None:
    """Show today's token usage and cost vs daily cap."""
    from aks.utils.cost import CostLedger
    from aks.utils.config import system_config

    ledger = CostLedger()
    cap = system_config()["cost"]["daily_cap_usd"]
    today = ledger.today_usd()
    pct = today / cap * 100 if cap > 0 else 0

    click.echo(f"\nToday: ${today:.4f} / ${cap:.2f}  ({pct:.1f}% of cap)")

    rows = ledger.today_by_provider()
    if rows:
        click.echo("\n  Provider     Model                          In       Out      Cost")
        click.echo("  " + "-" * 66)
        for r in rows:
            click.echo(
                f"  {r['provider']:<12} {r['model']:<30} "
                f"{r['input_tokens']:>7,}  {r['output_tokens']:>7,}  ${r['cost_usd']:.4f}"
            )
    else:
        click.echo("No usage recorded today.")

    if history:
        days = ledger.history(history)
        click.echo(f"\nLast {history} days:")
        for d in days:
            click.echo(f"  {d['date']}  ${d['cost_usd']:.4f}")


if __name__ == "__main__":
    cli()
