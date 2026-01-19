"""The Gazette (London, Edinburgh, Belfast) API client.

API Documentation: https://www.thegazette.co.uk/data
Rate Limit: Not defined, be reasonable
Authentication: None required for basic searches

Coverage:
- Official public record notifications
- Insolvency notices (bankruptcies, winding up)
- Company notices (change of name, strike off)
- State notices
- Honours and awards

Note: The Gazette has an Atom feed API that we can query.
"""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel

from .base import BaseAPIClient


class GazetteNotice(BaseModel):
    """A notice from The Gazette."""

    source: str = "gazette"

    # Notice identification
    notice_id: Optional[str] = None
    notice_code: Optional[str] = None
    notice_type: Optional[str] = None  # 'Insolvency', 'Company Law', etc.
    notice_category: Optional[str] = None

    # Content
    title: str
    content: Optional[str] = None
    summary: Optional[str] = None

    # Edition
    edition: Optional[str] = None  # 'London', 'Edinburgh', 'Belfast'
    issue_number: Optional[str] = None
    page_number: Optional[str] = None

    # Dates
    publication_date: Optional[date] = None
    content_date: Optional[date] = None

    # Links
    notice_url: Optional[str] = None
    pdf_url: Optional[str] = None

    # For insolvency notices
    debtor_name: Optional[str] = None
    trading_name: Optional[str] = None
    address: Optional[str] = None
    court: Optional[str] = None
    case_number: Optional[str] = None

    # For company notices
    company_name: Optional[str] = None
    company_number: Optional[str] = None

    raw_data: Optional[dict] = None


class GazetteClient(BaseAPIClient):
    """Client for The Gazette official notices."""

    BASE_URL = "https://www.thegazette.co.uk"

    NOTICE_TYPES = {
        "2903": "Winding-up Petitions",
        "2904": "Winding-up Orders",
        "2905": "Voluntary Arrangements",
        "2906": "Administration",
        "2907": "Receivership",
        "2908": "Bankruptcy Orders",
        "2909": "Bankruptcy Petitions",
        "2450": "Company Incorporation",
        "2451": "Company Strike-off",
        "2452": "Company Name Change",
    }

    def __init__(self):
        super().__init__(
            base_url=self.BASE_URL,
            api_key=None,
            rate_limit=1.0,
        )

    @property
    def source_name(self) -> str:
        return "gazette"

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse date string."""
        if not date_str:
            return None
        try:
            # Handle various formats
            for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"]:
                try:
                    return datetime.strptime(date_str.split("+")[0].split("Z")[0], fmt.split("+")[0]).date()
                except ValueError:
                    continue
            return None
        except Exception:
            return None

    def _parse_notice_from_atom(self, entry: dict) -> GazetteNotice:
        """Parse notice from Atom feed entry."""
        # Extract notice type from category
        notice_type = None
        notice_code = None
        categories = entry.get("categories", [])
        for cat in categories:
            if cat.get("scheme") == "https://www.thegazette.co.uk/def/publication#702":
                notice_type = cat.get("term")
            elif cat.get("scheme") == "notice-type":
                notice_code = cat.get("term")

        # Extract links
        notice_url = None
        pdf_url = None
        for link in entry.get("links", []):
            if link.get("type") == "text/html":
                notice_url = link.get("href")
            elif link.get("type") == "application/pdf":
                pdf_url = link.get("href")

        return GazetteNotice(
            source=self.source_name,
            notice_id=entry.get("id"),
            notice_code=notice_code,
            notice_type=notice_type,
            title=entry.get("title", ""),
            summary=entry.get("summary"),
            content=entry.get("content"),
            publication_date=self._parse_date(entry.get("published")),
            notice_url=notice_url,
            pdf_url=pdf_url,
            raw_data=entry,
        )

    async def search(self, query: str, **kwargs) -> list[GazetteNotice]:
        """Search gazette notices."""
        return await self.search_notices(query, **kwargs)

    async def search_notices(
        self,
        query: str,
        notice_type: Optional[str] = None,
        edition: Optional[str] = None,  # 'london', 'edinburgh', 'belfast'
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        page: int = 1,
        results_per_page: int = 20,
    ) -> list[GazetteNotice]:
        """Search gazette notices.

        Args:
            query: Search term
            notice_type: Notice type code (see NOTICE_TYPES)
            edition: Gazette edition
            start_date: Filter from date
            end_date: Filter to date
            page: Page number
            results_per_page: Results per page

        Returns:
            List of GazetteNotice objects
        """
        try:
            params = {
                "text": query,
                "start": (page - 1) * results_per_page + 1,
                "results-page-size": results_per_page,
            }

            if notice_type:
                params["categorycode"] = notice_type
            if edition:
                params["edition"] = edition.lower()
            if start_date:
                params["start-publish-date"] = start_date.isoformat()
            if end_date:
                params["end-publish-date"] = end_date.isoformat()

            # Use Atom feed endpoint
            import httpx

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.BASE_URL}/notice/search.atom",
                    params=params,
                    headers={"Accept": "application/atom+xml"},
                )

                if response.status_code != 200:
                    return []

                # Parse Atom XML
                return self._parse_atom_feed(response.text)

        except Exception as e:
            import sys
            print(f"[Gazette] Search error: {str(e)[:100]}", file=sys.stderr)
            return []

    def _parse_atom_feed(self, xml_content: str) -> list[GazetteNotice]:
        """Parse Atom feed XML."""
        import xml.etree.ElementTree as ET

        notices = []

        try:
            root = ET.fromstring(xml_content)

            # Atom namespace
            ns = {"atom": "http://www.w3.org/2005/Atom"}

            for entry in root.findall("atom:entry", ns):
                entry_data = {
                    "id": entry.findtext("atom:id", namespaces=ns),
                    "title": entry.findtext("atom:title", namespaces=ns),
                    "summary": entry.findtext("atom:summary", namespaces=ns),
                    "content": entry.findtext("atom:content", namespaces=ns),
                    "published": entry.findtext("atom:published", namespaces=ns),
                    "updated": entry.findtext("atom:updated", namespaces=ns),
                    "links": [],
                    "categories": [],
                }

                for link in entry.findall("atom:link", ns):
                    entry_data["links"].append({
                        "href": link.get("href"),
                        "type": link.get("type"),
                        "rel": link.get("rel"),
                    })

                for cat in entry.findall("atom:category", ns):
                    entry_data["categories"].append({
                        "term": cat.get("term"),
                        "scheme": cat.get("scheme"),
                    })

                notices.append(self._parse_notice_from_atom(entry_data))

        except Exception as e:
            import sys
            print(f"[Gazette] XML parse error: {str(e)[:100]}", file=sys.stderr)

        return notices

    async def search_insolvency_notices(
        self,
        name: str,
        notice_type: Optional[str] = None,
    ) -> list[GazetteNotice]:
        """Search for insolvency notices.

        Args:
            name: Person or company name
            notice_type: Specific insolvency type code

        Returns:
            List of insolvency notices
        """
        # Search insolvency category
        return await self.search_notices(
            query=name,
            notice_type=notice_type or "2900",  # Insolvency category
        )

    async def search_company_notices(
        self,
        company_name: Optional[str] = None,
        company_number: Optional[str] = None,
    ) -> list[GazetteNotice]:
        """Search for company law notices.

        Args:
            company_name: Company name
            company_number: Companies House number

        Returns:
            List of company notices
        """
        query = company_name or company_number or ""
        return await self.search_notices(
            query=query,
            notice_type="2450",  # Company law category
        )

    async def get_winding_up_petitions(
        self,
        company_name: Optional[str] = None,
    ) -> list[GazetteNotice]:
        """Get winding-up petition notices.

        Args:
            company_name: Optional company name filter

        Returns:
            List of winding-up petitions
        """
        return await self.search_notices(
            query=company_name or "*",
            notice_type="2903",  # Winding-up petitions
        )

    async def get_bankruptcy_orders(
        self,
        name: Optional[str] = None,
    ) -> list[GazetteNotice]:
        """Get bankruptcy order notices.

        Args:
            name: Optional name filter

        Returns:
            List of bankruptcy orders
        """
        return await self.search_notices(
            query=name or "*",
            notice_type="2908",  # Bankruptcy orders
        )
