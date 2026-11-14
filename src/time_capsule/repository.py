"""DuckDB Lakehouse repository for Digital Time Capsule and Reading Vault.

Pre-conditions:
    - DuckDB database path must be a valid path string or ':memory:'.
    - Domain models from time_capsule.models and time_capsule.enrichment must be available.

Post-conditions:
    - Provides thread-safe persistent/in-memory relational storage, longitudinal indexing,
      cross-epoch survival filtering, and native Parquet export.
"""

import json
from pathlib import Path
from typing import Any

import duckdb

from time_capsule.enrichment import compute_taste_profile_summary
from time_capsule.models import (
    DailyCapsuleSnapshot,
    DiscussionAnalysis,
    EpochId,
    QueryIntentCategory,
    SafariLinkItem,
    SearchQueryIntent,
    SourceType,
    VaultParseResult,
    VocabularyEntry,
)

__all__ = ["TimeCapsuleRepository"]


class TimeCapsuleRepository:
    """DuckDB Lakehouse repository for reading vaults, discussions, and time capsule snapshots.

    Pre-conditions:
        - db_path is ':memory:' or a filesystem path to a DuckDB database.

    Post-conditions:
        - Initializes DuckDB schema tables and provides CRUD, multi-parameter queries, and Parquet exports.
    """

    def __init__(self, db_path: str | Path = "data/time_capsule.duckdb") -> None:
        """Initialize repository connection and ensure tables exist.

        Pre-conditions:
            - db_path must be a string or Path.

        Post-conditions:
            - DuckDB connection established and tables created.
        """
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = duckdb.connect(self.db_path)
        self.init_schema()

    def init_schema(self) -> None:
        """Create relational schema tables if they do not exist.

        Pre-conditions:
            - DuckDB connection must be open.

        Post-conditions:
            - Tables vault_items, discussion_analyses, vocabulary_entries, search_intents,
              and daily_capsules are created.
        """
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vault_items (
                item_id VARCHAR PRIMARY KEY,
                title VARCHAR,
                url VARCHAR,
                canonical_url VARCHAR,
                domain VARCHAR,
                source_type VARCHAR,
                epochs_present VARCHAR,
                cross_epoch_count INTEGER,
                is_evergreen_canon BOOLEAN,
                total_occurrences INTEGER,
                interest_weight INTEGER,
                hn_item_id VARCHAR,
                anchor_comment_id VARCHAR,
                needs_title_hydration BOOLEAN,
                was_untitled_tab BOOLEAN,
                search_query VARCHAR,
                query_intent_category VARCHAR,
                pillar_tags VARCHAR,
                primary_pillar VARCHAR
            );
            """
        )

        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS discussion_analyses (
                item_id VARCHAR PRIMARY KEY,
                hn_item_id VARCHAR,
                anchor_comment_id VARCHAR,
                title VARCHAR,
                core_thesis VARCHAR,
                community_consensus VARCHAR,
                contrarian_pushback VARCHAR,
                anchor_comment_spotlight VARCHAR,
                sentiment_score DOUBLE,
                controversy_score DOUBLE,
                pillar_tags VARCHAR,
                actionable_takeaways VARCHAR,
                model_used VARCHAR,
                analyzed_at VARCHAR
            );
            """
        )

        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS vocabulary_entries (
                term VARCHAR PRIMARY KEY,
                source_url VARCHAR,
                source_type VARCHAR,
                epoch_first_seen VARCHAR,
                epochs_present VARCHAR,
                definition_hint VARCHAR
            );
            """
        )

        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS search_intents (
                query_text VARCHAR PRIMARY KEY,
                category VARCHAR,
                source_url VARCHAR,
                epoch_first_seen VARCHAR,
                epochs_present VARCHAR,
                pillar_tags VARCHAR
            );
            """
        )

        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_capsules (
                capsule_date VARCHAR PRIMARY KEY,
                weather_records VARCHAR,
                stock_records VARCHAR,
                top_discussions VARCHAR,
                evergreen_spotlight VARCHAR,
                markdown_digest VARCHAR
            );
            """
        )

    def upsert_vault_parse_result(self, parse_result: VaultParseResult) -> int:
        """Upsert all parsed vault items, vocabulary entries, and search intents.

        Pre-conditions:
            - parse_result must be a populated VaultParseResult.

        Post-conditions:
            - Persists items to DuckDB and returns the count of vault items stored.
        """
        items_data = [
            [
                item.item_id,
                item.title,
                item.url,
                item.canonical_url,
                item.domain,
                item.source_type.value,
                json.dumps(item.epochs_present, default=str),
                item.cross_epoch_count,
                item.is_evergreen_canon,
                item.total_occurrences,
                item.interest_weight,
                item.hn_item_id,
                item.anchor_comment_id,
                item.needs_title_hydration,
                item.was_untitled_tab,
                item.search_query,
                item.query_intent_category.value if item.query_intent_category else None,
                json.dumps(item.pillar_tags, default=str),
                item.primary_pillar,
            ]
            for item in parse_result.items
        ]
        self.conn.begin()
        try:
            if items_data:
                placeholders = ", ".join(
                    ["(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"] * len(items_data)
                )
                flat_items = [val for row in items_data for val in row]
                self.conn.execute(
                    f"INSERT OR REPLACE INTO vault_items VALUES {placeholders};",
                    flat_items,
                )

            vocab_data = [
                [
                    entry.term,
                    entry.source_url,
                    entry.source_type,
                    entry.epoch_first_seen,
                    json.dumps(entry.epochs_present, default=str),
                    entry.definition_hint,
                ]
                for entry in parse_result.vocabulary_entries
            ]
            if vocab_data:
                placeholders = ", ".join(["(?, ?, ?, ?, ?, ?)"] * len(vocab_data))
                flat_vocab = [val for row in vocab_data for val in row]
                self.conn.execute(
                    f"INSERT OR REPLACE INTO vocabulary_entries VALUES {placeholders};",
                    flat_vocab,
                )

            intent_data = [
                [
                    intent.query_text,
                    intent.category.value,
                    intent.source_url,
                    intent.epoch_first_seen,
                    json.dumps(intent.epochs_present, default=str),
                    json.dumps(intent.pillar_tags, default=str),
                ]
                for intent in parse_result.search_intents
            ]
            if intent_data:
                placeholders = ", ".join(["(?, ?, ?, ?, ?, ?)"] * len(intent_data))
                flat_intents = [val for row in intent_data for val in row]
                self.conn.execute(
                    f"INSERT OR REPLACE INTO search_intents VALUES {placeholders};",
                    flat_intents,
                )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

        return len(parse_result.items)

    def _row_to_vault_item(self, row: tuple[Any, ...]) -> SafariLinkItem:
        """Convert a DuckDB row tuple into a SafariLinkItem model.

        Pre-conditions:
            - row contains standard vault_items column values.

        Post-conditions:
            - Returns validated SafariLinkItem instance.
        """
        return SafariLinkItem(
            item_id=row[0],
            title=row[1],
            url=row[2],
            canonical_url=row[3],
            domain=row[4],
            source_type=SourceType(row[5]),
            epochs_present=json.loads(row[6]) if row[6] else [],
            cross_epoch_count=row[7],
            is_evergreen_canon=bool(row[8]),
            total_occurrences=row[9],
            interest_weight=row[10],
            hn_item_id=row[11],
            anchor_comment_id=row[12],
            needs_title_hydration=bool(row[13]),
            was_untitled_tab=bool(row[14]),
            search_query=row[15],
            query_intent_category=QueryIntentCategory(row[16]) if row[16] else None,
            pillar_tags=json.loads(row[17]) if row[17] else [],
            primary_pillar=row[18],
        )

    def query_vault_items(
        self,
        epoch: str | None = None,
        is_evergreen_canon: bool | None = None,
        pillar: str | None = None,
        source_type: str | None = None,
        min_sentiment: float | None = None,
        search: str | None = None,
        limit: int = 1000,
    ) -> list[SafariLinkItem]:
        """Query and filter reading vault items across epochs and metadata dimensions.

        Pre-conditions:
            - limit must be greater than zero.

        Post-conditions:
            - Returns list of matching SafariLinkItems ordered by canon status and occurrences.
        """
        query = "SELECT v.* FROM vault_items v"
        joins: list[str] = []
        conditions: list[str] = []
        params: list[Any] = []

        if min_sentiment is not None:
            joins.append("LEFT JOIN discussion_analyses d ON v.item_id = d.item_id")
            conditions.append("d.sentiment_score >= ?")
            params.append(min_sentiment)

        if epoch is not None:
            conditions.append("v.epochs_present LIKE ?")
            params.append(f'%"{epoch}"%')

        if is_evergreen_canon is not None:
            conditions.append("v.is_evergreen_canon = ?")
            params.append(is_evergreen_canon)

        if pillar is not None:
            conditions.append("(v.primary_pillar = ? OR v.pillar_tags LIKE ?)")
            params.extend([pillar, f'%"{pillar}"%'])

        if source_type is not None:
            conditions.append("v.source_type = ?")
            params.append(source_type)

        if search is not None and search.strip():
            conditions.append(
                "(v.title ILIKE ? OR v.search_query ILIKE ? OR v.canonical_url ILIKE ?)"
            )
            pattern = f"%{search.strip()}%"
            params.extend([pattern, pattern, pattern])

        if joins:
            query += " " + " ".join(joins)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY v.is_evergreen_canon DESC, v.total_occurrences DESC, v.title ASC LIMIT ?"
        params.append(limit)

        rows = self.conn.execute(query, params).fetchall()
        return [self._row_to_vault_item(r) for r in rows]

    def count_vault_items(self) -> int:
        """Count total items in vault_items table.

        Pre-conditions:
            - DuckDB connection must be open.

        Post-conditions:
            - Returns integer count of stored vault items.
        """
        row = self.conn.execute("SELECT COUNT(*) FROM vault_items;").fetchone()
        return int(row[0]) if row else 0

    def get_vault_item(self, item_id: str) -> SafariLinkItem | None:
        """Lookup a single vault item by item_id or hn_item_id.

        Pre-conditions:
            - item_id must be a non-empty string identifier.

        Post-conditions:
            - Returns SafariLinkItem if found, else None.
        """
        row = self.conn.execute(
            "SELECT * FROM vault_items WHERE item_id = ? OR hn_item_id = ? LIMIT 1;",
            [item_id, item_id],
        ).fetchone()
        return self._row_to_vault_item(row) if row else None

    def upsert_discussion_analyses(self, analyses: list[DiscussionAnalysis]) -> None:
        """Persist or update multiple DiscussionAnalysis records in a single batch.

        Pre-conditions:
            - analyses must be a list of DiscussionAnalysis models.

        Post-conditions:
            - Records stored in discussion_analyses.
        """
        if not analyses:
            return
        data = [
            [
                a.item_id,
                a.hn_item_id,
                a.anchor_comment_id,
                a.title,
                a.core_thesis,
                a.community_consensus,
                a.contrarian_pushback,
                a.anchor_comment_spotlight,
                a.sentiment_score,
                a.controversy_score,
                json.dumps(a.pillar_tags, default=str),
                json.dumps(a.actionable_takeaways, default=str),
                a.model_used,
                a.analyzed_at,
            ]
            for a in analyses
        ]
        self.conn.begin()
        try:
            placeholders = ", ".join(["(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"] * len(data))
            flat_data = [val for row in data for val in row]
            self.conn.execute(
                f"INSERT OR REPLACE INTO discussion_analyses VALUES {placeholders};",
                flat_data,
            )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def upsert_discussion_analysis(self, analysis: DiscussionAnalysis) -> None:
        """Persist or update a DiscussionAnalysis record.

        Pre-conditions:
            - analysis must be a valid DiscussionAnalysis model.

        Post-conditions:
            - Record stored in discussion_analyses keyed by item_id.
        """
        self.upsert_discussion_analyses([analysis])

    def _row_to_analysis(self, row: tuple[Any, ...]) -> DiscussionAnalysis:
        """Convert a DuckDB row into a DiscussionAnalysis model.

        Pre-conditions:
            - row matches discussion_analyses schema.

        Post-conditions:
            - Returns DiscussionAnalysis model.
        """
        return DiscussionAnalysis(
            item_id=row[0],
            hn_item_id=row[1],
            anchor_comment_id=row[2],
            title=row[3],
            core_thesis=row[4],
            community_consensus=row[5],
            contrarian_pushback=row[6],
            anchor_comment_spotlight=row[7],
            sentiment_score=row[8],
            controversy_score=row[9],
            pillar_tags=json.loads(row[10]) if row[10] else [],
            actionable_takeaways=json.loads(row[11]) if row[11] else [],
            model_used=row[12],
            analyzed_at=row[13],
        )

    def get_discussion_analysis(self, item_id: str) -> DiscussionAnalysis | None:
        """Retrieve a stored DiscussionAnalysis by item_id.

        Pre-conditions:
            - item_id must be a non-empty string.

        Post-conditions:
            - Returns DiscussionAnalysis if found, else None.
        """
        row = self.conn.execute(
            "SELECT * FROM discussion_analyses WHERE item_id = ? OR hn_item_id = ? LIMIT 1;",
            [item_id, item_id],
        ).fetchone()
        return self._row_to_analysis(row) if row else None

    def list_discussion_analyses(self, limit: int = 100) -> list[DiscussionAnalysis]:
        """List stored discussion analyses ordered by analyzed_at descending.

        Pre-conditions:
            - limit > 0.

        Post-conditions:
            - Returns list of DiscussionAnalysis records.
        """
        rows = self.conn.execute(
            "SELECT * FROM discussion_analyses ORDER BY analyzed_at DESC LIMIT ?;",
            [limit],
        ).fetchall()
        return [self._row_to_analysis(r) for r in rows]

    def list_vocabulary_entries(self, epoch: str | None = None) -> list[VocabularyEntry]:
        """List vocabulary lexicon entries ordered alphabetically.

        Pre-conditions:
            - None.

        Post-conditions:
            - Returns list of VocabularyEntry records.
        """
        if epoch:
            rows = self.conn.execute(
                "SELECT * FROM vocabulary_entries WHERE epochs_present LIKE ? ORDER BY term ASC;",
                [f'%"{epoch}"%'],
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM vocabulary_entries ORDER BY term ASC;"
            ).fetchall()

        entries: list[VocabularyEntry] = []
        for r in rows:
            entries.append(
                VocabularyEntry(
                    term=r[0],
                    source_url=r[1],
                    source_type=r[2],
                    epoch_first_seen=r[3],
                    epochs_present=json.loads(r[4]) if r[4] else [],
                    definition_hint=r[5],
                )
            )
        return entries

    def list_search_intents(
        self, category: str | None = None, epoch: str | None = None
    ) -> list[SearchQueryIntent]:
        """List longitudinal search query intents.

        Pre-conditions:
            - None.

        Post-conditions:
            - Returns list of SearchQueryIntent records.
        """
        query = "SELECT * FROM search_intents"
        conditions: list[str] = []
        params: list[Any] = []

        if category:
            conditions.append("category = ?")
            params.append(category)
        if epoch:
            conditions.append("epochs_present LIKE ?")
            params.append(f'%"{epoch}"%')

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY query_text ASC;"
        rows = self.conn.execute(query, params).fetchall()

        intents: list[SearchQueryIntent] = []
        for r in rows:
            intents.append(
                SearchQueryIntent(
                    query_text=r[0],
                    category=QueryIntentCategory(r[1]),
                    source_url=r[2],
                    epoch_first_seen=r[3],
                    epochs_present=json.loads(r[4]) if r[4] else [],
                    pillar_tags=json.loads(r[5]) if r[5] else [],
                )
            )
        return intents

    def upsert_daily_capsule(self, snapshot: DailyCapsuleSnapshot) -> None:
        """Store or replace a DailyCapsuleSnapshot.

        Pre-conditions:
            - snapshot must be a valid DailyCapsuleSnapshot.

        Post-conditions:
            - Record persisted in daily_capsules keyed by capsule_date.
        """
        self.conn.execute(
            """
            INSERT OR REPLACE INTO daily_capsules VALUES (
                ?, ?, ?, ?, ?, ?
            );
            """,
            [
                snapshot.capsule_date,
                json.dumps(snapshot.weather_records, default=str),
                json.dumps(snapshot.stock_records, default=str),
                json.dumps([d.model_dump() for d in snapshot.top_discussions], default=str),
                json.dumps([i.model_dump() for i in snapshot.evergreen_spotlight], default=str),
                snapshot.markdown_digest,
            ],
        )

    def get_daily_capsule(self, capsule_date: str) -> DailyCapsuleSnapshot | None:
        """Retrieve a stored DailyCapsuleSnapshot by capsule_date.

        Pre-conditions:
            - capsule_date must be formatted as YYYY-MM-DD.

        Post-conditions:
            - Returns DailyCapsuleSnapshot if found, else None.
        """
        row = self.conn.execute(
            "SELECT * FROM daily_capsules WHERE capsule_date = ? LIMIT 1;",
            [capsule_date],
        ).fetchone()
        if not row:
            return None

        discussions_raw = json.loads(row[3]) if row[3] else []
        evergreen_raw = json.loads(row[4]) if row[4] else []

        return DailyCapsuleSnapshot(
            capsule_date=row[0],
            weather_records=json.loads(row[1]) if row[1] else [],
            stock_records=json.loads(row[2]) if row[2] else [],
            top_discussions=[DiscussionAnalysis.model_validate(d) for d in discussions_raw],
            evergreen_spotlight=[SafariLinkItem.model_validate(i) for i in evergreen_raw],
            markdown_digest=row[5],
        )

    def list_daily_capsules(self, limit: int = 30) -> list[DailyCapsuleSnapshot]:
        """List stored daily capsule snapshots ordered by date descending.

        Pre-conditions:
            - limit > 0.

        Post-conditions:
            - Returns list of DailyCapsuleSnapshot records.
        """
        rows = self.conn.execute(
            "SELECT * FROM daily_capsules ORDER BY capsule_date DESC LIMIT ?;",
            [limit],
        ).fetchall()

        capsules: list[DailyCapsuleSnapshot] = []
        for row in rows:
            discussions_raw = json.loads(row[3]) if row[3] else []
            evergreen_raw = json.loads(row[4]) if row[4] else []
            capsules.append(
                DailyCapsuleSnapshot(
                    capsule_date=row[0],
                    weather_records=json.loads(row[1]) if row[1] else [],
                    stock_records=json.loads(row[2]) if row[2] else [],
                    top_discussions=[DiscussionAnalysis.model_validate(d) for d in discussions_raw],
                    evergreen_spotlight=[SafariLinkItem.model_validate(i) for i in evergreen_raw],
                    markdown_digest=row[5],
                )
            )
        return capsules

    def get_epochs_summary(self) -> dict[str, Any]:
        """Compute longitudinal statistics and distribution across all 3 historical epochs.

        Pre-conditions:
            - None.

        Post-conditions:
            - Returns dictionary of epoch link counts, evergreen canon items, anchored items,
              untitled counts, and taste profile distributions.
        """
        all_items = self.query_vault_items(limit=10000)
        evergreen_items = [i for i in all_items if i.is_evergreen_canon]
        anchored_items = [i for i in all_items if i.anchor_comment_id is not None]
        untitled_items = [i for i in all_items if i.was_untitled_tab]
        hydration_needed = [i for i in all_items if i.needs_title_hydration]

        epoch_ids = [
            EpochId.EPOCH_2023_2024.value,
            EpochId.EPOCH_2026_08_16.value,
            EpochId.EPOCH_2026_11_06.value,
        ]
        epoch_counts: dict[str, int] = {}
        for ep in epoch_ids:
            epoch_counts[ep] = len([i for i in all_items if ep in i.epochs_present])

        taste_profile = compute_taste_profile_summary(all_items)

        return {
            "total_vault_items": len(all_items),
            "epoch_counts": epoch_counts,
            "evergreen_canon_count": len(evergreen_items),
            "evergreen_canon_items": evergreen_items,
            "anchored_hn_count": len(anchored_items),
            "anchored_hn_items": anchored_items,
            "untitled_hn_count": len(untitled_items),
            "hydration_needed_count": len(hydration_needed),
            "taste_profile": taste_profile,
        }

    def export_to_parquet(self, export_dir: str | Path) -> dict[str, str]:
        """Export all Lakehouse tables to native Parquet files for S3/SeaweedFS storage.

        Pre-conditions:
            - export_dir path must be writable.

        Post-conditions:
            - Writes Parquet files for vault_items, discussion_analyses, vocabulary_entries,
              search_intents, and daily_capsules, returning a table-to-filepath mapping.
        """
        out_path = Path(export_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        tables = [
            "vault_items",
            "discussion_analyses",
            "vocabulary_entries",
            "search_intents",
            "daily_capsules",
        ]
        exported: dict[str, str] = {}

        for table in tables:
            dest = out_path / f"{table}.parquet"
            self.conn.execute(
                f"COPY {table} TO '{dest.as_posix()}' (FORMAT PARQUET);"
            )
            exported[table] = dest.as_posix()

        return exported
