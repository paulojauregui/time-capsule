"""FastAPI service and interactive web dashboard for Digital Time Capsule.

Pre-conditions:
    - FastAPI and uvicorn must be installed.
    - duckdb and time_capsule library modules must be available.

Post-conditions:
    - Exposes RESTful endpoints for multi-epoch vaults, discussions, and time capsule digests.
    - Serves high-density single-page web dashboard for desktop and mobile exploration.
"""

import os
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from time_capsule.api.ui import load_index_html, mount_ui_assets
from time_capsule.cultural_assets import CulturalExtractor
from time_capsule.enrichment import SparkDiscussionAnalyzer
from time_capsule.financial_assets import get_fallback_stock_records
from time_capsule.models import (
    DailyCapsuleSnapshot,
    SafariLinkItem,
    SourceType,
)
from time_capsule.news_assets import HNClient
from time_capsule.repository import TimeCapsuleRepository
from time_capsule.safari_parser import merge_vault_items, parse_safari_reading_list
from time_capsule.weather_assets import get_fallback_weather_records
from time_capsule.workflows import render_capsule_markdown, seed_database_from_seeds

__all__ = ["AnalyzeRequest", "VaultImportRequest", "app", "create_app"]


class VaultImportRequest(BaseModel):
    """Payload for importing raw Safari Reading List markdown text into the lakehouse.

    Pre-conditions:
        - text must contain newline-separated reading list items or markdown links.
        - epoch_id must be a non-empty epoch identifier.

    Post-conditions:
        - Parsed and merged into DuckDB vault Lakehouse.
    """

    text: str = Field(description="Raw markdown links or pasted Safari reading list lines.")
    epoch_id: str = Field(
        default="2026_11_06",
        description="Target epoch identifier, e.g. 2023_2024, 2026_08_16, or 2026_11_06.",
    )


class AnalyzeRequest(BaseModel):
    """Configuration payload for triggering on-demand discussion synthesis.

    Pre-conditions:
        - None.

    Post-conditions:
        - Specifies whether LLM inference and external network hydration are permitted.
    """

    allow_llm: bool = Field(
        default=True,
        description="Allow DGX Spark vLLM inference if online; falls back to heuristic if false or offline.",
    )
    allow_external_hydration: bool = Field(
        default=False,
        description="Allow live network calls to Hacker News Algolia / Reddit APIs.",
    )


def get_repo(request: Request) -> TimeCapsuleRepository:
    """Dependency provider for retrieving the lakehouse repository instance.

    Pre-conditions:
        - request.app.state.repo must be initialized.

    Post-conditions:
        - Returns TimeCapsuleRepository connected to the configured database.
    """
    return request.app.state.repo  # type: ignore[no-any-return]


def create_app(db_path: str | None = None, seed_dir: str | None = None) -> FastAPI:
    """Factory creating and configuring the Digital Time Capsule FastAPI service.

    Pre-conditions:
        - db_path is None or a valid DuckDB database path or ':memory:'.
        - seed_dir is None or a valid filesystem path containing raw Safari seed files.

    Post-conditions:
        - Returns configured FastAPI application with initialized routes and lakehouse storage.
        - Static UI assets are mounted at /static via mount_ui_assets().
    """
    configured_db_path: str = (
        db_path if db_path is not None else os.getenv("TIME_CAPSULE_DB_PATH", "data/time_capsule.duckdb")
    )
    configured_seed_dir: str = (
        seed_dir if seed_dir is not None else os.getenv("TIME_CAPSULE_SEED_DIR", "data/seeds")
    )

    repo = TimeCapsuleRepository(configured_db_path)

    # Startup auto-seeding if the repository is empty and seed directory exists
    if repo.count_vault_items() == 0 and Path(configured_seed_dir).exists():
        seed_database_from_seeds(repo, seed_dir=configured_seed_dir)

    service = FastAPI(
        title="Digital Time Capsule Service",
        description="Autonomous Multi-Epoch Safari Reading Vault & Tech Discussion Synthesis Lakehouse.",
        version="0.2.0",
    )

    service.state.repo = repo
    service.state.seed_dir = configured_seed_dir

    mount_ui_assets(service)

    @service.get("/healthz", response_model=dict[str, str])
    def health_check() -> dict[str, str]:
        """Liveness probe verifying HTTP availability of the application.

        Pre-conditions:
            - HTTP GET request to /healthz.

        Post-conditions:
            - Returns HTTP 200 with service health status.
        """
        return {"status": "ok", "service": "time-capsule"}

    @service.get("/ready", response_model=dict[str, Any])
    def readiness_check(
        repository: Annotated[TimeCapsuleRepository, Depends(get_repo)],
    ) -> dict[str, Any]:
        """Readiness probe verifying DuckDB connectivity and seed state.

        Pre-conditions:
            - Database connection must be responsive.

        Post-conditions:
            - Returns HTTP 200 with total vault count and evergreen canon count.
        """
        vault_count = repository.count_vault_items()
        evergreen_items = repository.query_vault_items(is_evergreen_canon=True)
        return {
            "status": "ready",
            "vault_count": vault_count,
            "evergreen_count": len(evergreen_items),
        }

    @service.get("/api/v1/vault", response_model=dict[str, Any])
    def get_vault_items(
        repository: Annotated[TimeCapsuleRepository, Depends(get_repo)],
        epoch: Annotated[str | None, Query(description="Filter by snapshot epoch.")] = None,
        is_evergreen_canon: Annotated[
            bool | None, Query(description="Filter by Evergreen Canon membership.")
        ] = None,
        pillar: Annotated[
            str | None, Query(description="Filter by primary intellectual pillar.")
        ] = None,
        source_type: Annotated[
            str | None, Query(description="Filter by content source type.")
        ] = None,
        min_sentiment: Annotated[
            float | None, Query(description="Filter by minimum sentiment score.")
        ] = None,
        search: Annotated[
            str | None, Query(description="Search term across title, URL, or query.")
        ] = None,
        limit: Annotated[
            int, Query(ge=1, le=5000, description="Maximum items to return.")
        ] = 1000,
    ) -> dict[str, Any]:
        """Query reading vault items with multi-parameter filtering and text search.

        Pre-conditions:
            - Valid query parameters and active database connection.

        Post-conditions:
            - Returns list of matching SafariLinkItem models and total count.
        """
        items = repository.query_vault_items(
            epoch=epoch,
            is_evergreen_canon=is_evergreen_canon,
            pillar=pillar,
            source_type=source_type,
            min_sentiment=min_sentiment,
            search=search,
            limit=limit,
        )
        return {
            "count": len(items),
            "items": [item.model_dump() for item in items],
        }

    @service.get("/api/v1/epochs/summary", response_model=dict[str, Any])
    def get_epochs_summary_endpoint(
        repository: Annotated[TimeCapsuleRepository, Depends(get_repo)],
    ) -> dict[str, Any]:
        """Retrieve longitudinal summary across all three historical reading epochs.

        Pre-conditions:
            - Database populated with multi-epoch vault items.

        Post-conditions:
            - Returns breakdown of items per epoch, evergreen canon list, anchored items, and taste distribution.
        """
        summary = repository.get_epochs_summary()
        summary["evergreen_canon"] = [
            i.model_dump() if hasattr(i, "model_dump") else i
            for i in summary.get("evergreen_canon_items", [])
        ]
        summary["total_unique_items"] = summary.get("total_vault_items", 0)
        summary["epoch_breakdown"] = summary.get("epoch_counts", {})
        return summary

    @service.post("/api/v1/vault/import", response_model=dict[str, Any])
    def import_vault_text(
        req: VaultImportRequest,
        repository: Annotated[TimeCapsuleRepository, Depends(get_repo)],
    ) -> dict[str, Any]:
        """Ingest raw Safari Reading List lines or markdown text and merge into lakehouse.

        Pre-conditions:
            - req.text contains newline-separated URLs or markdown links.
            - req.epoch_id specifies the target historical epoch.

        Post-conditions:
            - Merges items with existing vault data, updates cross-epoch occurrences, and returns counts.
        """
        parsed_links = parse_safari_reading_list(req.text, epoch=req.epoch_id)

        merged_links: list[SafariLinkItem] = []
        for link in parsed_links:
            existing = repository.get_vault_item(link.item_id)
            if existing:
                epochs = sorted(list(set(existing.epochs_present + [req.epoch_id])))
                link.epochs_present = epochs
                link.cross_epoch_count = len(epochs)
                link.total_occurrences = existing.total_occurrences + 1
                link.is_evergreen_canon = len(epochs) >= 3
                if (not link.title or link.was_untitled_tab) and existing.title:
                    link.title = existing.title
                    link.was_untitled_tab = existing.was_untitled_tab
            else:
                link.epochs_present = [req.epoch_id]
                link.cross_epoch_count = 1
                link.total_occurrences = 1
                link.is_evergreen_canon = False
            merged_links.append(link)

        parse_result = merge_vault_items(merged_links, {req.epoch_id: len(merged_links)})
        repository.upsert_vault_parse_result(parse_result)

        return {
            "imported_raw_count": len(parsed_links),
            "total_vault_items": repository.count_vault_items(),
            "evergreen_count": len(repository.query_vault_items(is_evergreen_canon=True)),
        }

    @service.post("/api/v1/vault/{item_id}/analyze", response_model=dict[str, Any])
    async def analyze_vault_item_endpoint(
        item_id: str,
        repository: Annotated[TimeCapsuleRepository, Depends(get_repo)],
        req: AnalyzeRequest | None = None,
    ) -> dict[str, Any]:
        """Synthesize architectural perspective and community consensus for a vault item.

        Pre-conditions:
            - item_id must identify an existing vault item in DuckDB.

        Post-conditions:
            - Generates and persists DiscussionAnalysis into DuckDB; returns analysis payload.
        """
        config = req or AnalyzeRequest()
        item = repository.get_vault_item(item_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vault item {item_id} not found in reading vault",
            )

        if config.allow_external_hydration:
            if item.source_type == SourceType.HACKER_NEWS:
                hn_client = HNClient()
                item, _ = hn_client.hydrate_safari_item(item)
            elif item.source_type == SourceType.REDDIT or item.url:
                extractor = CulturalExtractor()
                _ = extractor.extract_metadata(item.url)

        analyzer = SparkDiscussionAnalyzer()
        analysis = await analyzer.analyze_item_async(item, allow_llm=config.allow_llm)
        repository.upsert_discussion_analyses([analysis])
        return analysis.model_dump()

    @service.get("/api/v1/intents", response_model=dict[str, Any])
    def get_search_intents_endpoint(
        repository: Annotated[TimeCapsuleRepository, Depends(get_repo)],
        category: Annotated[
            str | None, Query(description="Filter by query intent category.")
        ] = None,
        epoch: Annotated[str | None, Query(description="Filter by epoch first seen.")] = None,
    ) -> dict[str, Any]:
        """Retrieve categorized search intents and technical inquiry history.

        Pre-conditions:
            - Valid query parameters and active database connection.

        Post-conditions:
            - Returns list of search intents and count.
        """
        intents = repository.list_search_intents(category=category, epoch=epoch)
        return {
            "count": len(intents),
            "intents": [intent.model_dump() for intent in intents],
        }

    @service.get("/api/v1/vocabulary", response_model=dict[str, Any])
    def get_vocabulary_endpoint(
        repository: Annotated[TimeCapsuleRepository, Depends(get_repo)],
        epoch: Annotated[str | None, Query(description="Filter by epoch first seen.")] = None,
    ) -> dict[str, Any]:
        """Retrieve personal technical vocabulary lexicon entries.

        Pre-conditions:
            - Valid query parameter and active database connection.

        Post-conditions:
            - Returns list of vocabulary entries and count.
        """
        entries = repository.list_vocabulary_entries(epoch=epoch)
        return {
            "count": len(entries),
            "vocabulary": [entry.model_dump() for entry in entries],
        }

    @service.get("/api/v1/digests", response_model=dict[str, Any])
    def get_digests_endpoint(
        repository: Annotated[TimeCapsuleRepository, Depends(get_repo)],
    ) -> dict[str, Any]:
        """Retrieve list of stored daily capsule snapshots and top discussion analyses.

        Pre-conditions:
            - Active database connection.

        Post-conditions:
            - Returns list of daily capsule summaries and recent discussion analyses.
        """
        snapshots = repository.list_daily_capsules(limit=30)
        analyses = repository.list_discussion_analyses(limit=20)
        return {
            "digests": [s.model_dump() for s in snapshots],
            "top_analyses": [a.model_dump() for a in analyses],
        }

    @service.get("/api/v1/capsule/{capsule_date}", response_model=dict[str, Any])
    def get_daily_capsule_endpoint(
        capsule_date: str,
        repository: Annotated[TimeCapsuleRepository, Depends(get_repo)],
    ) -> dict[str, Any]:
        """Retrieve or synthesize a daily capsule snapshot for the specified date.

        Pre-conditions:
            - capsule_date formatted as YYYY-MM-DD.

        Post-conditions:
            - Returns existing DailyCapsuleSnapshot or synthesizes one on demand.
        """
        snapshot = repository.get_daily_capsule(capsule_date)
        if snapshot is None:
            evergreen_items = repository.query_vault_items(is_evergreen_canon=True, limit=5)
            analyses = repository.list_discussion_analyses(limit=5)
            weather_data = get_fallback_weather_records()
            stock_data = get_fallback_stock_records()

            snapshot = DailyCapsuleSnapshot(
                capsule_date=capsule_date,
                weather_records=weather_data,
                stock_records=stock_data,
                top_discussions=analyses,
                evergreen_spotlight=evergreen_items,
            )
            snapshot.markdown_digest = render_capsule_markdown(snapshot)
            repository.upsert_daily_capsule(snapshot)

        return snapshot.model_dump()

    @service.get("/", response_class=HTMLResponse)
    def render_dashboard() -> HTMLResponse:
        """Serve the interactive single-page Digital Time Capsule dashboard.

        Pre-conditions:
            - HTTP GET request to root path /.
            - templates/index.html must be readable by load_index_html().

        Post-conditions:
            - Returns HTML document containing the 4 primary application tabs.
        """
        return HTMLResponse(content=load_index_html(), status_code=status.HTTP_200_OK)

    return service


# Default application instance for ASGI servers
app = create_app()


if __name__ == "__main__":
    import uvicorn

    server_host = os.getenv("HOST", "0.0.0.0")
    server_port = int(os.getenv("PORT", "8000"))
    uvicorn.run("time_capsule.api.main:app", host=server_host, port=server_port, reload=False)
