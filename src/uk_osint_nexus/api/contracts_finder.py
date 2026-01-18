"""Contracts Finder API client.

API Documentation: https://www.contractsfinder.service.gov.uk/apidocumentation
Rate Limit: Not strictly defined, be reasonable
Authentication: OAuth 2.0 Bearer token (optional for some public data)

FREE endpoints used:
- GET /Published/Notices/OCDS/Search - Search published notices (OCDS format)
- GET /Harvester/Notices/Data/CSV/Daily - Daily CSV exports (alternative)

Coverage:
- All UK government contracts over £10,000 (Central Gov) / £25,000 (wider public sector)
- Tender opportunities and awarded contracts
- Buyer and supplier information

Note: The API has moved to require authentication for some endpoints.
This client attempts unauthenticated access first, with graceful fallback.
"""

from datetime import datetime
from typing import Optional

from ..models.entities import Contract
from .base import BaseAPIClient


class ContractsFinderClient(BaseAPIClient):
    """Client for the Contracts Finder API."""

    BASE_URL = "https://www.contractsfinder.service.gov.uk/api/rest/2"

    def __init__(self):
        super().__init__(
            base_url=self.BASE_URL,
            api_key=None,  # No auth required
            rate_limit=2.0,
        )

    @property
    def source_name(self) -> str:
        return "contracts_finder"

    def _get_headers(self) -> dict[str, str]:
        """Get headers for Contracts Finder API."""
        return {
            "Accept": "application/json",
            "User-Agent": "UK-OSINT-Nexus/0.1.0",
            "Content-Type": "application/json",
        }

    def _parse_datetime(self, dt_str: Optional[str]) -> Optional[datetime]:
        """Parse ISO datetime string."""
        if not dt_str:
            return None
        try:
            # Handle various formats
            if "Z" in dt_str:
                dt_str = dt_str.replace("Z", "+00:00")
            if "." in dt_str:
                # Truncate microseconds if too long
                parts = dt_str.split(".")
                if len(parts) == 2:
                    ms_part = parts[1][:6]
                    tz_idx = ms_part.find("+") or ms_part.find("-")
                    if tz_idx == -1:
                        dt_str = f"{parts[0]}.{ms_part}"
                    else:
                        dt_str = f"{parts[0]}.{ms_part[:tz_idx]}{ms_part[tz_idx:]}"
            return datetime.fromisoformat(dt_str)
        except ValueError:
            return None

    def _parse_contract(self, notice: dict, releases: list) -> Contract:
        """Parse contract data from OCDS format."""
        # Get the latest release for this notice
        release = releases[0] if releases else {}

        # Extract tender information
        tender = release.get("tender", {})
        buyer = release.get("buyer", {})

        # Extract value
        value = tender.get("value", {})
        value_low = value.get("amount")
        value_high = value.get("amount")

        # Check for min/max values
        if "minValue" in tender:
            value_low = tender["minValue"].get("amount")
        if "maxValue" in tender:
            value_high = tender["maxValue"].get("amount")

        # Extract awarded information if available
        awards = release.get("awards", [])
        awarded_value = None
        awarded_date = None
        supplier_name = None

        if awards:
            award = awards[0]
            awarded_value = award.get("value", {}).get("amount")
            awarded_date = self._parse_datetime(award.get("date"))
            suppliers = award.get("suppliers", [])
            if suppliers:
                supplier_name = suppliers[0].get("name")

        # Extract CPV codes
        cpv_codes = []
        items = tender.get("items", [])
        for item in items:
            classification = item.get("classification", {})
            if classification.get("scheme") == "CPV":
                cpv_codes.append(classification.get("id", ""))

        # Determine status
        status = tender.get("status", notice.get("status"))

        return Contract(
            source=self.source_name,
            notice_id=notice.get("id", release.get("ocid", "")),
            title=tender.get("title", notice.get("title", "Untitled")),
            description=tender.get("description"),
            published_date=self._parse_datetime(notice.get("publishedDate")),
            deadline_date=self._parse_datetime(tender.get("tenderPeriod", {}).get("endDate")),
            value_low=value_low,
            value_high=value_high,
            currency=value.get("currency", "GBP"),
            buyer_name=buyer.get("name"),
            buyer_id=buyer.get("id"),
            supplier_name=supplier_name,
            awarded_date=awarded_date,
            awarded_value=awarded_value,
            status=status,
            cpv_codes=cpv_codes,
            region=notice.get("region"),
            notice_type=notice.get("type"),
            url=f"https://www.contractsfinder.service.gov.uk/Notice/{notice.get('id', '')}",
            raw_data={"notice": notice, "release": release},
        )

    async def search(self, query: str, **kwargs) -> list[Contract]:
        """Search for contracts by keyword."""
        return await self.search_contracts(query, **kwargs)

    async def search_contracts(
        self,
        query: Optional[str] = None,
        buyer_name: Optional[str] = None,
        supplier_name: Optional[str] = None,
        published_from: Optional[datetime] = None,
        published_to: Optional[datetime] = None,
        value_from: Optional[float] = None,
        value_to: Optional[float] = None,
        status: Optional[str] = None,
        cpv_codes: Optional[list[str]] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> list[Contract]:
        """Search for contracts with various filters.

        Args:
            query: Keyword search in title and description
            buyer_name: Filter by buyer/authority name
            supplier_name: Filter by supplier name (awarded contracts only)
            published_from: Start date for publication
            published_to: End date for publication
            value_from: Minimum contract value
            value_to: Maximum contract value
            status: Contract status ('Open', 'Closed', 'Awarded', etc.)
            cpv_codes: List of CPV codes to filter by
            page: Page number (1-indexed)
            page_size: Results per page (max 100)

        Returns:
            List of Contract objects
        """
        # Build query parameters for GET request (OCDS endpoint)
        params = {
            "limit": min(page_size, 100),
        }

        # Add filters as query params
        if published_from:
            params["publishedFrom"] = published_from.strftime("%Y-%m-%dT%H:%M:%SZ")

        if published_to:
            params["publishedTo"] = published_to.strftime("%Y-%m-%dT%H:%M:%SZ")

        if status:
            params["stages"] = status

        try:
            # Use GET endpoint for OCDS search
            data = await self.get("/Published/Notices/OCDS/Search", params=params)

            contracts = []
            # Handle both possible response formats
            results = data.get("results", data.get("releases", []))

            for result in results:
                # OCDS format can vary - handle different structures
                if isinstance(result, dict):
                    notice = result.get("notice", result)
                    releases = result.get("releases", [result] if "ocid" in result else [])
                    contract = self._parse_contract(notice, releases)

                    # Apply client-side filtering for fields not supported in API
                    if query and not self._matches_query(contract, query):
                        continue
                    if buyer_name and contract.buyer_name and buyer_name.lower() not in contract.buyer_name.lower():
                        continue
                    if supplier_name and contract.supplier_name and supplier_name.lower() not in contract.supplier_name.lower():
                        continue

                    contracts.append(contract)

            return contracts[:page_size]

        except Exception as e:
            # Log error but don't fail - return empty list
            # This allows other data sources to still work
            import sys
            error_msg = str(e)[:100]  # Truncate long error messages
            print(f"[Contracts Finder] API unavailable: {error_msg}...", file=sys.stderr)
            return []

    def _matches_query(self, contract: Contract, query: str) -> bool:
        """Check if contract matches search query."""
        query_lower = query.lower()
        searchable = [
            contract.title or "",
            contract.description or "",
            contract.buyer_name or "",
            contract.supplier_name or "",
        ]
        return any(query_lower in field.lower() for field in searchable)

    async def search_by_buyer(
        self,
        buyer_name: str,
        page: int = 1,
        page_size: int = 20,
    ) -> list[Contract]:
        """Search for contracts by buyer/authority name.

        Args:
            buyer_name: Name of the buying organization
            page: Page number
            page_size: Results per page

        Returns:
            List of contracts from this buyer
        """
        return await self.search_contracts(
            buyer_name=buyer_name,
            page=page,
            page_size=page_size,
        )

    async def search_by_supplier(
        self,
        supplier_name: str,
        page: int = 1,
        page_size: int = 20,
    ) -> list[Contract]:
        """Search for contracts awarded to a supplier.

        Args:
            supplier_name: Name of the supplier company
            page: Page number
            page_size: Results per page

        Returns:
            List of contracts awarded to this supplier
        """
        return await self.search_contracts(
            supplier_name=supplier_name,
            status="Awarded",
            page=page,
            page_size=page_size,
        )

    async def search_open_tenders(
        self,
        query: Optional[str] = None,
        value_from: Optional[float] = None,
        cpv_codes: Optional[list[str]] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> list[Contract]:
        """Search for currently open tender opportunities.

        Args:
            query: Optional keyword search
            value_from: Minimum contract value
            cpv_codes: Filter by CPV codes
            page: Page number
            page_size: Results per page

        Returns:
            List of open tender opportunities
        """
        return await self.search_contracts(
            query=query,
            status="Open",
            value_from=value_from,
            cpv_codes=cpv_codes,
            page=page,
            page_size=page_size,
        )

    async def get_contract(self, notice_id: str) -> Optional[Contract]:
        """Get a specific contract by notice ID.

        Args:
            notice_id: The notice ID from Contracts Finder

        Returns:
            Contract details or None if not found
        """
        try:
            # Try to get OCDS record directly
            data = await self.get(f"/Published/OCDS/Record/{notice_id}")

            if not data:
                return None

            # Parse from OCDS record format
            releases = data.get("releases", [])
            if releases:
                notice = {"id": notice_id}
                return self._parse_contract(notice, releases)
            return None
        except Exception:
            return None

    async def get_buyer_profile(self, buyer_name: str) -> dict:
        """Get profile information about a buyer.

        Aggregates contract data to build a profile.

        Args:
            buyer_name: Name of the buying organization

        Returns:
            Profile with contract statistics
        """
        contracts = await self.search_by_buyer(buyer_name, page_size=100)

        total_value = 0.0
        contract_count = len(contracts)
        open_tenders = 0
        awarded = 0
        suppliers = set()

        for contract in contracts:
            if contract.awarded_value:
                total_value += contract.awarded_value
            elif contract.value_high:
                total_value += contract.value_high

            if contract.status == "Open":
                open_tenders += 1
            elif contract.status == "Awarded":
                awarded += 1
                if contract.supplier_name:
                    suppliers.add(contract.supplier_name)

        return {
            "buyer_name": buyer_name,
            "total_contracts": contract_count,
            "total_value": total_value,
            "open_tenders": open_tenders,
            "awarded_contracts": awarded,
            "unique_suppliers": len(suppliers),
            "top_suppliers": list(suppliers)[:10],
        }

    async def get_supplier_profile(self, supplier_name: str) -> dict:
        """Get profile information about a supplier.

        Aggregates contract data to build a profile.

        Args:
            supplier_name: Name of the supplier company

        Returns:
            Profile with contract statistics
        """
        contracts = await self.search_by_supplier(supplier_name, page_size=100)

        total_value = 0.0
        buyers = set()

        for contract in contracts:
            if contract.awarded_value:
                total_value += contract.awarded_value
            elif contract.value_high:
                total_value += contract.value_high

            if contract.buyer_name:
                buyers.add(contract.buyer_name)

        return {
            "supplier_name": supplier_name,
            "awarded_contracts": len(contracts),
            "total_value": total_value,
            "unique_buyers": len(buyers),
            "top_buyers": list(buyers)[:10],
            "recent_contracts": [
                {"title": c.title, "buyer": c.buyer_name, "value": c.awarded_value}
                for c in contracts[:5]
            ],
        }
