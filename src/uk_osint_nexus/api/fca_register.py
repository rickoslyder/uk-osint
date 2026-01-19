"""FCA Financial Services Register API client.

API Documentation: https://register.fca.org.uk/s/resources
Rate Limit: 50 requests per 10 seconds
Authentication: API key via X-Auth-Key header + email via X-Auth-Email

FREE endpoints used:
- /Firm/{FRN} - Get firm details
- /Firm/{FRN}/Individuals - Get individuals at a firm
- /Firm/{FRN}/Permissions - Get regulated activities
- /Firm/{FRN}/DisciplinaryHistory - Get disciplinary actions
- Common search for firms, individuals, funds

Coverage:
- All FCA authorised/registered firms
- Approved persons and their functions
- Regulated activities and permissions
- Disciplinary history and sanctions
"""

from datetime import date
from typing import Optional

from pydantic import BaseModel

from .base import BaseAPIClient


class FCAIndividual(BaseModel):
    """An individual registered with the FCA."""

    source: str = "fca_register"
    individual_reference_number: str
    name: str
    status: Optional[str] = None
    firm_reference_number: Optional[str] = None
    firm_name: Optional[str] = None
    functions: list[str] = []
    raw_data: Optional[dict] = None


class FCAFirm(BaseModel):
    """A firm registered with the FCA."""

    source: str = "fca_register"
    firm_reference_number: str
    firm_name: str
    status: Optional[str] = None  # 'Authorised', 'Registered', 'No Longer Authorised'
    status_effective_date: Optional[date] = None

    # Contact details
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None

    # Business details
    firm_type: Optional[str] = None
    business_types: list[str] = []
    permissions: list[str] = []

    # Related entities
    individuals: list[FCAIndividual] = []
    appointed_representatives: list[str] = []

    # Disciplinary
    has_disciplinary_history: bool = False
    disciplinary_actions: list[dict] = []

    # Linked company (for correlation with Companies House)
    company_number: Optional[str] = None

    raw_data: Optional[dict] = None


class FCARegisterClient(BaseAPIClient):
    """Client for the FCA Financial Services Register API."""

    BASE_URL = "https://register.fca.org.uk/services/V0.1"

    def __init__(self, api_key: Optional[str] = None, email: Optional[str] = None):
        super().__init__(
            base_url=self.BASE_URL,
            api_key=api_key,
            rate_limit=5.0,  # 50 requests per 10 seconds = 5/sec
        )
        self.email = email

    @property
    def source_name(self) -> str:
        return "fca_register"

    def _get_headers(self) -> dict:
        """Override to use FCA-specific authentication headers."""
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["X-Auth-Key"] = self.api_key
        if self.email:
            headers["X-Auth-Email"] = self.email
        return headers

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse date string to date object."""
        if not date_str:
            return None
        try:
            if "T" in date_str:
                date_str = date_str.split("T")[0]
            return date.fromisoformat(date_str)
        except ValueError:
            return None

    def _parse_firm(self, data: dict) -> FCAFirm:
        """Parse firm data from API response."""
        # Build address from components
        address_parts = []
        for key in ["Address Line 1", "Address Line 2", "Address Line 3", "Address Line 4", "Town", "Postcode"]:
            if data.get(key):
                address_parts.append(data[key])
        address = ", ".join(address_parts) if address_parts else data.get("Address")

        return FCAFirm(
            source=self.source_name,
            firm_reference_number=str(data.get("FRN") or data.get("Firm Reference Number", "")),
            firm_name=data.get("Organisation Name") or data.get("Firm Name", ""),
            status=data.get("Status"),
            status_effective_date=self._parse_date(data.get("Status Effective Date")),
            address=address,
            phone=data.get("Phone"),
            email=data.get("Email Address"),
            website=data.get("Website Address"),
            firm_type=data.get("Firm Type"),
            company_number=data.get("Companies House Number"),
            raw_data=data,
        )

    def _parse_individual(self, data: dict) -> FCAIndividual:
        """Parse individual data from API response."""
        return FCAIndividual(
            source=self.source_name,
            individual_reference_number=str(data.get("IRN") or data.get("Individual Reference Number", "")),
            name=data.get("Name") or data.get("Full Name", ""),
            status=data.get("Status"),
            firm_reference_number=str(data.get("FRN", "")),
            firm_name=data.get("Firm Name"),
            raw_data=data,
        )

    async def search(self, query: str, **kwargs) -> list[FCAFirm]:
        """Search for firms by name."""
        return await self.search_firms(query, **kwargs)

    async def search_firms(self, query: str) -> list[FCAFirm]:
        """Search for firms by name.

        Args:
            query: Firm name to search for

        Returns:
            List of FCAFirm objects
        """
        try:
            data = await self.get(f"/Search?q={query}&type=firm")

            firms = []
            results = data if isinstance(data, list) else data.get("Data", [])
            for item in results:
                firms.append(self._parse_firm(item))

            return firms

        except Exception as e:
            import sys
            error_msg = str(e)[:100]
            print(f"[FCA Register] API error: {error_msg}...", file=sys.stderr)
            return []

    async def search_individuals(self, query: str) -> list[FCAIndividual]:
        """Search for individuals by name.

        Args:
            query: Individual name to search for

        Returns:
            List of FCAIndividual objects
        """
        try:
            data = await self.get(f"/Search?q={query}&type=individual")

            individuals = []
            results = data if isinstance(data, list) else data.get("Data", [])
            for item in results:
                individuals.append(self._parse_individual(item))

            return individuals

        except Exception as e:
            import sys
            error_msg = str(e)[:100]
            print(f"[FCA Register] API error: {error_msg}...", file=sys.stderr)
            return []

    async def get_firm(self, frn: str) -> Optional[FCAFirm]:
        """Get detailed firm information by FRN.

        Args:
            frn: Firm Reference Number

        Returns:
            FCAFirm details or None if not found
        """
        try:
            data = await self.get(f"/Firm/{frn}")

            if not data:
                return None

            # Handle nested response
            if "Data" in data:
                data = data["Data"][0] if isinstance(data["Data"], list) else data["Data"]

            return self._parse_firm(data)

        except Exception:
            return None

    async def get_firm_individuals(self, frn: str) -> list[FCAIndividual]:
        """Get individuals at a firm.

        Args:
            frn: Firm Reference Number

        Returns:
            List of FCAIndividual objects
        """
        try:
            data = await self.get(f"/Firm/{frn}/Individuals")

            individuals = []
            results = data if isinstance(data, list) else data.get("Data", [])
            for item in results:
                ind = self._parse_individual(item)
                ind.firm_reference_number = frn
                individuals.append(ind)

            return individuals

        except Exception:
            return []

    async def get_firm_permissions(self, frn: str) -> list[str]:
        """Get regulated permissions for a firm.

        Args:
            frn: Firm Reference Number

        Returns:
            List of permission strings
        """
        try:
            data = await self.get(f"/Firm/{frn}/Permissions")

            permissions = []
            results = data if isinstance(data, list) else data.get("Data", [])
            for item in results:
                if isinstance(item, dict):
                    perm = item.get("Permission") or item.get("Regulated Activity")
                    if perm:
                        permissions.append(perm)
                elif isinstance(item, str):
                    permissions.append(item)

            return permissions

        except Exception:
            return []

    async def get_firm_disciplinary_history(self, frn: str) -> list[dict]:
        """Get disciplinary history for a firm.

        Args:
            frn: Firm Reference Number

        Returns:
            List of disciplinary action records
        """
        try:
            data = await self.get(f"/Firm/{frn}/DisciplinaryHistory")

            if isinstance(data, list):
                return data
            return data.get("Data", [])

        except Exception:
            return []

    async def get_firm_full(self, frn: str) -> Optional[FCAFirm]:
        """Get complete firm information including individuals and permissions.

        Convenience method that fetches all related data.
        """
        firm = await self.get_firm(frn)
        if firm:
            firm.individuals = await self.get_firm_individuals(frn)
            firm.permissions = await self.get_firm_permissions(frn)
            disciplinary = await self.get_firm_disciplinary_history(frn)
            firm.disciplinary_actions = disciplinary
            firm.has_disciplinary_history = len(disciplinary) > 0

        return firm

    async def get_individual(self, irn: str) -> Optional[FCAIndividual]:
        """Get individual details by IRN.

        Args:
            irn: Individual Reference Number

        Returns:
            FCAIndividual or None
        """
        try:
            data = await self.get(f"/Individuals/{irn}")

            if not data:
                return None

            if "Data" in data:
                data = data["Data"][0] if isinstance(data["Data"], list) else data["Data"]

            return self._parse_individual(data)

        except Exception:
            return None
