import calendar
import hashlib
import html
import ipaddress
import re
import socket
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urlparse

import feedparser
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import TrendItem, utc_now
from app.security import require_api_token

router = APIRouter(prefix="/trends", tags=["trends"], dependencies=[Depends(require_api_token)])


class TrendRead(BaseModel):
    id: str
    title: str
    summary: str | None
    summary_source_url: str | None
    source_urls: list[str]
    article_urls: list[str]
    trend_score: float
    published_at: datetime | None
    first_seen_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DiscoveryResult(BaseModel):
    attempted_feeds: int
    successful_feeds: int
    items_added: int
    items_updated: int
    errors: list[str]


def _feed_urls() -> list[str]:
    return list(dict.fromkeys(url.strip() for url in get_settings().rss_feed_urls.split(",") if url.strip()))


def _validate_feed_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Feed URLs must use HTTPS and cannot contain credentials")
    if len(url) > 2048:
        raise ValueError("Feed URL is too long")
    try:
        resolved = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ValueError("Feed hostname could not be resolved") from exc
    for result in resolved:
        address = ipaddress.ip_address(result[4][0])
        if not address.is_global:
            raise ValueError("Feed host resolves to a non-public address")


def _clean_text(value: str | None, limit: int) -> str | None:
    if not value:
        return None
    clean = re.sub(r"<[^>]*>", " ", html.unescape(value))
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:limit] or None


def _canonical_key(title: str) -> str:
    normalized = unicodedata.normalize("NFKC", title).casefold()
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    normalized = " ".join(normalized.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _entry_datetime(entry) -> datetime | None:
    published = entry.get("published_parsed") or entry.get("updated_parsed")
    if not published:
        return None
    return datetime.fromtimestamp(calendar.timegm(published), tz=timezone.utc)


def _score(source_count: int, observed_at: datetime | None, now: datetime) -> float:
    source_diversity = min(source_count, 5) * 12
    if observed_at is None:
        freshness = 0
    else:
        age_hours = max(0, (now - observed_at).total_seconds() / 3600)
        freshness = 40 if age_hours <= 6 else 30 if age_hours <= 24 else 20 if age_hours <= 72 else 5 if age_hours <= 168 else 0
    return float(min(100, source_diversity + freshness))


def _fetch_feed(url: str, max_bytes: int) -> list[dict]:
    _validate_feed_url(url)
    with httpx.Client(timeout=httpx.Timeout(12, connect=4), follow_redirects=False,
                       headers={"User-Agent": "AYE-TrendRadar/0.1 (+RSS reader)"}) as client:
        with client.stream("GET", url) as response:
            if 300 <= response.status_code < 400:
                raise ValueError("Feed redirects are disabled; configure the final HTTPS URL")
            response.raise_for_status()
            declared_length = response.headers.get("content-length")
            if declared_length and int(declared_length) > max_bytes:
                raise ValueError("Feed response exceeds the configured size limit")
            chunks = []
            received = 0
            for chunk in response.iter_bytes():
                received += len(chunk)
                if received > max_bytes:
                    raise ValueError("Feed response exceeds the configured size limit")
                chunks.append(chunk)
    parsed = feedparser.parse(b"".join(chunks))
    if parsed.bozo and not parsed.entries:
        raise ValueError("Feed response could not be parsed")
    output = []
    for entry in parsed.entries[:100]:
        title = _clean_text(entry.get("title"), 500)
        if not title:
            continue
        link = entry.get("link")
        if link and (urlparse(link).scheme != "https" or not urlparse(link).hostname):
            link = None
        output.append({"title": title, "summary": _clean_text(entry.get("summary"), 4000),
                       "article_url": link, "published_at": _entry_datetime(entry)})
    return output


@router.get("", response_model=list[TrendRead])
def list_trends(limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)):
    return db.scalars(select(TrendItem).order_by(TrendItem.trend_score.desc(), TrendItem.last_seen_at.desc()).limit(limit)).all()


@router.post("/discover", response_model=DiscoveryResult)
def discover_trends(db: Session = Depends(get_db)):
    urls = _feed_urls()
    if not urls:
        raise HTTPException(status_code=422, detail="No RSS feeds configured. Set AYE_RSS_FEED_URLS to trusted HTTPS feed URLs.")
    if len(urls) > 20:
        raise HTTPException(status_code=422, detail="At most 20 RSS feeds can be configured")

    settings = get_settings()
    errors: list[str] = []
    successful_feeds = 0
    items_added = 0
    items_updated = 0
    for source_url in urls:
        try:
            entries = _fetch_feed(source_url, settings.max_feed_bytes)
            successful_feeds += 1
        except (httpx.HTTPError, ValueError) as exc:
            errors.append(f"{urlparse(source_url).hostname or 'invalid feed'}: {str(exc)[:200]}")
            continue
        for entry in entries:
            key = _canonical_key(entry["title"])
            trend = db.scalar(select(TrendItem).where(TrendItem.canonical_key == key))
            now = utc_now()
            if trend is None:
                trend = TrendItem(canonical_key=key, title=entry["title"], summary=entry["summary"],
                                  summary_source_url=source_url if entry["summary"] else None,
                                  source_urls=[source_url], article_urls=[entry["article_url"]] if entry["article_url"] else [],
                                  published_at=entry["published_at"], first_seen_at=now, last_seen_at=now)
                db.add(trend)
                items_added += 1
            else:
                if source_url not in trend.source_urls:
                    trend.source_urls = [*trend.source_urls, source_url]
                if entry["article_url"] and entry["article_url"] not in trend.article_urls:
                    trend.article_urls = [*trend.article_urls, entry["article_url"]][:20]
                if entry["published_at"] and (trend.published_at is None or entry["published_at"] > trend.published_at):
                    trend.published_at = entry["published_at"]
                if entry["summary"] and (not trend.summary or len(entry["summary"]) > len(trend.summary)):
                    trend.summary = entry["summary"]
                    trend.summary_source_url = source_url
                items_updated += 1
            trend.trend_score = _score(len(trend.source_urls), trend.published_at or trend.last_seen_at, now)
            trend.last_seen_at = now
    # Recalculate old scores too so items age out even when they stop appearing in feeds.
    scoring_time = utc_now()
    for trend in db.scalars(select(TrendItem)).all():
        trend.trend_score = _score(len(trend.source_urls), trend.published_at or trend.last_seen_at, scoring_time)
    db.commit()
    return DiscoveryResult(attempted_feeds=len(urls), successful_feeds=successful_feeds,
                           items_added=items_added, items_updated=items_updated, errors=errors)
