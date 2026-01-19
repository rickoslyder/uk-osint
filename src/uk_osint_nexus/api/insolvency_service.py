"""Insolvency Service Individual Insolvency Register API client.

API Documentation: https://www.insolvencydirect.bis.gov.uk/IESdatabase/
Rate Limit: Not defined, be reasonable
Authentication: None required

Endpoints used:
- Search the Individual Insolvency Register

Coverage:
- Bankruptcies
- Individual Voluntary Arrangements (IVAs)
- Debt Relief Orders (DROs)
- Bankruptcy Restriction Orders/Undertakings

Note: This covers individual insolvencies only. Company insolvencies
are handled through Companies House.
"""

from datetime import date
from typing import Optional

from pydantic import BaseModel

from .base import BaseAPIClient


class InsolvencyRecord(BaseModel):
    """An individual insolvency record."""

    source: str = "insolvency_service"

    # Person details
    surname: str
    forenames: Optional[str] = None
    title: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[date] = None

    # Address
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    address_line_3: Optional[str] = None
    town: Optional[str] = None
    postcode: Optional[str] = None

    # Aliases
    aliases: list[str] = []
    trading_names: list[str] = []

    # Insolvency details
    case_type: str  # 'Bankruptcy', 'IVA', 'DRO', 'BRO', 'BRU'
    case_number: Optional[str] = None
    case_year: Optional[int] = None
    court: Optional[str] = None

    # Key dates
    start_date: Optional[date] = None  # Date of order/arrangement
    discharge_date: Optional[date] = None  # When discharged
    annulment_date: Optional[date] = None  # If annulled

    # Status
    status: Optional[str] = None  # 'Current', 'Discharged', 'Annulled'

    # For BROs/BRUs
    restriction_type: Optional[str] = None
    restriction_start: Optional[date] = None
    restriction_end: Optional[date] = None

    # Practitioner
    insolvency_practitioner: Optional[str] = None
    practitioner_firm: Optional[str] = None
    practitioner_address: Optional[str] = None

    raw_data: Optional[dict] = None


class InsolvencyServiceClient(BaseAPIClient):
    """Client for the Insolvency Service Individual Insolvency Register.

    Note: The official register uses a web form, so we scrape the results.
    An alternative is the Gov.uk API when available.
    """

    BASE_URL = "https://www.insolvencydirect.bis.gov.uk"

    def __init__(self):
        super().__init__(
            base_url=self.BASE_URL,
            api_key=None,
            rate_limit=2.0,  # Conservative rate limit
        )

    @property
    def source_name(self) -> str:
        return "insolvency_service"

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse date string to date object."""
        if not date_str:
            return None
        try:
            # Handle various date formats
            if "/" in date_str:
                parts = date_str.split("/")
                if len(parts) == 3:
                    return date(int(parts[2]), int(parts[1]), int(parts[0]))
            return date.fromisoformat(date_str)
        except (ValueError, IndexError):
            return None

    def _parse_record(self, data: dict) -> InsolvencyRecord:
        """Parse insolvency record from scraped data."""
        return InsolvencyRecord(
            source=self.source_name,
            surname=data.get("surname", ""),
            forenames=data.get("forenames"),
            title=data.get("title"),
            gender=data.get("gender"),
            date_of_birth=self._parse_date(data.get("dob")),
            address_line_1=data.get("address1"),
            address_line_2=data.get("address2"),
            address_line_3=data.get("address3"),
            town=data.get("town"),
            postcode=data.get("postcode"),
            aliases=data.get("aliases", []),
            trading_names=data.get("trading_names", []),
            case_type=data.get("type", "Unknown"),
            case_number=data.get("case_number"),
            case_year=data.get("case_year"),
            court=data.get("court"),
            start_date=self._parse_date(data.get("start_date")),
            discharge_date=self._parse_date(data.get("discharge_date")),
            annulment_date=self._parse_date(data.get("annulment_date")),
            status=data.get("status"),
            restriction_type=data.get("restriction_type"),
            restriction_start=self._parse_date(data.get("restriction_start")),
            restriction_end=self._parse_date(data.get("restriction_end")),
            insolvency_practitioner=data.get("practitioner"),
            practitioner_firm=data.get("practitioner_firm"),
            practitioner_address=data.get("practitioner_address"),
            raw_data=data,
        )

    async def search(self, query: str, **kwargs) -> list[InsolvencyRecord]:
        """Search for insolvency records by name."""
        return await self.search_by_name(query, **kwargs)

    async def search_by_name(
        self,
        surname: str,
        forenames: Optional[str] = None,
        include_aliases: bool = True,
    ) -> list[InsolvencyRecord]:
        """Search the Individual Insolvency Register by name.

        Args:
            surname: Surname to search for
            forenames: Optional forenames
            include_aliases: Whether to search aliases too

        Returns:
            List of InsolvencyRecord objects
        """
        try:
            from bs4 import BeautifulSoup

            # The IIR uses POST requests to a search form
            form_data = {
                "surname": surname,
                "forename": forenames or "",
                "includealiases": "1" if include_aliases else "0",
            }

            # First get the search page to establish session
            await self.get("/IESdatabase/viewdirectory.asp")

            # Then POST the search
            response_text = await self._post_form(
                "/IESdatabase/viewdebtor-results-t.asp",
                form_data
            )

            if not response_text:
                return []

            # Parse HTML results
            soup = BeautifulSoup(response_text, "html.parser")
            records = []

            # Find result rows (table structure varies)
            result_table = soup.find("table", {"class": "results"}) or soup.find("table")
            if not result_table:
                return []

            rows = result_table.find_all("tr")[1:]  # Skip header

            for row in rows:
                cells = row.find_all("td")
                if len(cells) >= 4:
                    data = {
                        "surname": cells[0].get_text(strip=True) if len(cells) > 0 else "",
                        "forenames": cells[1].get_text(strip=True) if len(cells) > 1 else None,
                        "type": cells[2].get_text(strip=True) if len(cells) > 2 else "Unknown",
                        "status": cells[3].get_text(strip=True) if len(cells) > 3 else None,
                        "start_date": cells[4].get_text(strip=True) if len(cells) > 4 else None,
                    }
                    records.append(self._parse_record(data))

            return records

        except Exception as e:
            import sys
            error_msg = str(e)[:100]
            print(f"[Insolvency Service] Error: {error_msg}...", file=sys.stderr)
            return []

    async def _post_form(self, path: str, data: dict) -> Optional[str]:
        """POST form data and return response text."""
        import httpx

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.BASE_URL}{path}",
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    follow_redirects=True,
                )
                if response.status_code == 200:
                    return response.text
        except Exception:
            pass
        return None

    async def check_bankruptcy(self, surname: str, forenames: Optional[str] = None) -> dict:
        """Quick check if someone has bankruptcy records.

        Args:
            surname: Surname to check
            forenames: Optional forenames

        Returns:
            Dict with check results
        """
        records = await self.search_by_name(surname, forenames)

        bankruptcies = [r for r in records if r.case_type == "Bankruptcy"]
        ivas = [r for r in records if r.case_type == "IVA"]
        dros = [r for r in records if r.case_type == "DRO"]
        restrictions = [r for r in records if r.case_type in ("BRO", "BRU")]

        return {
            "name": f"{forenames or ''} {surname}".strip(),
            "has_records": len(records) > 0,
            "total_records": len(records),
            "bankruptcies": len(bankruptcies),
            "ivas": len(ivas),
            "dros": len(dros),
            "restrictions": len(restrictions),
            "records": records,
        }
