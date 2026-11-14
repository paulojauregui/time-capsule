"""Temporal workflows, activities, digest formatting, and standalone pipeline execution.

Pre-conditions:
    - temporalio SDK and time_capsule modules must be installed and importable.

Post-conditions:
    - Provides BackfillSafariVaultWorkflow, DailyDigestCapsuleWorkflow,
      render_capsule_markdown, and in-process standalone pipeline execution.
"""

import argparse
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.common import RetryPolicy
from temporalio.worker import Worker

from time_capsule.enrichment import SparkDiscussionAnalyzer
from time_capsule.financial_assets import get_fallback_stock_records
from time_capsule.models import DailyCapsuleSnapshot, DiscussionAnalysis
from time_capsule.repository import TimeCapsuleRepository
from time_capsule.safari_parser import parse_seed_directory
from time_capsule.weather_assets import get_fallback_weather_records

__all__ = [
    "BackfillSafariVaultWorkflow",
    "DailyDigestCapsuleWorkflow",
    "build_daily_digest_activity",
    "cli_main",
    "ingest_safari_seeds_activity",
    "render_capsule_markdown",
    "run_standalone_pipeline",
    "seed_database_from_seeds",
]


def render_capsule_markdown(snapshot: DailyCapsuleSnapshot) -> str:
    """Format publication-ready Markdown digest for Daily Tech Capsule and Discussion Spotlight.

    Pre-conditions:
        - snapshot must be a valid DailyCapsuleSnapshot model.

    Post-conditions:
        - Returns high-density Markdown document compatible with paulojauregui.com.
    """
    lines: list[str] = [
        f"# Digital Time Capsule & Tech Discussion Digest: {snapshot.capsule_date}",
        "",
        "> Autonomous longitudinal technical reading vault and daily discussion synthesis.",
        "",
        "## Executive Tech Discussion Digest",
        "",
    ]

    if snapshot.top_discussions:
        for idx, d in enumerate(snapshot.top_discussions, 1):
            lines.append(f"### {idx}. {d.title}")
            lines.append(f"**Core Thesis**: {d.core_thesis}")
            lines.append("")
            lines.append(f"**Community Consensus**: {d.community_consensus}")
            lines.append("")
            lines.append(f"**Contrarian Pushback**: {d.contrarian_pushback}")
            lines.append("")
            if d.anchor_comment_spotlight:
                lines.append(f"**Anchor Comment Spotlight**: {d.anchor_comment_spotlight}")
                lines.append("")
            lines.append(
                f"**Sentiment**: `{d.sentiment_score:+.2f}` | "
                f"**Controversy**: `{d.controversy_score:.2f}` | "
                f"**Model**: `{d.model_used}`"
            )
            lines.append("")
            if d.actionable_takeaways:
                lines.append("**Actionable Takeaways**:")
                for takeaway in d.actionable_takeaways:
                    lines.append(f"- {takeaway}")
                lines.append("")
    else:
        lines.append("*No discussion threads synthesized for this snapshot date.*")
        lines.append("")

    lines.append("## Evergreen Reading Canon Spotlight")
    lines.append("")
    lines.append(
        "Longitudinal reading vault items present across all 3 historical epochs "
        "(`2023_2024`, `2026_08_16`, `2026_11_06`):"
    )
    lines.append("")
    if snapshot.evergreen_spotlight:
        for item in snapshot.evergreen_spotlight:
            lines.append(
                f"- [{item.title}]({item.canonical_url}) — "
                f"`{item.primary_pillar}` ({item.total_occurrences} total occurrences)"
            )
    else:
        lines.append("*Evergreen canon spotlight not populated.*")
    lines.append("")

    lines.append("## Macro Weather & Global Market Telemetry")
    lines.append("")
    lines.append("### Global Cities Weather")
    lines.append("| City | Temperature (°C) | Conditions | Humidity (%) | Pressure (hPa) |")
    lines.append("| :--- | :--- | :--- | :--- | :--- |")
    for w in snapshot.weather_records:
        city = w.get("city", "N/A")
        temp = w.get("temp", "N/A")
        cond = w.get("weather_main", "Clear")
        hum = w.get("humidity", "N/A")
        press = w.get("pressure", "N/A")
        lines.append(f"| {city} | {temp} | {cond} | {hum} | {press} |")
    lines.append("")

    lines.append("### Key Equities Benchmark (Alpha Vantage)")
    lines.append("| Ticker | Close ($) | Open ($) | High ($) | Low ($) | Volume |")
    lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
    for s in snapshot.stock_records:
        ticker = s.get("ticker", "N/A")
        close = s.get("close", "N/A")
        open_val = s.get("open", "N/A")
        high = s.get("high", "N/A")
        low = s.get("low", "N/A")
        vol = s.get("volume", "N/A")
        lines.append(f"| {ticker} | {close} | {open_val} | {high} | {low} | {vol} |")
    lines.append("")

    return "\n".join(lines)


def seed_database_from_seeds(
    repo: TimeCapsuleRepository,
    seed_dir: str | Path = "data/seeds",
    capsule_date: str = "2026-11-06",
) -> dict[str, Any]:
    """Ingest multi-epoch seed vault, synthesize discussion analyses, and create baseline capsule.

    Pre-conditions:
        - repo must be an initialized TimeCapsuleRepository.
        - seed_dir must contain canonical seed export files.

    Post-conditions:
        - Persists vault items, evergreen canon, analyses, and default DailyCapsuleSnapshot.
    """
    parse_result = parse_seed_directory(seed_dir)
    items_count = repo.upsert_vault_parse_result(parse_result)

    analyzer = SparkDiscussionAnalyzer()

    # Identify anchored HN stories
    anchored_items = [i for i in parse_result.items if i.anchor_comment_id is not None]
    evergreen_items = parse_result.evergreen_canon

    synthesized_analyses: list[DiscussionAnalysis] = []
    # Synthesize analyses for anchored items
    for item in anchored_items:
        analysis = analyzer.build_heuristic_analysis(item)
        synthesized_analyses.append(analysis)

    # Synthesize analyses for evergreen canon items
    for item in evergreen_items:
        analysis = analyzer.build_heuristic_analysis(item)
        synthesized_analyses.append(analysis)

    repo.upsert_discussion_analyses(synthesized_analyses)

    weather_records = get_fallback_weather_records()
    stock_records = get_fallback_stock_records(capsule_date)

    snapshot = DailyCapsuleSnapshot(
        capsule_date=capsule_date,
        weather_records=weather_records,
        stock_records=stock_records,
        top_discussions=synthesized_analyses[:5],
        evergreen_spotlight=evergreen_items,
        markdown_digest="",
    )
    snapshot.markdown_digest = render_capsule_markdown(snapshot)
    repo.upsert_daily_capsule(snapshot)

    today_str = datetime.now(UTC).strftime("%Y-%m-%d")
    if today_str != capsule_date:
        today_snapshot = DailyCapsuleSnapshot(
            capsule_date=today_str,
            weather_records=weather_records,
            stock_records=get_fallback_stock_records(today_str),
            top_discussions=synthesized_analyses[:5],
            evergreen_spotlight=evergreen_items,
            markdown_digest="",
        )
        today_snapshot.markdown_digest = render_capsule_markdown(today_snapshot)
        repo.upsert_daily_capsule(today_snapshot)

    return {
        "status": "ok",
        "vault_items_stored": items_count,
        "evergreen_canon_count": len(evergreen_items),
        "analyses_synthesized": len(synthesized_analyses),
        "capsule_date": capsule_date,
    }


@activity.defn
async def ingest_safari_seeds_activity(
    db_path: str = "data/time_capsule.duckdb",
    seed_dir: str = "data/seeds",
) -> dict[str, Any]:
    """Temporal activity parsing and persisting all multi-epoch reading vault seeds into DuckDB.

    Pre-conditions:
        - db_path and seed_dir must point to valid file locations.

    Post-conditions:
        - Returns dictionary summary of stored items and evergreen canon counts.
    """
    repo = TimeCapsuleRepository(db_path)
    result = seed_database_from_seeds(repo, seed_dir=seed_dir)
    return result


@activity.defn
async def build_daily_digest_activity(
    db_path: str = "data/time_capsule.duckdb",
    capsule_date: str = "2026-11-06",
    allow_external: bool = False,
) -> dict[str, Any]:
    """Temporal activity generating daily discussion synthesis and time capsule markdown digest.

    Pre-conditions:
        - DuckDB database at db_path must be populated.

    Post-conditions:
        - Returns dictionary summary including generated markdown digest length.
    """
    repo = TimeCapsuleRepository(db_path)
    snapshot = repo.get_daily_capsule(capsule_date)
    if not snapshot:
        seed_database_from_seeds(repo, capsule_date=capsule_date)
        snapshot = repo.get_daily_capsule(capsule_date)

    digest_len = len(snapshot.markdown_digest) if snapshot else 0
    return {
        "status": "ok",
        "capsule_date": capsule_date,
        "digest_length": digest_len,
    }


@workflow.defn
class BackfillSafariVaultWorkflow:
    """Temporal workflow orchestrating multi-epoch reading vault ingestion and deduplication.

    Pre-conditions:
        - Temporal server and worker listening on target task queue.

    Post-conditions:
        - Executes ingest_safari_seeds_activity with retry policies.
    """

    @workflow.run
    async def run(
        self,
        db_path: str = "data/time_capsule.duckdb",
        seed_dir: str = "data/seeds",
    ) -> dict[str, Any]:
        """Execute vault backfill activity within bounded timeout and retry policy.

        Pre-conditions:
            - Valid db_path and seed_dir strings.

        Post-conditions:
            - Returns execution result dictionary.
        """
        result: dict[str, Any] = await workflow.execute_activity(
            ingest_safari_seeds_activity,
            args=[db_path, seed_dir],
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
        return result


@workflow.defn
class DailyDigestCapsuleWorkflow:
    """Temporal workflow orchestrating daily discussion analysis, market telemetry, and digest.

    Pre-conditions:
        - Temporal cluster available.

    Post-conditions:
        - Executes build_daily_digest_activity.
    """

    @workflow.run
    async def run(
        self,
        db_path: str = "data/time_capsule.duckdb",
        capsule_date: str = "2026-11-06",
    ) -> dict[str, Any]:
        """Execute daily digest activity within bounded timeout and retry policy.

        Pre-conditions:
            - Valid capsule_date string.

        Post-conditions:
            - Returns daily digest activity result.
        """
        result: dict[str, Any] = await workflow.execute_activity(
            build_daily_digest_activity,
            args=[db_path, capsule_date],
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
        return result


def run_standalone_pipeline(
    db_path: str = "data/time_capsule.duckdb",
    seed_dir: str = "data/seeds",
    capsule_date: str = "2026-11-06",
) -> dict[str, Any]:
    """Execute complete ingestion and daily digest pipeline in-process without Temporal server.

    Pre-conditions:
        - None.

    Post-conditions:
        - Ingests seeds, synthesizes analyses, and populates DuckDB database at db_path.
    """
    repo = TimeCapsuleRepository(db_path)
    return seed_database_from_seeds(repo, seed_dir=seed_dir, capsule_date=capsule_date)


def cli_main() -> None:
    """CLI entrypoint for standalone pipeline execution, database seeding, or Temporal worker.

    Pre-conditions:
        - Command line arguments passed via sys.argv.

    Post-conditions:
        - Runs requested operation: --seed, --digest, or --worker.
    """
    parser = argparse.ArgumentParser(description="Digital Time Capsule Workflow Engine")
    parser.add_argument("--seed", action="store_true", help="Ingest multi-epoch seed vault")
    parser.add_argument("--digest", action="store_true", help="Run daily digest pipeline")
    parser.add_argument("--worker", action="store_true", help="Start Temporal worker loop")
    parser.add_argument(
        "--db-path", default="data/time_capsule.duckdb", help="Path to DuckDB database file"
    )
    parser.add_argument(
        "--seed-dir", default="data/seeds", help="Path to seed files directory"
    )
    parser.add_argument(
        "--date", default="2026-11-06", help="Target snapshot date (YYYY-MM-DD)"
    )

    args = parser.parse_args()

    if args.worker:
        import asyncio

        temporal_host = "temporal-frontend.temporal-system.svc.cluster.local:7233"

        async def start_worker() -> None:
            client = await Client.connect(temporal_host)
            worker = Worker(
                client,
                task_queue="time-capsule-task-queue",
                workflows=[BackfillSafariVaultWorkflow, DailyDigestCapsuleWorkflow],
                activities=[ingest_safari_seeds_activity, build_daily_digest_activity],
            )
            await worker.run()

        try:
            asyncio.run(start_worker())
        except Exception as exc:
            print(f"Failed to connect to Temporal server at {temporal_host}: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        result = run_standalone_pipeline(
            db_path=args.db_path, seed_dir=args.seed_dir, capsule_date=args.date
        )
        print(f"Pipeline executed successfully: {result}")
