"""Companies House API client.

API Documentation: https://developer.company-information.service.gov.uk/
Rate Limit: 600 requests per 5 minutes (2/second average)
Authentication: API key via HTTP Basic Auth (key as username, no password)

FREE endpoints used:
- /search/companies - Search for companies by name
- /search/officers - Search for officers/directors by name
- /company/{company_number} - Get company profile
- /company/{company_number}/officers - Get company officers
- /company/{company_number}/filing-history - Get filing history
- /officers/{officer_id}/appointments - Get all appointments for an officer
"""

import base64
from datetime import date
from typing import Optional

from ..models.entities import Address, Company, Officer
from .base import BaseAPIClient


class CompaniesHouseClient(BaseAPIClient):
    """Client for the Companies House API."""

    BASE_URL = "https://api.company-information.service.gov.uk"

    def __init__(self, api_key: Optional[str] = None):
        # API key is passed as username with empty password in Basic Auth
        encoded_key = None
        if api_key:
            encoded_key = base64.b64encode(f"{api_key}:".encode()).decode()
        super().__init__(
            base_url=self.BASE_URL,
            api_key=encoded_key,
            rate_limit=2.0,  # 600 req / 300 sec = 2/sec
        )
        self._raw_api_key = api_key

    @property
    def source_name(self) -> str:
        return "companies_house"

    def _parse_address(self, addr_data: dict) -> Address:
        """Parse Companies House address format."""
        return Address(
            address_line_1=addr_data.get("address_line_1"),
            address_line_2=addr_data.get("address_line_2"),
            locality=addr_data.get("locality"),
            region=addr_data.get("region"),
            postal_code=addr_data.get("postal_code"),
            country=addr_data.get("country", "United Kingdom"),
        )

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse ISO date string to date object."""
        if not date_str:
            return None
        try:
            return date.fromisoformat(date_str)
        except ValueError:
            return None

    def _parse_company(self, data: dict) -> Company:
        """Parse company data from API response."""
        address = None
        if "registered_office_address" in data:
            address = self._parse_address(data["registered_office_address"])

        previous_names = []
        if "previous_company_names" in data:
            previous_names = [
                {
                    "name": pn.get("name"),
                    "effective_from": pn.get("effective_from"),
                    "ceased_on": pn.get("ceased_on"),
                }
                for pn in data["previous_company_names"]
            ]

        return Company(
            source=self.source_name,
            company_number=data.get("company_number", ""),
            company_name=data.get("company_name") or data.get("title", ""),
            company_status=data.get("company_status"),
            company_type=data.get("type"),
            date_of_creation=self._parse_date(data.get("date_of_creation")),
            date_of_cessation=self._parse_date(data.get("date_of_cessation")),
            registered_office_address=address,
            sic_codes=data.get("sic_codes", []),
            previous_names=previous_names,
            has_charges=data.get("has_charges", False),
            has_insolvency_history=data.get("has_insolvency_history", False),
            raw_data=data,
        )

    def _parse_officer(self, data: dict, company_number: Optional[str] = None) -> Officer:
        """Parse officer data from API response."""
        address = None
        if "address" in data:
            address = self._parse_address(data["address"])

        dob = None
        if "date_of_birth" in data:
            dob = data["date_of_birth"]

        # Extract company info from links if available
        comp_num = company_number
        comp_name = None
        if "appointed_to" in data:
            comp_num = data["appointed_to"].get("company_number", company_number)
            comp_name = data["appointed_to"].get("company_name")

        return Officer(
            source=self.source_name,
            officer_id=data.get("links", {}).get("officer", {}).get("appointments", "").split("/")[
                -2
            ]
            if "links" in data
            else None,
            name=data.get("name", ""),
            role=data.get("officer_role", "unknown"),
            appointed_on=self._parse_date(data.get("appointed_on")),
            resigned_on=self._parse_date(data.get("resigned_on")),
            date_of_birth=dob,
            nationality=data.get("nationality"),
            country_of_residence=data.get("country_of_residence"),
            occupation=data.get("occupation"),
            address=address,
            company_number=comp_num,
            company_name=comp_name,
            raw_data=data,
        )

    async def search(self, query: str, **kwargs) -> list[Company]:
        """Search for companies by name."""
        return await self.search_companies(query, **kwargs)

    async def search_companies(
        self,
        query: str,
        items_per_page: int = 20,
        start_index: int = 0,
    ) -> list[Company]:
        """Search for companies by name.

        Args:
            query: Company name to search for
            items_per_page: Number of results (max 100)
            start_index: Starting offset for pagination
        """
        params = {
            "q": query,
            "items_per_page": min(items_per_page, 100),
            "start_index": start_index,
        }
        data = await self.get("/search/companies", params=params)

        companies = []
        for item in data.get("items", []):
            companies.append(self._parse_company(item))
        return companies

    async def search_officers(
        self,
        query: str,
        items_per_page: int = 20,
        start_index: int = 0,
    ) -> list[Officer]:
        """Search for officers/directors by name.

        Args:
            query: Officer name to search for
            items_per_page: Number of results (max 100)
            start_index: Starting offset for pagination
        """
        params = {
            "q": query,
            "items_per_page": min(items_per_page, 100),
            "start_index": start_index,
        }
        data = await self.get("/search/officers", params=params)

        officers = []
        for item in data.get("items", []):
            officers.append(self._parse_officer(item))
        return officers

    async def get_company(self, company_number: str) -> Company:
        """Get detailed company profile by company number.

        Args:
            company_number: The 8-character company registration number
        """
        # Normalize company number (pad with zeros)
        company_number = company_number.upper().zfill(8)
        data = await self.get(f"/company/{company_number}")
        return self._parse_company(data)

    async def get_company_officers(
        self,
        company_number: str,
        items_per_page: int = 50,
        start_index: int = 0,
        register_type: Optional[str] = None,
    ) -> list[Officer]:
        """Get officers for a company.

        Args:
            company_number: The company registration number
            items_per_page: Number of results
            start_index: Starting offset
            register_type: Optional filter ('directors', 'secretaries', etc.)
        """
        company_number = company_number.upper().zfill(8)
        params = {
            "items_per_page": items_per_page,
            "start_index": start_index,
        }
        if register_type:
            params["register_type"] = register_type

        data = await self.get(f"/company/{company_number}/officers", params=params)

        officers = []
        for item in data.get("items", []):
            officers.append(self._parse_officer(item, company_number=company_number))
        return officers

    async def get_officer_appointments(
        self,
        officer_id: str,
        items_per_page: int = 50,
        start_index: int = 0,
    ) -> list[Officer]:
        """Get all company appointments for an officer.

        Useful for finding all companies a person is involved with.

        Args:
            officer_id: The officer's unique ID from Companies House
            items_per_page: Number of results
            start_index: Starting offset
        """
        params = {
            "items_per_page": items_per_page,
            "start_index": start_index,
        }
        data = await self.get(f"/officers/{officer_id}/appointments", params=params)

        appointments = []
        for item in data.get("items", []):
            appointments.append(self._parse_officer(item))
        return appointments

    async def get_company_filing_history(
        self,
        company_number: str,
        items_per_page: int = 25,
        start_index: int = 0,
        category: Optional[str] = None,
    ) -> list[dict]:
        """Get filing history for a company.

        Args:
            company_number: The company registration number
            items_per_page: Number of results
            start_index: Starting offset
            category: Filter by category ('accounts', 'confirmation-statement', etc.)
        """
        company_number = company_number.upper().zfill(8)
        params = {
            "items_per_page": items_per_page,
            "start_index": start_index,
        }
        if category:
            params["category"] = category

        data = await self.get(f"/company/{company_number}/filing-history", params=params)
        return data.get("items", [])

    async def get_company_with_officers(self, company_number: str) -> Company:
        """Get company profile with all officers populated.

        Convenience method that fetches both in one call.
        """
        company = await self.get_company(company_number)
        officers = await self.get_company_officers(company_number)
        company.officers = officers
        return company

    async def get_disqualified_officer(self, officer_id: str) -> Optional[dict]:
        """Check if an officer is disqualified.

        Args:
            officer_id: The officer's unique ID

        Returns:
            Disqualification details if disqualified, None otherwise
        """
        try:
            data = await self.get(f"/disqualified-officers/natural/{officer_id}")
            return data
        except Exception:
            # Not disqualified or not found
            return None
