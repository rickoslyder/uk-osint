"""BAILII (British and Irish Legal Information Institute) scraper.

BAILII provides free access to UK and Irish case law and legislation.
URL: https://www.bailii.org

Coverage includes:
- England and Wales Courts
- Scotland Courts
- Northern Ireland Courts
- UK Supreme Court
- UK Parliament/Legislation
- European Courts (historically)

This scraper uses the public search interface. Be respectful with rate limiting.
"""

import asyncio
import re
from datetime import date
from typing import Optional
from urllib.parse import quote_plus, urljoin

import httpx
from bs4 import BeautifulSoup

from ..models.entities import LegalCase


class BAILIIScraper:
    """Scraper for BAILII legal database."""

    BASE_URL = "https://www.bailii.org"
    SEARCH_URL = "https://www.bailii.org/cgi-bin/lucy_search_1.cgi"

    # Court database mappings for filtering
    COURTS = {
        "uksc": "UK Supreme Court",
        "ukhl": "UK House of Lords",
        "ewca": "England and Wales Court of Appeal",
        "ewhc": "England and Wales High Court",
        "ewcop": "England and Wales Court of Protection",
        "ukut": "UK Upper Tribunal",
        "ukftt": "UK First-tier Tribunal",
        "scot": "Scottish Courts",
        "nica": "Northern Ireland Court of Appeal",
        "nie": "Employment Tribunals (NI)",
    }

    def __init__(self, rate_limit: float = 1.0):
        """Initialize the BAILII scraper.

        Args:
            rate_limit: Requests per second (be respectful, default 1/sec)
        """
        self.rate_limit = rate_limit
        self._last_request = 0.0
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def source_name(self) -> str:
        return "bailii"

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={
                    "User-Agent": "UK-OSINT-Nexus/0.1.0 (Research Tool)",
                    "Accept": "text/html,application/xhtml+xml",
                },
                timeout=30.0,
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _rate_limit(self) -> None:
        """Enforce rate limiting."""
        import time

        now = time.monotonic()
        elapsed = now - self._last_request
        min_interval = 1.0 / self.rate_limit
        if elapsed < min_interval:
            await asyncio.sleep(min_interval - elapsed)
        self._last_request = time.monotonic()

    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse various date formats from BAILII."""
        if not date_str:
            return None

        # Try various formats
        import re
        from datetime import datetime

        # Format: [2024] or (2024)
        year_match = re.search(r"[\[\(](\d{4})[\]\)]", date_str)
        if year_match:
            try:
                return date(int(year_match.group(1)), 1, 1)
            except ValueError:
                pass

        # Format: 15 January 2024
        try:
            return datetime.strptime(date_str.strip(), "%d %B %Y").date()
        except ValueError:
            pass

        # Format: 15/01/2024
        try:
            return datetime.strptime(date_str.strip(), "%d/%m/%Y").date()
        except ValueError:
            pass

        return None

    def _parse_neutral_citation(self, text: str) -> Optional[str]:
        """Extract neutral citation from text.

        Neutral citations look like: [2024] UKSC 1, [2023] EWCA Civ 123
        """
        pattern = r"\[\d{4}\]\s+[A-Z]+\s+(?:Civ|Crim|Ch|QB|KB|Fam|Admin|Pat|Costs|TCC|IPEC|Comm)?\s*\d+"
        match = re.search(pattern, text)
        if match:
            return match.group(0)
        return None

    def _parse_case_name(self, title: str) -> str:
        """Clean up case name from search results."""
        # Remove citation if present at start
        title = re.sub(r"^\[\d{4}\]\s+[A-Z]+\s+\d+\s*[-:]\s*", "", title)
        # Remove common prefixes
        title = re.sub(r"^(Re|In the matter of)\s+", "", title, flags=re.IGNORECASE)
        return title.strip()

    def _extract_court(self, url: str, text: str) -> Optional[str]:
        """Extract court name from URL or text."""
        url_lower = url.lower()

        for code, name in self.COURTS.items():
            if code in url_lower:
                return name

        # Try to extract from citation
        citation_courts = {
            "UKSC": "UK Supreme Court",
            "UKHL": "UK House of Lords",
            "EWCA Civ": "Court of Appeal (Civil Division)",
            "EWCA Crim": "Court of Appeal (Criminal Division)",
            "EWHC": "High Court",
            "UKUT": "Upper Tribunal",
            "UKFTT": "First-tier Tribunal",
        }

        for code, name in citation_courts.items():
            if code in text:
                return name

        return None

    async def search(
        self,
        query: str,
        court: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        max_results: int = 20,
    ) -> list[LegalCase]:
        """Search BAILII for cases.

        Args:
            query: Search terms (case name, party name, keywords)
            court: Optional court filter (e.g., 'uksc', 'ewca', 'ewhc')
            date_from: Optional start date filter
            date_to: Optional end date filter
            max_results: Maximum number of results to return

        Returns:
            List of LegalCase objects
        """
        await self._rate_limit()
        client = await self._get_client()

        # Build search parameters
        params = {
            "query": query,
            "mask_path": "",  # Search all databases
            "show": str(max_results),
            "sort": "rank",  # Sort by relevance
        }

        # Add court filter if specified
        if court:
            court_lower = court.lower()
            if court_lower in self.COURTS:
                # BAILII uses path-based filtering
                params["mask_path"] = f"/{court_lower}/"

        try:
            response = await client.get(self.SEARCH_URL, params=params)
            response.raise_for_status()
            html = response.text
        except httpx.HTTPError:
            return []

        return self._parse_search_results(html)

    def _parse_search_results(self, html: str) -> list[LegalCase]:
        """Parse BAILII search results HTML."""
        soup = BeautifulSoup(html, "html.parser")
        cases = []

        # Find search result items - BAILII uses various formats
        # Look for links to case documents
        for link in soup.find_all("a", href=True):
            href = link.get("href", "")

            # Filter for actual case links (contain year and case number patterns)
            if not re.search(r"/\d{4}/", href):
                continue
            if not any(court in href.lower() for court in ["uk", "ew", "scot", "ni"]):
                continue

            # Get case title
            title_text = link.get_text(strip=True)
            if not title_text or len(title_text) < 5:
                continue

            # Skip navigation and utility links
            if title_text.lower() in ["next", "previous", "home", "search"]:
                continue

            # Extract information
            full_url = urljoin(self.BASE_URL, href)
            neutral_citation = self._parse_neutral_citation(title_text)
            case_name = self._parse_case_name(title_text)
            court = self._extract_court(href, title_text)

            # Try to extract date from citation
            case_date = None
            if neutral_citation:
                case_date = self._parse_date(neutral_citation)

            # Look for date in surrounding text
            parent = link.parent
            if parent:
                parent_text = parent.get_text()
                if not case_date:
                    case_date = self._parse_date(parent_text)

            case = LegalCase(
                source=self.source_name,
                case_id=href,
                neutral_citation=neutral_citation,
                case_name=case_name or title_text,
                court=court,
                date_judgment=case_date,
                full_text_url=full_url,
                raw_data={"title": title_text, "url": full_url},
            )
            cases.append(case)

        # Deduplicate by URL
        seen_urls = set()
        unique_cases = []
        for case in cases:
            if case.full_text_url not in seen_urls:
                seen_urls.add(case.full_text_url)
                unique_cases.append(case)

        return unique_cases

    async def get_case(self, url: str) -> Optional[LegalCase]:
        """Get detailed case information from a BAILII case URL.

        Args:
            url: Full URL to the case on BAILII

        Returns:
            LegalCase with additional details, or None if not found
        """
        await self._rate_limit()
        client = await self._get_client()

        try:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text
        except httpx.HTTPError:
            return None

        return self._parse_case_page(html, url)

    def _parse_case_page(self, html: str, url: str) -> LegalCase:
        """Parse a full BAILII case page."""
        soup = BeautifulSoup(html, "html.parser")

        # Extract title
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else "Unknown Case"

        # Clean title - remove "BAILII" suffix
        title = re.sub(r"\s*-?\s*BAILII$", "", title)

        # Extract neutral citation
        neutral_citation = self._parse_neutral_citation(title)

        # Try to find case name
        case_name = self._parse_case_name(title)

        # Extract judges - look for common patterns
        judges = []
        text = soup.get_text()

        # Pattern: "Before: Lord Justice X, Mr Justice Y"
        before_match = re.search(
            r"Before[:\s]+([A-Z][^.]+?)(?:\n|$|Hearing)", text, re.IGNORECASE
        )
        if before_match:
            judges_text = before_match.group(1)
            # Split on common separators
            for judge in re.split(r",|\band\b", judges_text):
                judge = judge.strip()
                if judge and len(judge) > 3:
                    judges.append(judge)

        # Extract parties - look for "v" or "v."
        parties = []
        v_match = re.search(r"([A-Z][^v]+)\s+v\.?\s+([A-Z][^\[]+)", title)
        if v_match:
            parties = [v_match.group(1).strip(), v_match.group(2).strip()]

        # Extract date
        case_date = self._parse_date(text)

        # Extract court
        court = self._extract_court(url, title)

        # Get summary (first paragraph after case details)
        summary = None
        # Look for judgment content
        for p in soup.find_all("p"):
            p_text = p.get_text(strip=True)
            # Skip short paragraphs and boilerplate
            if len(p_text) > 100 and not p_text.startswith(("BAILII", "Neutral Citation")):
                summary = p_text[:500] + "..." if len(p_text) > 500 else p_text
                break

        return LegalCase(
            source=self.source_name,
            case_id=url,
            neutral_citation=neutral_citation,
            case_name=case_name,
            court=court,
            date_judgment=case_date,
            judges=judges,
            parties=parties,
            summary=summary,
            full_text_url=url,
            raw_data={"title": title, "url": url},
        )

    async def search_by_party(self, party_name: str, max_results: int = 20) -> list[LegalCase]:
        """Search for cases involving a specific party.

        Args:
            party_name: Name of person or company
            max_results: Maximum results to return

        Returns:
            List of cases involving the party
        """
        # Use quoted search for exact party name matching
        query = f'"{party_name}"'
        return await self.search(query, max_results=max_results)

    async def search_recent(
        self, court: Optional[str] = None, days: int = 30, max_results: int = 20
    ) -> list[LegalCase]:
        """Search for recent cases.

        Args:
            court: Optional court filter
            days: Number of days to look back
            max_results: Maximum results

        Returns:
            List of recent cases
        """
        # BAILII doesn't have great date filtering in search
        # We search broadly and filter results
        from datetime import datetime, timedelta

        cutoff = datetime.now().date() - timedelta(days=days)

        # Search with empty query to get recent
        cases = await self.search("*", court=court, max_results=max_results * 2)

        # Filter by date
        recent = [c for c in cases if c.date_judgment and c.date_judgment >= cutoff]

        return recent[:max_results]

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
