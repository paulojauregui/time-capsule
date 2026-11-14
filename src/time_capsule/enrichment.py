"""DGX Spark LLM discussion analysis, VADER sentiment engine, and taste profiling.

Pre-conditions:
    - vaderSentiment, httpx, and domain models from time_capsule must be available.

Post-conditions:
    - Provides VADER sentiment metrics, DGX Spark async analysis with zero-retry circuit breaker,
      deterministic heuristic fallback, and longitudinal taste profiling.
"""

import asyncio
import json
import os
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import BaseModel, Field
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from time_capsule.cultural_assets import CulturalContentSummary
from time_capsule.models import (
    DiscussionAnalysis,
    EpochId,
    IntellectualPillar,
    SafariLinkItem,
)
from time_capsule.news_assets import HNStoryThread

__all__ = [
    "SentimentMetrics",
    "SparkDiscussionAnalyzer",
    "compute_taste_profile_summary",
    "compute_vader_sentiment",
]


class SentimentMetrics(BaseModel):
    """Normalized lexical sentiment polarity and controversy scores.

    Pre-conditions:
        - compound_score must be bounded within [-1.0, 1.0].
        - positive_ratio, negative_ratio, neutral_ratio, and controversy_score bounded within [0.0, 1.0].

    Post-conditions:
        - Encapsulates structured sentiment indices derived from VADER analysis.
    """

    compound_score: float = Field(default=0.0, ge=-1.0, le=1.0)
    positive_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    negative_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    neutral_ratio: float = Field(default=1.0, ge=0.0, le=1.0)
    controversy_score: float = Field(default=0.0, ge=0.0, le=1.0)


def compute_vader_sentiment(texts: list[str]) -> SentimentMetrics:
    """Compute aggregated VADER lexical sentiment metrics and community controversy score.

    Pre-conditions:
        - texts is a list of string observations or comment bodies.

    Post-conditions:
        - Returns SentimentMetrics with bounded polarity ratios and controversy index.
    """
    valid_texts = [t.strip() for t in texts if t and t.strip()]
    if not valid_texts:
        return SentimentMetrics(
            compound_score=0.0,
            positive_ratio=0.0,
            negative_ratio=0.0,
            neutral_ratio=1.0,
            controversy_score=0.0,
        )

    analyzer = SentimentIntensityAnalyzer()
    compounds: list[float] = []
    pos_ratios: list[float] = []
    neg_ratios: list[float] = []
    neu_ratios: list[float] = []

    for t in valid_texts:
        scores = analyzer.polarity_scores(t)
        compounds.append(scores["compound"])
        pos_ratios.append(scores["pos"])
        neg_ratios.append(scores["neg"])
        neu_ratios.append(scores["neu"])

    n = float(len(valid_texts))
    mean_compound = sum(compounds) / n
    mean_pos = sum(pos_ratios) / n
    mean_neg = sum(neg_ratios) / n
    mean_neu = sum(neu_ratios) / n

    clamped_compound = max(-1.0, min(1.0, round(mean_compound, 4)))
    clamped_pos = max(0.0, min(1.0, round(mean_pos, 4)))
    clamped_neg = max(0.0, min(1.0, round(mean_neg, 4)))
    clamped_neu = max(0.0, min(1.0, round(mean_neu, 4)))

    # Compute controversy index from polarity balance and compound variance
    if len(compounds) > 1:
        variance = sum((c - mean_compound) ** 2 for c in compounds) / n
    else:
        variance = 0.0

    balance = (
        (2.0 * min(clamped_pos, clamped_neg)) / (clamped_pos + clamped_neg + 1e-6)
        if (clamped_pos + clamped_neg) > 0.0
        else 0.0
    )
    controversy = min(1.0, max(0.0, round(0.5 * balance + 0.5 * min(1.0, variance * 2.0), 4)))

    return SentimentMetrics(
        compound_score=clamped_compound,
        positive_ratio=clamped_pos,
        negative_ratio=clamped_neg,
        neutral_ratio=clamped_neu,
        controversy_score=controversy,
    )


class SparkDiscussionAnalyzer:
    """Analyzer combining VADER sentiment with DGX Spark vLLM inference and heuristic fallback.

    Pre-conditions:
        - probe_timeout and request_timeout must be strictly positive floats.

    Post-conditions:
        - Provides check_spark_available, build_heuristic_analysis, and analyze_item methods.
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        probe_timeout: float = 1.8,
        request_timeout: float = 20.0,
    ) -> None:
        """Initialize SparkDiscussionAnalyzer with endpoints and timeouts.

        Pre-conditions:
            - probe_timeout > 0 and request_timeout > 0.

        Post-conditions:
            - Analyzer configured with target vLLM base URL, model ID, and timeouts.
        """
        raw_url = (
            base_url
            or os.getenv("SPARK_LLM_BASE_URL")
            or "http://happy.tail749110.ts.net:8000/v1"
        )
        self.base_url: str = raw_url.rstrip("/")
        self.model: str = (
            model
            or os.getenv("SPARK_LLM_MODEL")
            or "nvidia/Qwen3.8-Flash-Next-FP4-Local"
        )
        self.probe_timeout = probe_timeout
        self.request_timeout = request_timeout

    async def check_spark_available(self) -> bool:
        """Probe DGX Spark vLLM /models endpoint within circuit-breaker timeout (< 2.0s).

        Pre-conditions:
            - None.

        Post-conditions:
            - Returns True if /models responds HTTP 200, False on timeout or error without retrying.
        """
        probe_url = f"{self.base_url}/models"
        try:
            async with httpx.AsyncClient(timeout=self.probe_timeout) as client:
                resp = await client.get(probe_url)
                return resp.status_code == 200
        except (httpx.HTTPError, TimeoutError, OSError):
            return False

    def build_heuristic_analysis(
        self,
        item: SafariLinkItem,
        thread: HNStoryThread | None = None,
        cultural: CulturalContentSummary | None = None,
    ) -> DiscussionAnalysis:
        """Synthesize deterministic architectural discussion analysis without cloud/local LLM.

        Pre-conditions:
            - item must be a valid SafariLinkItem.

        Post-conditions:
            - Returns DiscussionAnalysis with high-signal structured consensus, spotlight, and scores.
        """
        texts: list[str] = [item.title]
        if thread:
            for comment in thread.top_comments:
                if comment.text:
                    texts.append(comment.text)
            if thread.anchor_subthread and thread.anchor_subthread.text:
                texts.append(thread.anchor_subthread.text)
        if cultural:
            if cultural.excerpt:
                texts.append(cultural.excerpt)
            for reply in cultural.top_replies:
                texts.append(reply)

        metrics = compute_vader_sentiment(texts)

        # Build core thesis
        if cultural and cultural.excerpt:
            core_thesis = (
                f"Community exploration of '{item.title}': {cultural.excerpt[:160]}..."
            )
        elif thread and thread.top_comments:
            core_thesis = (
                f"Engineering discussion on '{item.title}' evaluating architectural tradeoffs, "
                f"operational viability, and real-world failure modes."
            )
        else:
            core_thesis = (
                f"Curated analysis of '{item.title}' exploring technical patterns in {item.primary_pillar}."
            )

        # Build community consensus
        if metrics.compound_score > 0.15:
            consensus = (
                "Community sentiment is broadly positive, affirming operational efficiency, "
                "ergonomics, and production reliability."
            )
        elif metrics.compound_score < -0.15:
            consensus = (
                "Community perspective expresses skepticism regarding implementation complexity, "
                "hidden operational overhead, and maintenance friction."
            )
        else:
            consensus = (
                "Community analysis presents a balanced view weighing architectural flexibility "
                "against integration complexity and lifecycle maintenance costs."
            )

        # Build contrarian pushback
        contrarian = (
            "Caution urged regarding undocumented edge cases, cognitive load of abstraction layers, "
            "and potential vendor lock-in compared to simpler standard primitives."
        )

        # Build anchor spotlight
        anchor_spotlight: str | None = None
        if thread and thread.anchor_subthread and thread.anchor_subthread.text:
            anchor_spotlight = (
                f"Spotlight on comment #{thread.anchor_subthread.comment_id} "
                f"by {thread.anchor_subthread.author}: "
                f"\"{thread.anchor_subthread.text[:280]}\""
            )
        elif item.anchor_comment_id:
            anchor_spotlight = (
                f"Isolated discussion thread rooted at anchor comment #{item.anchor_comment_id}."
            )

        # Actionable takeaways mapped to intellectual pillars
        primary_pillar = item.primary_pillar
        if primary_pillar == IntellectualPillar.AI_LLM_AGENTS.value:
            takeaways = [
                "Implement sub-2.0s circuit breaker fallbacks for all autonomous LLM harnesses.",
                "Enforce structured JSON output validation and deterministic offline heuristic guards.",
            ]
        elif primary_pillar == IntellectualPillar.SYSTEMS_KERNEL.value:
            takeaways = [
                "Benchmark block I/O queue depths and memory access patterns under production load.",
                "Profile context switch overhead and eBPF tracepoints to eliminate kernel bottlenecks.",
            ]
        elif primary_pillar == IntellectualPillar.INFRA_K8S_HOMELAB.value:
            takeaways = [
                "Enforce non-root container boundaries and declarative GitOps state convergence.",
                "Implement automated health probes and multi-replica circuit-breaker resiliency.",
            ]
        else:
            takeaways = [
                "Establish strict Design-by-Contract preconditions and postconditions on public APIs.",
                "Maintain fast, deterministic unit test loops that execute sub-second without external I/O.",
            ]

        now_str = datetime.now(UTC).isoformat()
        hn_id = item.hn_item_id or (thread.hn_item_id if thread else None)
        anchor_id = item.anchor_comment_id or (thread.anchor_comment_id if thread else None)

        return DiscussionAnalysis(
            item_id=item.item_id,
            hn_item_id=hn_id,
            anchor_comment_id=anchor_id,
            title=item.title,
            core_thesis=core_thesis,
            community_consensus=consensus,
            contrarian_pushback=contrarian,
            anchor_comment_spotlight=anchor_spotlight,
            sentiment_score=metrics.compound_score,
            controversy_score=metrics.controversy_score,
            pillar_tags=item.pillar_tags if item.pillar_tags else [primary_pillar],
            actionable_takeaways=takeaways,
            model_used="heuristic-vader",
            analyzed_at=now_str,
        )

    async def analyze_item_async(
        self,
        item: SafariLinkItem,
        thread: HNStoryThread | None = None,
        cultural: CulturalContentSummary | None = None,
        allow_llm: bool = True,
    ) -> DiscussionAnalysis:
        """Analyze discussion using local DGX Spark vLLM when healthy, falling back to heuristic.

        Pre-conditions:
            - item must be a valid SafariLinkItem.

        Post-conditions:
            - Returns DiscussionAnalysis synthesized by LLM or deterministic fallback.
        """
        if allow_llm and await self.check_spark_available():
            chat_url = f"{self.base_url}/chat/completions"
            system_prompt = (
                "You are an expert systems infrastructure and software engineering analyst. "
                "Analyze the provided discussion and respond with a strict JSON object having keys: "
                "core_thesis, community_consensus, contrarian_pushback, "
                "anchor_comment_spotlight, actionable_takeaways."
            )
            content_summary = f"Title: {item.title}\nURL: {item.canonical_url}\n"
            if thread:
                content_summary += f"HN Points: {thread.points}, Comments: {thread.num_comments}\n"
                if thread.anchor_subthread:
                    content_summary += (
                        f"Anchor #{thread.anchor_subthread.comment_id}: "
                        f"{thread.anchor_subthread.text[:300]}\n"
                    )
            if cultural:
                content_summary += f"Excerpt: {cultural.excerpt[:300]}\n"

            payload = {
                "model": self.model,
                "temperature": 0.2,
                "max_tokens": 600,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content_summary},
                ],
            }

            try:
                async with httpx.AsyncClient(timeout=self.request_timeout) as client:
                    resp = await client.post(chat_url, json=payload)
                    resp.raise_for_status()
                    result_data = resp.json()
                    raw_content = result_data["choices"][0]["message"]["content"]
                    parsed_json = json.loads(raw_content)

                    # Compute VADER metrics to ensure uniform sentiment calibration
                    heuristic_fallback = self.build_heuristic_analysis(
                        item, thread=thread, cultural=cultural
                    )

                    takeaways = parsed_json.get("actionable_takeaways", [])
                    if not isinstance(takeaways, list) or not takeaways:
                        takeaways = heuristic_fallback.actionable_takeaways

                    return DiscussionAnalysis(
                        item_id=item.item_id,
                        hn_item_id=item.hn_item_id,
                        anchor_comment_id=item.anchor_comment_id,
                        title=item.title,
                        core_thesis=parsed_json.get("core_thesis") or heuristic_fallback.core_thesis,
                        community_consensus=parsed_json.get("community_consensus")
                        or heuristic_fallback.community_consensus,
                        contrarian_pushback=parsed_json.get("contrarian_pushback")
                        or heuristic_fallback.contrarian_pushback,
                        anchor_comment_spotlight=parsed_json.get("anchor_comment_spotlight")
                        or heuristic_fallback.anchor_comment_spotlight,
                        sentiment_score=heuristic_fallback.sentiment_score,
                        controversy_score=heuristic_fallback.controversy_score,
                        pillar_tags=item.pillar_tags if item.pillar_tags else [item.primary_pillar],
                        actionable_takeaways=takeaways,
                        model_used=self.model,
                        analyzed_at=datetime.now(UTC).isoformat(),
                    )
            except (httpx.HTTPError, TimeoutError, json.JSONDecodeError, KeyError, IndexError):
                pass

        return self.build_heuristic_analysis(item, thread=thread, cultural=cultural)

    def analyze_item(
        self,
        item: SafariLinkItem,
        thread: HNStoryThread | None = None,
        cultural: CulturalContentSummary | None = None,
        allow_llm: bool = False,
    ) -> DiscussionAnalysis:
        """Synchronous wrapper for item discussion analysis.

        Pre-conditions:
            - item must be a valid SafariLinkItem.

        Post-conditions:
            - Returns DiscussionAnalysis via synchronous heuristic or completed async loop.
        """
        if not allow_llm:
            return self.build_heuristic_analysis(item, thread=thread, cultural=cultural)

        try:
            return asyncio.run(
                self.analyze_item_async(
                    item, thread=thread, cultural=cultural, allow_llm=True
                )
            )
        except RuntimeError:
            return self.build_heuristic_analysis(item, thread=thread, cultural=cultural)


def compute_taste_profile_summary(items: list[SafariLinkItem]) -> dict[str, Any]:
    """Compute longitudinal taste profile distribution across Intellectual Pillars and epochs.

    Pre-conditions:
        - items is a list of SafariLinkItem models.

    Post-conditions:
        - Returns a dictionary detailing pillar counts, percentages, epoch shifts, and rising pillars.
    """
    all_pillars = [p.value for p in IntellectualPillar]
    known_epochs = [
        EpochId.EPOCH_2023_2024.value,
        EpochId.EPOCH_2026_08_16.value,
        EpochId.EPOCH_2026_11_06.value,
    ]

    pillar_counts: dict[str, int] = {p: 0 for p in all_pillars}
    epoch_breakdown: dict[str, dict[str, int]] = {
        ep: {p: 0 for p in all_pillars} for ep in known_epochs
    }

    total_items = len(items)

    for item in items:
        tags = item.pillar_tags if item.pillar_tags else [item.primary_pillar]
        for tag in tags:
            if tag in pillar_counts:
                pillar_counts[tag] += 1

        for ep in item.epochs_present:
            if ep in epoch_breakdown:
                for tag in tags:
                    if tag in epoch_breakdown[ep]:
                        epoch_breakdown[ep][tag] += 1

    total_tag_occurrences = sum(pillar_counts.values()) or 1
    pillar_percentages: dict[str, float] = {
        p: round((count / total_tag_occurrences) * 100.0, 2)
        for p, count in pillar_counts.items()
    }

    epoch_percentages: dict[str, dict[str, float]] = {}
    for ep in known_epochs:
        ep_total = sum(epoch_breakdown[ep].values()) or 1
        epoch_percentages[ep] = {
            p: round((epoch_breakdown[ep][p] / ep_total) * 100.0, 2)
            for p in all_pillars
        }

    top_pillar_overall = max(pillar_counts.items(), key=lambda kv: kv[1])[0]

    # Compute rising pillars: growth in share between 2023_2024 and 2026_11_06
    rising_pillars: list[str] = []
    e1_pcts = epoch_percentages.get(EpochId.EPOCH_2023_2024.value, {})
    e3_pcts = epoch_percentages.get(EpochId.EPOCH_2026_11_06.value, {})

    growth_deltas = [
        (p, e3_pcts.get(p, 0.0) - e1_pcts.get(p, 0.0))
        for p in all_pillars
    ]
    growth_deltas.sort(key=lambda kv: kv[1], reverse=True)
    rising_pillars = [p for p, delta in growth_deltas if delta > 0.0]

    return {
        "total_items": total_items,
        "pillar_counts": pillar_counts,
        "pillar_percentages": pillar_percentages,
        "epoch_breakdown": epoch_breakdown,
        "epoch_percentages": epoch_percentages,
        "top_pillar_overall": top_pillar_overall,
        "rising_pillars": rising_pillars,
    }
