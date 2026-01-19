"""Care Quality Commission (CQC) API client.

API Documentation: https://www.cqc.org.uk/about-us/transparency/using-cqc-data
Rate Limit: Not defined, be reasonable
Authentication: None required

Endpoints used:
- /locations - Search care locations
- /providers - Search care providers
- /reports - Inspection reports

Coverage:
- All registered health and social care providers in England
- Hospitals, care homes, GP surgeries, dental practices
- Inspection ratings (Outstanding, Good, Requires Improvement, Inadequate)
- Detailed inspection reports
"""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel

from .base import BaseAPIClient


class CQCLocation(BaseModel):
    """A CQC registered care location."""

    source: str = "cqc"

    # Location identification
    location_id: str
    name: str
    provider_id: Optional[str] = None
    provider_name: Optional[str] = None

    # Type
    location_type: Optional[str] = None  # 'Social Care Org', 'NHS Healthcare', etc.
    primary_inspection_category: Optional[str] = None
    specialisms: list[str] = []
    service_types: list[str] = []

    # Address
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    town: Optional[str] = None
    county: Optional[str] = None
    region: Optional[str] = None
    postcode: Optional[str] = None

    # Contact
    phone_number: Optional[str] = None
    website: Optional[str] = None

    # Location
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Registration
    registration_status: Optional[str] = None
    registration_date: Optional[date] = None
    deregistration_date: Optional[date] = None

    # Overall rating
    overall_rating: Optional[str] = None  # 'Outstanding', 'Good', 'Requires improvement', 'Inadequate'
    report_date: Optional[date] = None
    report_link: Optional[str] = None

    # Key question ratings
    safe_rating: Optional[str] = None
    effective_rating: Optional[str] = None
    caring_rating: Optional[str] = None
    responsive_rating: Optional[str] = None
    well_led_rating: Optional[str] = None

    # Capacity (for care homes)
    number_of_beds: Optional[int] = None

    raw_data: Optional[dict] = None


class CQCProvider(BaseModel):
    """A CQC registered care provider (organisation)."""

    source: str = "cqc"

    # Provider identification
    provider_id: str
    name: str
    organisation_type: Optional[str] = None

    # Contact
    main_phone_number: Optional[str] = None
    website: Optional[str] = None

    # Address
    postal_address_line_1: Optional[str] = None
    postal_address_line_2: Optional[str] = None
    postal_address_town: Optional[str] = None
    postal_address_county: Optional[str] = None
    postal_address_postcode: Optional[str] = None

    # Registration
    registration_status: Optional[str] = None
    registration_date: Optional[date] = None

    # Linked locations
    number_of_locations: int = 0

    raw_data: Optional[dict] = None


class CQCClient(BaseAPIClient):
    """Client for the Care Quality Commission API."""

    BASE_URL = "https://api.cqc.org.uk/public/v1"

    RATING_LEVELS = ["Outstanding", "Good", "Requires improvement", "Inadequate"]

    def __init__(self):
        super().__init__(
            base_url=self.BASE_URL,
            api_key=None,
            rate_limit=1.0,
        )

    @property
    def source_name(self) -> str:
        return "cqc"

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse date string."""
        if not date_str:
            return None
        try:
            if "T" in date_str:
                date_str = date_str.split("T")[0]
            return date.fromisoformat(date_str)
        except ValueError:
            return None

    def _parse_location(self, data: dict) -> CQCLocation:
        """Parse location from API response."""
        # Extract ratings
        current_ratings = data.get("currentRatings", {})
        overall = current_ratings.get("overall", {})

        # Key question ratings
        key_questions = {}
        for kq in current_ratings.get("keyQuestionRatings", []):
            name = kq.get("name", "").lower().replace(" ", "_")
            key_questions[name] = kq.get("rating")

        # Get inspection area ratings if no key questions
        if not key_questions and "inspectionAreas" in data:
            for area in data.get("inspectionAreas", []):
                for rating in area.get("ratings", []):
                    name = rating.get("questionKey", "").lower()
                    if name:
                        key_questions[name] = rating.get("rating")

        return CQCLocation(
            source=self.source_name,
            location_id=data.get("locationId", ""),
            name=data.get("name", ""),
            provider_id=data.get("providerId"),
            provider_name=data.get("providerName"),
            location_type=data.get("type"),
            primary_inspection_category=data.get("primaryInspectionCategoryName"),
            specialisms=data.get("specialisms", []),
            service_types=[s.get("name") for s in data.get("regulatedActivities", []) if s.get("name")],
            address_line_1=data.get("postalAddressLine1"),
            address_line_2=data.get("postalAddressLine2"),
            town=data.get("postalAddressTownCity"),
            county=data.get("postalAddressCounty"),
            region=data.get("region"),
            postcode=data.get("postalCode"),
            phone_number=data.get("mainPhoneNumber"),
            website=data.get("website"),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            registration_status=data.get("registrationStatus"),
            registration_date=self._parse_date(data.get("registrationDate")),
            deregistration_date=self._parse_date(data.get("deregistrationDate")),
            overall_rating=overall.get("rating"),
            report_date=self._parse_date(overall.get("reportDate")),
            report_link=overall.get("reportLinkId"),
            safe_rating=key_questions.get("safe"),
            effective_rating=key_questions.get("effective"),
            caring_rating=key_questions.get("caring"),
            responsive_rating=key_questions.get("responsive"),
            well_led_rating=key_questions.get("well_led") or key_questions.get("well-led"),
            number_of_beds=data.get("numberOfBeds"),
            raw_data=data,
        )

    def _parse_provider(self, data: dict) -> CQCProvider:
        """Parse provider from API response."""
        return CQCProvider(
            source=self.source_name,
            provider_id=data.get("providerId", ""),
            name=data.get("name", ""),
            organisation_type=data.get("organisationType"),
            main_phone_number=data.get("mainPhoneNumber"),
            website=data.get("website"),
            postal_address_line_1=data.get("postalAddressLine1"),
            postal_address_line_2=data.get("postalAddressLine2"),
            postal_address_town=data.get("postalAddressTownCity"),
            postal_address_county=data.get("postalAddressCounty"),
            postal_address_postcode=data.get("postalCode"),
            registration_status=data.get("registrationStatus"),
            registration_date=self._parse_date(data.get("registrationDate")),
            number_of_locations=data.get("locationIds", 0) if isinstance(data.get("locationIds"), int) else len(data.get("locationIds", [])),
            raw_data=data,
        )

    async def search(self, query: str, **kwargs) -> list[CQCLocation]:
        """Search locations by name."""
        return await self.search_locations(name=query, **kwargs)

    async def search_locations(
        self,
        name: Optional[str] = None,
        postcode: Optional[str] = None,
        overall_rating: Optional[str] = None,
        location_type: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> list[CQCLocation]:
        """Search CQC registered locations.

        Args:
            name: Location name
            postcode: Postcode to search
            overall_rating: Filter by rating
            location_type: Filter by type
            page: Page number
            per_page: Results per page

        Returns:
            List of CQCLocation objects
        """
        try:
            params = {
                "page": page,
                "perPage": per_page,
            }

            if name:
                params["partnerCode"] = "CQC"  # Required for name search
                params["q"] = name
            if postcode:
                params["postalCode"] = postcode.replace(" ", "").upper()
            if overall_rating:
                params["overallRating"] = overall_rating
            if location_type:
                params["locationType"] = location_type

            data = await self.get("/locations", params=params)

            locations = []
            for item in data.get("locations", []):
                # Get full location details
                location_detail = await self.get_location(item.get("locationId"))
                if location_detail:
                    locations.append(location_detail)
                else:
                    # Fallback to basic info
                    locations.append(self._parse_location(item))

            return locations

        except Exception as e:
            import sys
            print(f"[CQC] Location search error: {str(e)[:100]}", file=sys.stderr)
            return []

    async def get_location(self, location_id: str) -> Optional[CQCLocation]:
        """Get detailed information about a specific location.

        Args:
            location_id: The CQC location ID

        Returns:
            CQCLocation or None
        """
        try:
            data = await self.get(f"/locations/{location_id}")
            return self._parse_location(data)
        except Exception:
            return None

    async def search_providers(
        self,
        name: Optional[str] = None,
        postcode: Optional[str] = None,
        page: int = 1,
        per_page: int = 20,
    ) -> list[CQCProvider]:
        """Search CQC registered providers.

        Args:
            name: Provider name
            postcode: Postcode to search
            page: Page number
            per_page: Results per page

        Returns:
            List of CQCProvider objects
        """
        try:
            params = {
                "page": page,
                "perPage": per_page,
            }

            if name:
                params["q"] = name
            if postcode:
                params["postalCode"] = postcode.replace(" ", "").upper()

            data = await self.get("/providers", params=params)

            providers = []
            for item in data.get("providers", []):
                provider_detail = await self.get_provider(item.get("providerId"))
                if provider_detail:
                    providers.append(provider_detail)
                else:
                    providers.append(self._parse_provider(item))

            return providers

        except Exception as e:
            import sys
            print(f"[CQC] Provider search error: {str(e)[:100]}", file=sys.stderr)
            return []

    async def get_provider(self, provider_id: str) -> Optional[CQCProvider]:
        """Get detailed information about a specific provider.

        Args:
            provider_id: The CQC provider ID

        Returns:
            CQCProvider or None
        """
        try:
            data = await self.get(f"/providers/{provider_id}")
            return self._parse_provider(data)
        except Exception:
            return None

    async def get_provider_locations(
        self,
        provider_id: str,
    ) -> list[CQCLocation]:
        """Get all locations for a provider.

        Args:
            provider_id: The CQC provider ID

        Returns:
            List of CQCLocation objects
        """
        try:
            data = await self.get(f"/providers/{provider_id}")
            location_ids = data.get("locationIds", [])

            locations = []
            for loc_id in location_ids[:20]:  # Limit to 20 to avoid rate limiting
                location = await self.get_location(loc_id)
                if location:
                    locations.append(location)

            return locations

        except Exception as e:
            import sys
            print(f"[CQC] Provider locations error: {str(e)[:100]}", file=sys.stderr)
            return []

    async def search_care_homes(
        self,
        postcode: Optional[str] = None,
        min_rating: Optional[str] = None,
    ) -> list[CQCLocation]:
        """Search for care homes.

        Args:
            postcode: Optional postcode filter
            min_rating: Minimum acceptable rating

        Returns:
            List of care home locations
        """
        locations = await self.search_locations(
            postcode=postcode,
            location_type="Social Care Org",
            per_page=50,
        )

        # Filter by rating if specified
        if min_rating and min_rating in self.RATING_LEVELS:
            min_index = self.RATING_LEVELS.index(min_rating)
            locations = [
                loc for loc in locations
                if loc.overall_rating and self.RATING_LEVELS.index(loc.overall_rating) <= min_index
            ]

        return locations

    async def search_gp_surgeries(
        self,
        postcode: Optional[str] = None,
        name: Optional[str] = None,
    ) -> list[CQCLocation]:
        """Search for GP surgeries.

        Args:
            postcode: Optional postcode filter
            name: Optional name filter

        Returns:
            List of GP surgery locations
        """
        return await self.search_locations(
            name=name,
            postcode=postcode,
            location_type="Primary Medical Services",
            per_page=50,
        )

    async def get_inadequate_providers(
        self,
        postcode: Optional[str] = None,
        location_type: Optional[str] = None,
    ) -> list[CQCLocation]:
        """Get providers with Inadequate ratings.

        Args:
            postcode: Optional postcode filter
            location_type: Optional type filter

        Returns:
            List of inadequate-rated locations
        """
        return await self.search_locations(
            postcode=postcode,
            location_type=location_type,
            overall_rating="Inadequate",
            per_page=100,
        )

    async def get_rating_summary(
        self,
        postcode: str,
    ) -> dict:
        """Get a summary of CQC ratings for an area.

        Args:
            postcode: Postcode to analyze

        Returns:
            Dict with rating distribution
        """
        locations = await self.search_locations(
            postcode=postcode,
            per_page=100,
        )

        # Count by rating
        ratings: dict[str, int] = {}
        types: dict[str, int] = {}

        for loc in locations:
            rating = loc.overall_rating or "Not rated"
            ratings[rating] = ratings.get(rating, 0) + 1

            loc_type = loc.location_type or "Unknown"
            types[loc_type] = types.get(loc_type, 0) + 1

        return {
            "postcode": postcode,
            "total_locations": len(locations),
            "rating_distribution": ratings,
            "type_distribution": types,
        }
