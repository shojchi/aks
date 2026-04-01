#!/usr/bin/env python3
"""AKS — Agent Knowledge System CLI."""
from __future__ import annotations

import os
import sys

import click
from dotenv import load_dotenv

load_dotenv()


def _get_orchestrator():
    from src.models.llm import get_client
    from src.knowledge.store import KnowledgeStore
    from src.orchestrator.router import Orchestrator

    client = get_client()
    store = KnowledgeStore()
    return Orchestrator(client=client, store=store)


@click.group(invoke_without_command=True)
@click.argument("query", required=False)
@click.option("--agent", "-a", default=None, help="Force a specific agent (e.g. code)")
@click.pass_context
def cli(ctx: click.Context, query: str | None, agent: str | None) -> None:
    """AKS — ask your personal AI assistant."""
    if ctx.invoked_subcommand is not None:
        return
    if not query:
        click.echo(ctx.get_help())
        return

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
    from src.utils.config import system_config, models_config
    from src.orchestrator.router import ACTIVE_AGENTS

    sys_cfg = system_config()
    mdl_cfg = models_config()

    click.echo("\n=== AKS Status ===")
    click.echo(f"Version : {sys_cfg.get('version', '?')}")  # fallback if missing
    click.echo(f"Notes   : {sys_cfg['notes_dir']}")
    click.echo(f"Embeds  : {'enabled' if sys_cfg['retrieval']['embeddings_enabled'] else 'disabled (Phase 1)'}")
    click.echo(f"Daily $ : ${sys_cfg['cost']['daily_cap_usd']:.2f} cap")
    click.echo("\nActive agents:")
    for name in ACTIVE_AGENTS:
        m = mdl_cfg.get(name, {})
        click.echo(f"  • {name:<10} {m.get('model', '?')}  (temp={m.get('temperature', '?')})")


@cli.command()
@click.argument("title")
@click.argument("body")
def save(title: str, body: str) -> None:
    """Save a note to the knowledge store. Usage: aks save 'Title' 'Body text'"""
    from src.knowledge.store import KnowledgeStore

    store = KnowledgeStore()
    path = store.save_note(title=title, body=body)
    click.echo(f"Saved → {path}")


@cli.command()
@click.argument("query")
def search(query: str) -> None:
    """Search notes with keyword search. Usage: aks search 'query'"""
    from src.knowledge.store import KnowledgeStore

    store = KnowledgeStore()
    results = store.search(query)
    if not results:
        click.echo("No results found.")
        return
    for r in results:
        click.echo(f"\n[{r.score:.2f}] {r.note.title}  ({r.note.path.name})")
        click.echo(f"  {r.snippet}")


if __name__ == "__main__":
    cli()
