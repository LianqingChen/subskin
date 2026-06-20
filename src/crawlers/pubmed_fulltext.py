"""PubMed Central full-text fetcher for the SubSkin project.

Fetches full-text body content from PubMed Central (PMC) for papers
that have been deposited in PMC. Uses NCBI EFetch API with db=pmc to
retrieve JATS XML, then extracts clean plain text from the body sections.

Rate limiting: 3 req/s without API key, 10 req/s with NCBI_API_KEY.
"""

from __future__ import annotations

import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Optional

import requests
from dotenv import load_dotenv
from lxml import etree

load_dotenv()

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
OA_URL = "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi"

# JATS XML namespaces
JATS_NS = {
    "x": "http://dtd.nlm.nih.gov/ncbi/pmc/articleset/nlm-articleset-2.0.dtd",
}

RATE_WITH_KEY = 10.0
RATE_WITHOUT_KEY = 3.0

# Tags whose text should be extracted from JATS body
BODY_TEXT_TAGS = {"p", "title", "label", "caption", "th", "td", "li", "abstract"}


# ── Public API ───────────────────────────────────────────────────────────────


class PubmedFulltextFetcher:
    """Fetcher for PMC full-text articles via NCBI EFetch.

    Args:
        data_dir: Directory to store downloaded full-text files.
        requests_per_second: Rate limit override.
        max_retries: Retry attempts for transient failures.
        backoff_base_seconds: Base delay for exponential backoff.
    """

    def __init__(
        self,
        *,
        data_dir: str = "data/fulltext",
        requests_per_second: float | None = None,
        max_retries: int = 3,
        backoff_base_seconds: float = 1.0,
    ) -> None:
        api_key = os.getenv("NCBI_API_KEY")
        if requests_per_second is None:
            requests_per_second = (
                RATE_WITH_KEY if api_key else RATE_WITHOUT_KEY
            )

        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._rate = requests_per_second
        self._min_interval = 1.0 / requests_per_second
        self._last_request = 0.0
        self._max_retries = max_retries
        self._backoff_base = backoff_base_seconds

        if api_key:
            logger.info("NCBI API key detected — rate limit %.0f req/s", self._rate)
        else:
            logger.warning(
                "No NCBI_API_KEY — rate capped at %.0f req/s", self._rate
            )

    # ── Fetching ─────────────────────────────────────────────────────────

    def fetch_fulltext(self, pmcid: str) -> Optional[str]:
        """Fetch full-text plain text for a PMCID.

        Args:
            pmcid: PubMed Central ID (numeric, without 'PMC' prefix).

        Returns:
            Extracted plain text, or None if unavailable.
        """
        # Check cache first
        cache_path = self._cache_path(pmcid)
        if cache_path.exists():
            cached = cache_path.read_text(encoding="utf-8")
            if cached.strip():
                return cached

        # Try EFetch XML (works for all PMC papers with full text)
        text = self._fetch_via_efetch(pmcid)
        if text is None:
            # Fall back to OA package download
            text = self._fetch_via_oa(pmcid)

        if text:
            cache_path.write_text(text, encoding="utf-8")
            logger.info("Fetched full text for PMC%s (%d chars)", pmcid, len(text))
        else:
            logger.info("No full text available for PMC%s", pmcid)

        return text

    def fetch_batch(
        self, pmcid_list: list[str], on_progress: Any = None
    ) -> dict[str, Optional[str]]:
        """Fetch full text for multiple PMCIDs.

        Returns:
            Dict mapping PMCID → full text (or None).
        """
        results: dict[str, Optional[str]] = {}
        total = len(pmcid_list)

        for i, pmcid in enumerate(pmcid_list):
            text = self.fetch_fulltext(pmcid)
            results[pmcid] = text

            if on_progress:
                on_progress(i + 1, total, pmcid, text is not None)
            elif (i + 1) % 50 == 0 or i == total - 1:
                count_ok = sum(1 for v in results.values() if v is not None)
                logger.info(
                    "Full-text batch: %d/%d (%.0f%% success)",
                    count_ok,
                    i + 1,
                    count_ok / (i + 1) * 100,
                )

        return results

    # ── Internal ──────────────────────────────────────────────────────────

    def _cache_path(self, pmcid: str) -> Path:
        """Get cache file path for a PMCID."""
        # Strip 'PMC' prefix if present, then add back
        clean_id = pmcid.upper().replace("PMC", "", 1)
        return self._data_dir / f"PMC{clean_id}.txt"

    def _rate_limit(self) -> None:
        """Enforce request rate limit."""
        now = time.monotonic()
        elapsed = now - self._last_request
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request = time.monotonic()

    def _with_retries(self, fn: Any, *args: Any, **kwargs: Any) -> Any:
        """Call fn with exponential backoff retry."""
        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                last_error = exc
                if attempt == self._max_retries:
                    raise
                sleep_time = self._backoff_base * (2 ** (attempt - 1))
                logger.warning(
                    "Transient error (attempt %d/%d): %s. Retrying in %.1fs",
                    attempt, self._max_retries, exc, sleep_time,
                )
                time.sleep(sleep_time)
        raise last_error  # type: ignore[misc]

    def _fetch_via_efetch(self, pmcid: str) -> Optional[str]:
        """Fetch full text via NCBI EFetch (returns JATS XML)."""
        self._rate_limit()

        def _do_fetch() -> Optional[str]:
            params = {
                "db": "pmc",
                "id": pmcid,
                "rettype": "xml",
                "retmode": "xml",
            }
            resp = requests.get(EFETCH_URL, params=params, timeout=30)
            resp.raise_for_status()

            if not resp.content.strip():
                return None

            try:
                root = etree.fromstring(resp.content)
            except etree.XMLSyntaxError:
                logger.warning("Invalid XML for PMC%s", pmcid)
                return None

            # Check for errors
            errors = root.xpath(".//error")
            if errors:
                error_codes = [e.get("code", "unknown") for e in errors]
                logger.debug("No full text for PMC%s: %s", pmcid, error_codes)
                return None

            # Extract body
            bodies = root.xpath(".//body")
            if not bodies:
                return None

            return self._extract_text(bodies[0])

        try:
            return self._with_retries(_do_fetch)
        except Exception:
            logger.warning("EFetch failed for PMC%s", pmcid, exc_info=True)
            return None

    def _fetch_via_oa(self, pmcid: str) -> Optional[str]:
        """Fetch full text via PMC OA service (downloads tarball).

        This is a fallback for papers the OA service lists as downloadable.
        Downloads the .tar.gz, extracts the .nxml file, and parses it.
        """
        self._rate_limit()

        def _do_fetch() -> Optional[str]:
            # Query OA service for download links
            resp = requests.get(OA_URL, params={"id": pmcid}, timeout=15)
            resp.raise_for_status()
            root = etree.fromstring(resp.content)

            links = root.xpath(".//link")
            if not links:
                return None

            # Prefer PDF, fall back to tgz
            pdf_link = None
            tgz_link = None
            for link in links:
                fmt = link.get("format", "")
                href = link.get("href", "")
                if fmt == "pdf":
                    pdf_link = href
                elif fmt == "tgz":
                    tgz_link = href

            download_url = pdf_link or tgz_link
            if not download_url:
                return None

            # Download — handle both HTTP and FTP
            import io
            import tarfile
            from ftplib import FTP
            from urllib.parse import urlparse

            self._rate_limit()

            if download_url.startswith("ftp://"):
                # FTP: parse host/path, download to memory
                parsed = urlparse(download_url)
                ftp = FTP(parsed.hostname, timeout=30)
                ftp.login()
                bio = io.BytesIO()
                ftp.retrbinary(f"RETR {parsed.path}", bio.write)
                ftp.quit()
                dl_content = bio.getvalue()
            else:
                dl_resp = requests.get(download_url, timeout=60)
                dl_resp.raise_for_status()
                dl_content = dl_resp.content

            if download_url.endswith(".pdf"):
                pdf_path = self._data_dir / f"PMC{pmcid}.pdf"
                pdf_path.write_bytes(dl_content)
                logger.info("Downloaded PDF for PMC%s (%d bytes)", pmcid, len(dl_content))
                return f"[PDF downloaded: {pdf_path}]"

            # For tgz, extract nxml and parse
            with tarfile.open(fileobj=io.BytesIO(dl_content), mode="r:gz") as tar:
                for member in tar.getmembers():
                    if member.name.endswith(".nxml"):
                        nxml_content = tar.extractfile(member)
                        if nxml_content:
                            root = etree.parse(nxml_content)
                            bodies = root.xpath(".//body")
                            if bodies:
                                return self._extract_text(bodies[0])

            return None

        try:
            return self._with_retries(_do_fetch)
        except Exception:
            logger.warning("OA fetch failed for PMC%s", pmcid, exc_info=True)
            return None

    @staticmethod
    def _extract_text(body_elem: Any) -> str:
        """Extract clean plain text from a JATS body element.

        Preserves paragraph and section structure with appropriate
        whitespace separation.
        """
        parts: list[str] = []

        for elem in body_elem.iter():
            tag = etree.QName(elem).localname if hasattr(elem, "tag") else ""

            if tag in BODY_TEXT_TAGS:
                text = elem.text or ""
                # Collect tail text too (text after closing tag of children)
                for child in elem:
                    if child.tail:
                        text += " " + child.tail
                text = text.strip()
                if text and len(text) > 3:  # Skip very short fragments
                    parts.append(text)

        if not parts:
            # Simpler fallback: just get all text
            all_text = "".join(body_elem.itertext()).strip()
            # Collapse excessive whitespace
            all_text = re.sub(r"\n{3,}", "\n\n", all_text)
            all_text = re.sub(r"[ \t]{2,}", " ", all_text)
            return all_text

        return "\n\n".join(parts)


# ── Convenience function ─────────────────────────────────────────────────────


def check_pmcid_availability(pmcid_list: list[str]) -> dict[str, bool]:
    """Quick check whether PMCIDs have full text available via EFetch.

    Returns:
        Dict mapping PMCID → has_full_text (bool).
    """
    results: dict[str, bool] = {}
    fetcher = PubmedFulltextFetcher()

    for pmcid in pmcid_list:
        cache_path = fetcher._cache_path(pmcid)
        if cache_path.exists() and cache_path.read_text(encoding="utf-8").strip():
            results[pmcid] = True
            continue

        try:
            fetcher._rate_limit()
            params = {"db": "pmc", "id": pmcid, "rettype": "xml", "retmode": "xml"}
            resp = requests.get(EFETCH_URL, params=params, timeout=30)
            root = etree.fromstring(resp.content)
            has_body = len(root.xpath(".//body")) > 0
            has_error = len(root.xpath(".//error")) > 0
            results[pmcid] = has_body and not has_error
        except Exception:
            results[pmcid] = False

    return results
