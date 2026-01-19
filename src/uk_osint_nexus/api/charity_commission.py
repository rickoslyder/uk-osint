"""Charity Commission API client.

API Documentation: https://api-portal.charitycommission.gov.uk/
Rate Limit: Not strictly defined, be reasonable
Authentication: API key via Ocp-Apim-Subscription-Key header

FREE endpoints used:
- GetCharitiesByName - Search charities by name
- GetCharitiesByKeyword - Search charities by keyword
- GetCharityByRegisteredCharityNumber - Get charity details
- GetCharityTrustees - Get charity trustees (valuable for correlation)

Coverage:
- 170,000+ registered charities in England and Wales
- Charity finances, activities, trustees
- Registration and removal dates
"""

from datetime import date
from typing import Optional

from pydantic import BaseModel

from .base import BaseAPIClient


class Trustee(BaseModel):
    """A charity trustee."""

    source: str = "charity_commission"
    charity_number: int
    charity_name: Optional[str] = None
    trustee_name: str
    trustee_id: Optional[str] = None
    is_chair: bool = False
    appointment_date: Optional[date] = None
    raw_data: Optional[dict] = None


class Charity(BaseModel):
    """A registered charity."""

    source: str = "charity_commission"
    charity_number: int
    charity_name: str
    charity_status: Optional[str] = None  # 'Registered', 'Removed'
    date_of_registration: Optional[date] = None
    date_of_removal: Optional[date] = None

    # Contact details
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None

    # Activities
    activities: Optional[str] = None
    classification: Optional[list[str]] = None

    # Financial
    income: Optional[float] = None
    spending: Optional[float] = None
    financial_year_end: Optional[date] = None

    # People
    trustees: list[Trustee] = []

    # Linked companies (for correlation)
    linked_company_number: Optional[str] = None

    raw_data: Optional[dict] = None


class CharityCommissionClient(BaseAPIClient):
    """Client for the Charity Commission API."""

    BASE_URL = "https://api.charitycommission.gov.uk/register/api"

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(
            base_url=self.BASE_URL,
            api_key=api_key,
            rate_limit=2.0,  # Conservative rate limit
        )

    @property
    def source_name(self) -> str:
        return "charity_commission"

    def _get_headers(self) -> dict:
        """Override to use Ocp-Apim-Subscription-Key header."""
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Ocp-Apim-Subscription-Key"] = self.api_key
        return headers

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse date string to date object."""
        if not date_str:
            return None
        try:
            # Handle various date formats
            if "T" in date_str:
                date_str = date_str.split("T")[0]
            return date.fromisoformat(date_str)
        except ValueError:
            return None

    def _parse_charity(self, data: dict) -> Charity:
        """Parse charity data from API response."""
        # Extract address components
        address_parts = []
        for key in ["line1", "line2", "line3", "line4", "line5", "postcode"]:
            if data.get(key):
                address_parts.append(data[key])
        address = ", ".join(address_parts) if address_parts else None

        return Charity(
            source=self.source_name,
            charity_number=data.get("reg_charity_number") or data.get("registered_charity_number", 0),
            charity_name=data.get("charity_name", ""),
            charity_status=data.get("reg_status") or data.get("charity_registration_status"),
            date_of_registration=self._parse_date(data.get("date_of_registration")),
            date_of_removal=self._parse_date(data.get("date_of_removal")),
            address=address,
            phone=data.get("phone"),
            email=data.get("email"),
            website=data.get("web"),
            activities=data.get("activities"),
            income=data.get("latest_income"),
            spending=data.get("latest_expenditure"),
            linked_company_number=data.get("cio_company_number"),
            raw_data=data,
        )

    def _parse_trustee(self, data: dict, charity_number: int, charity_name: str = None) -> Trustee:
        """Parse trustee data from API response."""
        return Trustee(
            source=self.source_name,
            charity_number=charity_number,
            charity_name=charity_name,
            trustee_name=data.get("trustee_name", ""),
            trustee_id=data.get("trustee_id"),
            is_chair=data.get("trustee_is_chair", False),
            raw_data=data,
        )

    async def search(self, query: str, **kwargs) -> list[Charity]:
        """Search for charities by name or keyword."""
        return await self.search_charities(query, **kwargs)

    async def search_charities(
        self,
        query: str,
        search_type: str = "name",  # 'name' or 'keyword'
        page: int = 0,
        page_size: int = 20,
    ) -> list[Charity]:
        """Search for charities by name or keyword.

        Args:
            query: Search term
            search_type: 'name' for exact name search, 'keyword' for broader search
            page: Page number (0-indexed)
            page_size: Results per page

        Returns:
            List of Charity objects
        """
        try:
            if search_type == "keyword":
                endpoint = f"/allcharitydetailsV2/Keyword/{query}/{page}/{page_size}"
            else:
                endpoint = f"/allcharitydetailsV2/Name/{query}/{page}/{page_size}"

            data = await self.get(endpoint)

            charities = []
            # Handle both list and single result responses
            if isinstance(data, list):
                for item in data:
                    charities.append(self._parse_charity(item))
            elif isinstance(data, dict):
                if "charities" in data:
                    for item in data["charities"]:
                        charities.append(self._parse_charity(item))
                else:
                    charities.append(self._parse_charity(data))

            return charities

        except Exception as e:
            import sys
            error_msg = str(e)[:100]
            print(f"[Charity Commission] API error: {error_msg}...", file=sys.stderr)
            return []

    async def get_charity(self, charity_number: int) -> Optional[Charity]:
        """Get detailed charity information by registration number.

        Args:
            charity_number: The charity registration number

        Returns:
            Charity details or None if not found
        """
        try:
            data = await self.get(f"/allcharitydetailsV2/RegisteredCharityNumber/{charity_number}/0")

            if not data:
                return None

            # Handle list or single response
            if isinstance(data, list) and data:
                data = data[0]

            return self._parse_charity(data)

        except Exception:
            return None

    async def get_trustees(self, charity_number: int) -> list[Trustee]:
        """Get trustees for a charity.

        Args:
            charity_number: The charity registration number

        Returns:
            List of Trustee objects
        """
        try:
            data = await self.get(f"/TrusteeByCharityRegNo/{charity_number}")

            trustees = []
            if isinstance(data, list):
                for item in data:
                    trustees.append(self._parse_trustee(item, charity_number))
            elif isinstance(data, dict) and "trustees" in data:
                for item in data["trustees"]:
                    trustees.append(self._parse_trustee(item, charity_number))

            return trustees

        except Exception:
            return []

    async def get_charity_with_trustees(self, charity_number: int) -> Optional[Charity]:
        """Get charity details including trustees.

        Convenience method that fetches both in parallel.
        """
        charity = await self.get_charity(charity_number)
        if charity:
            charity.trustees = await self.get_trustees(charity_number)
        return charity

    async def search_by_trustee_name(self, name: str) -> list[Charity]:
        """Search for charities by trustee name.

        This is useful for finding all charities a person is involved with.
        Note: This may require iterating through results client-side.
        """
        # The API doesn't have a direct trustee search, so we search by keyword
        # and then filter by trustee name
        charities = await self.search_charities(name, search_type="keyword")

        # For each charity, check trustees
        matched = []
        for charity in charities:
            trustees = await self.get_trustees(charity.charity_number)
            for trustee in trustees:
                if name.lower() in trustee.trustee_name.lower():
                    charity.trustees = trustees
                    matched.append(charity)
                    break

        return matched
