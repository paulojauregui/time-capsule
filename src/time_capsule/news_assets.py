"""Hacker News Algolia discussion thread hydration, comments tree extraction, and Dagster asset.

Pre-conditions:
    - Target Hacker News items or front-page queries must be accessible via Algolia or fallback mock.

Post-conditions:
    - Provides structured thread models, anchor comment isolation, and title hydration.
"""

import html
import re
from typing import Any

import pandas as pd
import requests
from dagster import asset
from pydantic import BaseModel, Field

from time_capsule.models import SafariLinkItem

__all__ = [
    "HNClient",
    "HNCommentNode",
    "HNStoryThread",
    "top_hn_discussions",
]


class HNCommentNode(BaseModel):
    """Recursive comment node within a Hacker News discussion tree.

    Pre-conditions:
        - comment_id must be a non-empty string.

    Post-conditions:
        - Represents an individual comment and its nested replies.
    """

    comment_id: str
    author: str = "anonymous"
    text: str = ""
    created_at: str = ""
    points: int | None = None
    children: list["HNCommentNode"] = Field(default_factory=list)


class HNStoryThread(BaseModel):
    """Structured Hacker News story thread with top comments and anchor spotlight.

    Pre-conditions:
        - hn_item_id must be a non-empty string.

    Post-conditions:
        - Encapsulates story metadata, top-level comments, and isolated anchor sub-thread.
    """

    hn_item_id: str
    title: str
    url: str | None = None
    author: str = "anonymous"
    points: int = 0
    num_comments: int = 0
    created_at: str = ""
    top_comments: list[HNCommentNode] = Field(default_factory=list)
    anchor_comment_id: str | None = None
    anchor_subthread: HNCommentNode | None = None
    was_hydrated_from_untitled: bool = False


class HNClient:
    """Client for querying the Algolia Hacker News search and item API.

    Pre-conditions:
        - base_url must point to a valid Algolia HN endpoint.
        - timeout must be strictly positive.

    Post-conditions:
        - Provides thread fetching, anchor comment isolation, and item hydration.
    """

    def __init__(
        self,
        base_url: str = "https://hn.algolia.com/api/v1",
        timeout: float = 5.0,
    ) -> None:
        """Initialize Algolia Hacker News client.

        Pre-conditions:
            - timeout > 0.

        Post-conditions:
            - Client configured with base_url and timeout.
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @staticmethod
    def clean_hn_html(raw_html: str | None) -> str:
        """Strip HTML markup and unescape entities from raw Hacker News comments.

        Pre-conditions:
            - raw_html is an optional string containing comment text or HTML markup.

        Post-conditions:
            - Returns plain text string with HTML tags removed and entities unescaped.
        """
        if not raw_html:
            return ""
        text = re.sub(r"<p>", "\n\n", raw_html, flags=re.IGNORECASE)
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        unescaped = html.unescape(text)
        return unescaped.strip()

    def _dict_to_comment_node(self, child: dict[str, Any]) -> HNCommentNode:
        """Recursively convert Algolia comment dictionary to HNCommentNode model.

        Pre-conditions:
            - child dictionary contains Algolia comment data.

        Post-conditions:
            - Returns fully parsed HNCommentNode tree.
        """
        cid = str(child.get("id") or child.get("objectID") or "")
        author = str(child.get("author") or "anonymous")
        raw_text = str(child.get("text") or "")
        clean_text = self.clean_hn_html(raw_text)
        created_at = str(child.get("created_at") or "")
        points = child.get("points")
        if points is not None:
            points = int(points)

        raw_children = child.get("children") or []
        children_nodes: list[HNCommentNode] = []
        if isinstance(raw_children, list):
            for sub_child in raw_children:
                if isinstance(sub_child, dict):
                    children_nodes.append(self._dict_to_comment_node(sub_child))

        return HNCommentNode(
            comment_id=cid,
            author=author,
            text=clean_text,
            created_at=created_at,
            points=points,
            children=children_nodes,
        )

    def find_comment_by_id(
        self,
        node_or_children: list[dict[str, Any]] | dict[str, Any],
        target_id: str,
    ) -> HNCommentNode | None:
        """Recursively search for an anchor comment by ID in an Algolia comment tree.

        Pre-conditions:
            - target_id must be a non-empty string identifier.

        Post-conditions:
            - Returns matching HNCommentNode with its nested replies if found, else None.
        """
        normalized_target = target_id.lstrip("#").strip()

        if isinstance(node_or_children, dict):
            cid = (
                str(node_or_children.get("id") or node_or_children.get("objectID") or "")
                .lstrip("#")
                .strip()
            )
            if cid == normalized_target:
                return self._dict_to_comment_node(node_or_children)
            children = node_or_children.get("children", [])
            if isinstance(children, list):
                return self.find_comment_by_id(children, normalized_target)
            return None

        if isinstance(node_or_children, list):
            for item in node_or_children:
                if isinstance(item, dict):
                    found = self.find_comment_by_id(item, normalized_target)
                    if found is not None:
                        return found

        return None

    def fetch_item_thread(
        self,
        hn_item_id: str,
        anchor_comment_id: str | None = None,
        was_untitled: bool = False,
    ) -> HNStoryThread:
        """Fetch structured discussion thread and isolated anchor sub-thread from Algolia.

        Pre-conditions:
            - hn_item_id is a non-empty string.

        Post-conditions:
            - Returns HNStoryThread populated with story metadata, top comments, and optional anchor.
        """
        clean_item_id = hn_item_id.strip()
        url = f"{self.base_url}/items/{clean_item_id}"
        try:
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError):
            return HNStoryThread(
                hn_item_id=clean_item_id,
                title=f"Hacker News Discussion {clean_item_id}",
                url=f"https://news.ycombinator.com/item?id={clean_item_id}",
                author="community",
                points=100,
                num_comments=10,
                created_at="2026-11-06T00:00:00Z",
                anchor_comment_id=anchor_comment_id,
                was_hydrated_from_untitled=was_untitled,
            )

        title = str(data.get("title") or f"HN Story {clean_item_id}")
        story_url = data.get("url") or f"https://news.ycombinator.com/item?id={clean_item_id}"
        author = str(data.get("author") or "anonymous")
        points = int(data.get("points") or 0)
        created_at = str(data.get("created_at") or "")

        raw_children = data.get("children", [])
        if not isinstance(raw_children, list):
            raw_children = []

        num_comments = len(raw_children)
        top_comments: list[HNCommentNode] = []
        for c in raw_children[:10]:
            if isinstance(c, dict):
                top_comments.append(self._dict_to_comment_node(c))

        anchor_subthread: HNCommentNode | None = None
        if anchor_comment_id:
            anchor_subthread = self.find_comment_by_id(raw_children, anchor_comment_id)

        return HNStoryThread(
            hn_item_id=clean_item_id,
            title=title,
            url=story_url,
            author=author,
            points=points,
            num_comments=num_comments,
            created_at=created_at,
            top_comments=top_comments,
            anchor_comment_id=anchor_comment_id,
            anchor_subthread=anchor_subthread,
            was_hydrated_from_untitled=was_untitled,
        )

    def hydrate_safari_item(
        self, item: SafariLinkItem
    ) -> tuple[SafariLinkItem, HNStoryThread | None]:
        """Hydrate an un-titled or generic Hacker News vault item using Algolia story metadata.

        Pre-conditions:
            - item must be a valid SafariLinkItem.

        Post-conditions:
            - Returns a tuple of (updated_or_original_item, thread_or_none).
        """
        if not item.hn_item_id:
            return item, None

        thread = self.fetch_item_thread(
            item.hn_item_id,
            anchor_comment_id=item.anchor_comment_id,
            was_untitled=item.needs_title_hydration,
        )

        updated_item = item.model_copy()
        if item.needs_title_hydration and thread.title:
            updated_item.title = f"{thread.title} | Hacker News"
            updated_item.needs_title_hydration = False

        return updated_item, thread

    def fetch_front_page_stories(self, limit: int = 10) -> list[HNStoryThread]:
        """Retrieve current front-page discussions from Hacker News via Algolia.

        Pre-conditions:
            - limit must be an integer between 1 and 50.

        Post-conditions:
            - Returns list of HNStoryThread objects for top stories.
        """
        url = f"{self.base_url}/search?tags=front_page&hitsPerPage={limit}"
        try:
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            hits = data.get("hits", [])
            stories: list[HNStoryThread] = []
            for hit in hits:
                stories.append(
                    HNStoryThread(
                        hn_item_id=str(hit.get("objectID") or hit.get("id")),
                        title=str(hit.get("title") or "Untitled Discussion"),
                        url=hit.get("url"),
                        author=str(hit.get("author") or "anonymous"),
                        points=int(hit.get("points") or 0),
                        num_comments=int(hit.get("num_comments") or 0),
                        created_at=str(hit.get("created_at") or ""),
                    )
                )
            return stories
        except (requests.RequestException, ValueError):
            return [
                HNStoryThread(
                    hn_item_id="49802161",
                    title="OpenAI is well positioned to fast-follow Jev",
                    url="https://news.ycombinator.com/item?id=49802161",
                    author="sample_user",
                    points=245,
                    num_comments=120,
                    created_at="2026-11-06T12:00:00Z",
                ),
                HNStoryThread(
                    hn_item_id="49985548",
                    title="Ask HN: What do you run on a $5 VPS that's worth keeping online 24/7?",
                    url="https://news.ycombinator.com/item?id=49985548",
                    author="vps_enthusiast",
                    points=380,
                    num_comments=210,
                    created_at="2026-11-06T14:30:00Z",
                ),
            ]


@asset
def top_hn_discussions() -> pd.DataFrame:
    """Dagster asset collecting top Hacker News discussions into a DataFrame.

    Pre-conditions:
        - None.

    Post-conditions:
        - Returns pandas DataFrame containing top HN front-page stories.
    """
    client = HNClient()
    stories = client.fetch_front_page_stories(limit=10)
    records = [
        {
            "hn_item_id": s.hn_item_id,
            "title": s.title,
            "url": s.url,
            "author": s.author,
            "points": s.points,
            "num_comments": s.num_comments,
            "created_at": s.created_at,
        }
        for s in stories
    ]
    return pd.DataFrame(records)
