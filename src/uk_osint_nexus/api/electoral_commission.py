"""Electoral Commission Political Finance API client.

Search Portal: https://search.electoralcommission.org.uk/
Rate Limit: Not defined, be reasonable
Authentication: None required for public data

Endpoints used (discovered from portal):
- /api/search/Donations - Search political donations
- /api/search/Loans - Search political loans

Coverage:
- All reportable donations to political parties (>£500)
- Loans to political parties
- Donor details (name, type, amount)
- Quarterly and weekly reporting periods

Note: The API endpoints are not officially documented but can be
discovered from the search portal's network requests.
"""

from datetime import date
from typing import Optional

from pydantic import BaseModel

from .base import BaseAPIClient


class PoliticalDonation(BaseModel):
    """A political donation record."""

    source: str = "electoral_commission"
    ec_reference: Optional[str] = None  # Electoral Commission reference

    # Recipient
    recipient_name: str
    recipient_type: Optional[str] = None  # 'Political Party', 'Regulated Donee', etc.
    recipient_regulated_entity_type: Optional[str] = None

    # Donor
    donor_name: str
    donor_status: Optional[str] = None  # 'Individual', 'Company', 'Trade Union', etc.
    donor_company_registration: Optional[str] = None  # Companies House number if company

    # Donation details
    amount: float
    donation_type: Optional[str] = None  # 'Cash', 'Non Cash', 'Visit'
    nature_of_donation: Optional[str] = None
    purpose_of_visit: Optional[str] = None

    # Dates
    received_date: Optional[date] = None
    accepted_date: Optional[date] = None
    reported_date: Optional[date] = None
    reporting_period: Optional[str] = None

    # Electoral register
    electoral_register: Optional[str] = None  # 'Great Britain', 'Northern Ireland'
    is_aggregated: bool = False
    is_sponsorship: bool = False

    raw_data: Optional[dict] = None


class PoliticalParty(BaseModel):
    """A registered political party."""

    source: str = "electoral_commission"
    party_name: str
    party_id: Optional[str] = None
    registration_date: Optional[date] = None
    address: Optional[str] = None
    treasurer: Optional[str] = None
    status: Optional[str] = None  # 'Registered', 'Deregistered'
    total_donations: float = 0
    raw_data: Optional[dict] = None


class ElectoralCommissionClient(BaseAPIClient):
    """Client for the Electoral Commission Political Finance data."""

    BASE_URL = "https://search.electoralcommission.org.uk"

    def __init__(self):
        super().__init__(
            base_url=self.BASE_URL,
            api_key=None,
            rate_limit=1.0,  # Conservative rate limit
        )

    @property
    def source_name(self) -> str:
        return "electoral_commission"

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse date string to date object."""
        if not date_str:
            return None
        try:
            # Handle various date formats
            if "T" in date_str:
                date_str = date_str.split("T")[0]
            # Handle dd/mm/yyyy format
            if "/" in date_str:
                parts = date_str.split("/")
                if len(parts) == 3:
                    return date(int(parts[2]), int(parts[1]), int(parts[0]))
            return date.fromisoformat(date_str)
        except (ValueError, IndexError):
            return None

    def _parse_donation(self, data: dict) -> PoliticalDonation:
        """Parse donation data from API response."""
        return PoliticalDonation(
            source=self.source_name,
            ec_reference=data.get("ECRef") or data.get("ecReference"),
            recipient_name=data.get("RegulatedEntityName") or data.get("regulatedEntityName", ""),
            recipient_type=data.get("RegulatedEntityType") or data.get("regulatedEntityType"),
            donor_name=data.get("DonorName") or data.get("donorName", ""),
            donor_status=data.get("DonorStatus") or data.get("donorStatus"),
            donor_company_registration=data.get("CompanyRegistrationNumber"),
            amount=float(data.get("Value") or data.get("value", 0)),
            donation_type=data.get("DonationType") or data.get("donationType"),
            nature_of_donation=data.get("NatureOfDonation") or data.get("natureOfDonation"),
            received_date=self._parse_date(data.get("ReceivedDate") or data.get("receivedDate")),
            accepted_date=self._parse_date(data.get("AcceptedDate") or data.get("acceptedDate")),
            reported_date=self._parse_date(data.get("ReportedDate") or data.get("reportedDate")),
            reporting_period=data.get("ReportingPeriodName") or data.get("reportingPeriodName"),
            electoral_register=data.get("RegisterName") or data.get("registerName"),
            is_aggregated=data.get("IsAggregation", False),
            is_sponsorship=data.get("IsSponsorship", False),
            raw_data=data,
        )

    async def search(self, query: str, **kwargs) -> list[PoliticalDonation]:
        """Search for donations by donor or recipient name."""
        return await self.search_donations(query, **kwargs)

    async def search_donations(
        self,
        query: str,
        start: int = 0,
        rows: int = 50,
        sort: str = "AcceptedDate",
        order: str = "desc",
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> list[PoliticalDonation]:
        """Search for political donations.

        Args:
            query: Search term (donor name, recipient name, etc.)
            start: Starting offset for pagination
            rows: Number of results to return
            sort: Sort field ('AcceptedDate', 'Value')
            order: Sort order ('asc', 'desc')
            from_date: Filter donations from this date
            to_date: Filter donations up to this date

        Returns:
            List of PoliticalDonation objects
        """
        try:
            # Build query parameters
            params = {
                "query": query,
                "start": start,
                "rows": rows,
                "sort": sort,
                "order": order,
                # Include all entity types
                "et": ["pp", "ppm", "tp", "perpar", "rd"],
                # Include all registers
                "register": ["gb", "ni"],
                "prePoll": "false",
                "postPoll": "true",
            }

            if from_date:
                params["from"] = from_date.isoformat()
            if to_date:
                params["to"] = to_date.isoformat()

            # Try the JSON API endpoint
            data = await self.get("/api/search/Donations", params=params)

            donations = []
            # Handle different response structures
            if isinstance(data, dict):
                results = data.get("Result") or data.get("results") or data.get("data", [])
                if isinstance(results, list):
                    for item in results:
                        donations.append(self._parse_donation(item))
            elif isinstance(data, list):
                for item in data:
                    donations.append(self._parse_donation(item))

            return donations

        except Exception as e:
            import sys
            error_msg = str(e)[:100]
            print(f"[Electoral Commission] API error: {error_msg}...", file=sys.stderr)
            return []

    async def get_donations_by_donor(
        self,
        donor_name: str,
        limit: int = 100,
    ) -> list[PoliticalDonation]:
        """Get all donations from a specific donor.

        Args:
            donor_name: Name of the donor
            limit: Maximum results to return

        Returns:
            List of donations from this donor
        """
        return await self.search_donations(donor_name, rows=limit)

    async def get_donations_to_party(
        self,
        party_name: str,
        limit: int = 100,
    ) -> list[PoliticalDonation]:
        """Get all donations to a specific party.

        Args:
            party_name: Name of the political party
            limit: Maximum results to return

        Returns:
            List of donations to this party
        """
        donations = await self.search_donations(party_name, rows=limit)
        # Filter to only those where the party is the recipient
        return [d for d in donations if party_name.lower() in d.recipient_name.lower()]

    async def get_donations_by_company(
        self,
        company_name: str,
        company_number: Optional[str] = None,
    ) -> list[PoliticalDonation]:
        """Get donations from a company, useful for correlation with Companies House.

        Args:
            company_name: Name of the company
            company_number: Optional Companies House number for exact match

        Returns:
            List of donations from this company
        """
        donations = await self.search_donations(company_name)

        if company_number:
            # Filter by company registration number
            return [
                d for d in donations
                if d.donor_company_registration == company_number
            ]

        return [d for d in donations if d.donor_status in ("Company", "Limited Liability Partnership")]

    async def get_top_donors(
        self,
        party_name: Optional[str] = None,
        limit: int = 20,
    ) -> list[dict]:
        """Get top donors by total amount.

        Args:
            party_name: Optional party name to filter by
            limit: Number of top donors to return

        Returns:
            List of dicts with donor name and total amount
        """
        query = party_name or "*"
        donations = await self.search_donations(query, rows=500, sort="Value", order="desc")

        # Aggregate by donor
        donor_totals: dict[str, float] = {}
        for d in donations:
            if d.donor_name:
                donor_totals[d.donor_name] = donor_totals.get(d.donor_name, 0) + d.amount

        # Sort by total
        sorted_donors = sorted(donor_totals.items(), key=lambda x: x[1], reverse=True)

        return [
            {"donor_name": name, "total_amount": amount}
            for name, amount in sorted_donors[:limit]
        ]
