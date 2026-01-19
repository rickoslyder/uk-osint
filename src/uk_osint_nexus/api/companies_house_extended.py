"""Extended Companies House API features.

Additional endpoints for:
- Disqualified Directors
- Persons with Significant Control (PSC)
- Company Charges (Mortgages/Security)
- Register of Overseas Entities

Uses the same Companies House API but separates these specialized searches.
"""

from datetime import date
from typing import Optional

from pydantic import BaseModel

from .companies_house import CompaniesHouseClient


class DisqualifiedDirector(BaseModel):
    """A disqualified director record."""

    source: str = "companies_house"

    # Person details
    name: str
    forename: Optional[str] = None
    surname: Optional[str] = None
    date_of_birth: Optional[str] = None  # Month/Year only
    nationality: Optional[str] = None

    # Address
    address: Optional[dict] = None

    # Disqualification details
    disqualified_from: Optional[date] = None
    disqualified_until: Optional[date] = None

    # Reason
    reason: Optional[str] = None
    case_identifier: Optional[str] = None
    court: Optional[str] = None
    act: Optional[str] = None  # Companies Act section

    # Company involved
    company_names: list[str] = []

    # Exemptions
    has_exemption: bool = False
    exemption_details: Optional[str] = None

    raw_data: Optional[dict] = None


class PersonWithSignificantControl(BaseModel):
    """A Person with Significant Control (PSC) record."""

    source: str = "companies_house"

    # Company
    company_number: str
    company_name: Optional[str] = None

    # PSC details
    name: str
    name_elements: Optional[dict] = None  # title, forename, surname, etc.
    date_of_birth: Optional[dict] = None  # month/year
    nationality: Optional[str] = None
    country_of_residence: Optional[str] = None

    # Address
    address: Optional[dict] = None

    # Control nature
    natures_of_control: list[str] = []  # e.g., 'ownership-of-shares-75-to-100-percent'

    # Dates
    notified_on: Optional[date] = None
    ceased_on: Optional[date] = None

    # For corporate PSCs
    kind: str = "individual"  # 'individual', 'corporate-entity', 'legal-person'
    identification: Optional[dict] = None  # For corporate PSCs

    raw_data: Optional[dict] = None


class CompanyCharge(BaseModel):
    """A company charge (mortgage/security) record."""

    source: str = "companies_house"

    # Company
    company_number: str
    company_name: Optional[str] = None

    # Charge details
    charge_number: Optional[str] = None
    charge_code: Optional[str] = None
    classification: Optional[dict] = None

    # Status
    status: str  # 'outstanding', 'satisfied', 'part-satisfied'

    # Secured details
    secured_details: Optional[dict] = None
    particulars: Optional[str] = None
    assets_ceased_released: Optional[str] = None

    # Persons entitled
    persons_entitled: list[dict] = []

    # Dates
    created_on: Optional[date] = None
    delivered_on: Optional[date] = None
    satisfied_on: Optional[date] = None
    covering_instrument_date: Optional[date] = None

    # Scottish charges
    scottish_alterations: Optional[dict] = None

    raw_data: Optional[dict] = None


class OverseasEntity(BaseModel):
    """A registered overseas entity."""

    source: str = "companies_house"

    # Entity details
    entity_number: str  # OE number
    entity_name: str
    incorporation_country: Optional[str] = None
    legal_form: Optional[str] = None
    governing_law: Optional[str] = None

    # Principal address
    principal_address: Optional[dict] = None
    service_address: Optional[dict] = None

    # Beneficial owners
    beneficial_owners: list[dict] = []

    # Registration
    registered_on: Optional[date] = None
    registration_status: Optional[str] = None

    raw_data: Optional[dict] = None


class CompaniesHouseExtendedClient(CompaniesHouseClient):
    """Extended Companies House client with additional endpoints."""

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

    # Disqualified Directors

    async def search_disqualified_officers(
        self,
        query: str,
        items_per_page: int = 20,
        start_index: int = 0,
    ) -> list[DisqualifiedDirector]:
        """Search for disqualified directors.

        Args:
            query: Name to search for
            items_per_page: Number of results per page
            start_index: Starting offset

        Returns:
            List of DisqualifiedDirector objects
        """
        try:
            params = {
                "q": query,
                "items_per_page": items_per_page,
                "start_index": start_index,
            }

            data = await self.get("/search/disqualified-officers", params=params)
            items = data.get("items", [])

            directors = []
            for item in items:
                directors.append(self._parse_disqualified_director(item))

            return directors

        except Exception as e:
            import sys
            print(f"[Companies House] Disqualified search error: {str(e)[:100]}", file=sys.stderr)
            return []

    async def get_disqualified_officer(self, officer_id: str) -> Optional[DisqualifiedDirector]:
        """Get details of a specific disqualified officer.

        Args:
            officer_id: The officer ID from search results

        Returns:
            DisqualifiedDirector or None
        """
        try:
            data = await self.get(f"/disqualified-officers/natural/{officer_id}")
            return self._parse_disqualified_director(data)
        except Exception:
            return None

    def _parse_disqualified_director(self, data: dict) -> DisqualifiedDirector:
        """Parse disqualified director from API response."""
        disqualifications = data.get("disqualifications", [])
        first_disq = disqualifications[0] if disqualifications else {}

        company_names = []
        for disq in disqualifications:
            for company in disq.get("company_names", []):
                company_names.append(company)

        return DisqualifiedDirector(
            source="companies_house",
            name=data.get("title", "") or f"{data.get('forename', '')} {data.get('surname', '')}".strip(),
            forename=data.get("forename"),
            surname=data.get("surname"),
            date_of_birth=data.get("date_of_birth"),
            nationality=data.get("nationality"),
            address=data.get("address"),
            disqualified_from=self._parse_date(first_disq.get("disqualified_from")),
            disqualified_until=self._parse_date(first_disq.get("disqualified_until")),
            reason=first_disq.get("reason", {}).get("description_identifier"),
            case_identifier=first_disq.get("case_identifier"),
            court=first_disq.get("court_name"),
            act=first_disq.get("reason", {}).get("act"),
            company_names=company_names,
            has_exemption=len(data.get("exemptions", [])) > 0,
            exemption_details=str(data.get("exemptions")) if data.get("exemptions") else None,
            raw_data=data,
        )

    # Persons with Significant Control (PSC)

    async def get_company_pscs(
        self,
        company_number: str,
        items_per_page: int = 25,
        start_index: int = 0,
    ) -> list[PersonWithSignificantControl]:
        """Get PSCs for a company.

        Args:
            company_number: Company number
            items_per_page: Results per page
            start_index: Starting offset

        Returns:
            List of PSC records
        """
        try:
            params = {
                "items_per_page": items_per_page,
                "start_index": start_index,
            }

            data = await self.get(
                f"/company/{company_number}/persons-with-significant-control",
                params=params
            )

            pscs = []
            for item in data.get("items", []):
                pscs.append(self._parse_psc(item, company_number))

            return pscs

        except Exception as e:
            import sys
            print(f"[Companies House] PSC error: {str(e)[:100]}", file=sys.stderr)
            return []

    def _parse_psc(self, data: dict, company_number: str) -> PersonWithSignificantControl:
        """Parse PSC from API response."""
        return PersonWithSignificantControl(
            source="companies_house",
            company_number=company_number,
            name=data.get("name", ""),
            name_elements=data.get("name_elements"),
            date_of_birth=data.get("date_of_birth"),
            nationality=data.get("nationality"),
            country_of_residence=data.get("country_of_residence"),
            address=data.get("address"),
            natures_of_control=data.get("natures_of_control", []),
            notified_on=self._parse_date(data.get("notified_on")),
            ceased_on=self._parse_date(data.get("ceased_on")),
            kind=data.get("kind", "individual"),
            identification=data.get("identification"),
            raw_data=data,
        )

    # Company Charges

    async def get_company_charges(
        self,
        company_number: str,
        items_per_page: int = 25,
        start_index: int = 0,
    ) -> list[CompanyCharge]:
        """Get charges (mortgages/security) for a company.

        Args:
            company_number: Company number
            items_per_page: Results per page
            start_index: Starting offset

        Returns:
            List of CompanyCharge records
        """
        try:
            params = {
                "items_per_page": items_per_page,
                "start_index": start_index,
            }

            data = await self.get(f"/company/{company_number}/charges", params=params)

            charges = []
            for item in data.get("items", []):
                charges.append(self._parse_charge(item, company_number))

            return charges

        except Exception as e:
            import sys
            print(f"[Companies House] Charges error: {str(e)[:100]}", file=sys.stderr)
            return []

    def _parse_charge(self, data: dict, company_number: str) -> CompanyCharge:
        """Parse charge from API response."""
        return CompanyCharge(
            source="companies_house",
            company_number=company_number,
            charge_number=data.get("charge_number"),
            charge_code=data.get("charge_code"),
            classification=data.get("classification"),
            status=data.get("status", "unknown"),
            secured_details=data.get("secured_details"),
            particulars=data.get("particulars", {}).get("description"),
            assets_ceased_released=data.get("assets_ceased_released"),
            persons_entitled=data.get("persons_entitled", []),
            created_on=self._parse_date(data.get("created_on")),
            delivered_on=self._parse_date(data.get("delivered_on")),
            satisfied_on=self._parse_date(data.get("satisfied_on")),
            covering_instrument_date=self._parse_date(data.get("covering_instrument_date")),
            scottish_alterations=data.get("scottish_alterations"),
            raw_data=data,
        )

    # Overseas Entities

    async def get_overseas_entity(self, oe_number: str) -> Optional[OverseasEntity]:
        """Get an overseas entity by number.

        Args:
            oe_number: Overseas entity number (OE...)

        Returns:
            OverseasEntity or None
        """
        try:
            data = await self.get(f"/company/{oe_number}")

            if data.get("type") != "registered-overseas-entity":
                return None

            return OverseasEntity(
                source="companies_house",
                entity_number=oe_number,
                entity_name=data.get("company_name", ""),
                incorporation_country=data.get("foreign_company_details", {}).get("originating_registry", {}).get("country"),
                legal_form=data.get("foreign_company_details", {}).get("legal_form"),
                governing_law=data.get("foreign_company_details", {}).get("governed_by"),
                principal_address=data.get("registered_office_address"),
                service_address=data.get("service_address"),
                registered_on=self._parse_date(data.get("date_of_creation")),
                registration_status=data.get("company_status"),
                raw_data=data,
            )

        except Exception:
            return None

    async def search_overseas_entities(
        self,
        query: str,
        items_per_page: int = 20,
    ) -> list[OverseasEntity]:
        """Search for overseas entities.

        Args:
            query: Name to search for
            items_per_page: Results per page

        Returns:
            List of OverseasEntity records
        """
        # Use regular company search but filter by type
        try:
            from .companies_house import CompaniesHouseClient

            # Search companies and filter to overseas entities
            companies = await self.search_companies(query, items_per_page=items_per_page)

            entities = []
            for company in companies:
                if company.company_number.startswith("OE"):
                    entity = await self.get_overseas_entity(company.company_number)
                    if entity:
                        entities.append(entity)

            return entities

        except Exception as e:
            import sys
            print(f"[Companies House] Overseas entity error: {str(e)[:100]}", file=sys.stderr)
            return []
