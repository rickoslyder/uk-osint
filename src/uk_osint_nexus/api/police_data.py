"""UK Police Data API client.

API Documentation: https://data.police.uk/docs/
Rate Limit: Not strictly defined, large requests may return 503
Authentication: None required

FREE endpoints used:
- /api/crimes-street/{category} - Street level crimes
- /api/stops-street - Stop and search data
- /api/crime-categories - List of crime categories
- /api/forces - List of police forces

Coverage:
- All reported crimes in England, Wales, and Northern Ireland
- Street-level crime data (anonymised to nearest point)
- Stop and search records
- Monthly data updates

Note: Location data is anonymised to protect privacy.
"""

from datetime import date
from typing import Optional

from pydantic import BaseModel

from .base import BaseAPIClient


class Crime(BaseModel):
    """A recorded crime."""

    source: str = "police_data"
    crime_id: Optional[str] = None
    category: str
    location_type: Optional[str] = None
    location_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    street_name: Optional[str] = None
    month: str  # YYYY-MM format
    outcome_status: Optional[str] = None
    outcome_date: Optional[str] = None
    context: Optional[str] = None
    persistent_id: Optional[str] = None
    raw_data: Optional[dict] = None


class StopAndSearch(BaseModel):
    """A stop and search record."""

    source: str = "police_data"
    type: str  # 'Person search', 'Vehicle search', etc.
    datetime: Optional[str] = None
    outcome: Optional[str] = None
    outcome_linked_to_object: Optional[bool] = None
    involved_person: Optional[bool] = None

    # Location
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    street_name: Optional[str] = None

    # Subject details (anonymised)
    gender: Optional[str] = None
    age_range: Optional[str] = None
    self_defined_ethnicity: Optional[str] = None
    officer_defined_ethnicity: Optional[str] = None

    # Legal basis
    legislation: Optional[str] = None
    object_of_search: Optional[str] = None

    # Operation
    operation: Optional[bool] = None
    operation_name: Optional[str] = None

    raw_data: Optional[dict] = None


class PoliceDataClient(BaseAPIClient):
    """Client for the UK Police Data API."""

    BASE_URL = "https://data.police.uk/api"

    def __init__(self):
        super().__init__(
            base_url=self.BASE_URL,
            api_key=None,  # No authentication required
            rate_limit=1.0,  # Conservative rate limit
        )

    @property
    def source_name(self) -> str:
        return "police_data"

    def _parse_crime(self, data: dict) -> Crime:
        """Parse crime data from API response."""
        location = data.get("location", {})
        street = location.get("street", {})
        outcome = data.get("outcome_status") or {}

        return Crime(
            source=self.source_name,
            crime_id=data.get("id"),
            category=data.get("category", ""),
            location_type=data.get("location_type"),
            location_name=location.get("name"),
            latitude=float(location.get("latitude")) if location.get("latitude") else None,
            longitude=float(location.get("longitude")) if location.get("longitude") else None,
            street_name=street.get("name"),
            month=data.get("month", ""),
            outcome_status=outcome.get("category") if isinstance(outcome, dict) else None,
            outcome_date=outcome.get("date") if isinstance(outcome, dict) else None,
            context=data.get("context"),
            persistent_id=data.get("persistent_id"),
            raw_data=data,
        )

    def _parse_stop_search(self, data: dict) -> StopAndSearch:
        """Parse stop and search data from API response."""
        location = data.get("location") or {}
        street = location.get("street", {})

        return StopAndSearch(
            source=self.source_name,
            type=data.get("type", ""),
            datetime=data.get("datetime"),
            outcome=data.get("outcome"),
            outcome_linked_to_object=data.get("outcome_linked_to_object_of_search"),
            involved_person=data.get("involved_person"),
            latitude=float(location.get("latitude")) if location.get("latitude") else None,
            longitude=float(location.get("longitude")) if location.get("longitude") else None,
            street_name=street.get("name") if isinstance(street, dict) else None,
            gender=data.get("gender"),
            age_range=data.get("age_range"),
            self_defined_ethnicity=data.get("self_defined_ethnicity"),
            officer_defined_ethnicity=data.get("officer_defined_ethnicity"),
            legislation=data.get("legislation"),
            object_of_search=data.get("object_of_search"),
            operation=data.get("operation"),
            operation_name=data.get("operation_name"),
            raw_data=data,
        )

    async def search(self, query: str, **kwargs) -> list[Crime]:
        """Search by postcode - converts to lat/lng first."""
        # For the general search, we treat query as a postcode
        return await self.get_crimes_by_postcode(query, **kwargs)

    async def get_crimes_at_location(
        self,
        lat: float,
        lng: float,
        date: Optional[str] = None,  # YYYY-MM format
        category: str = "all-crime",
    ) -> list[Crime]:
        """Get crimes at a specific location.

        Args:
            lat: Latitude
            lng: Longitude
            date: Optional date in YYYY-MM format
            category: Crime category or 'all-crime'

        Returns:
            List of Crime objects
        """
        try:
            params = {"lat": lat, "lng": lng}
            if date:
                params["date"] = date

            data = await self.get(f"/crimes-street/{category}", params=params)

            crimes = []
            if isinstance(data, list):
                for item in data:
                    crimes.append(self._parse_crime(item))

            return crimes

        except Exception as e:
            import sys
            error_msg = str(e)[:100]
            print(f"[Police Data] API error: {error_msg}...", file=sys.stderr)
            return []

    async def get_crimes_by_postcode(
        self,
        postcode: str,
        date: Optional[str] = None,
        category: str = "all-crime",
    ) -> list[Crime]:
        """Get crimes near a postcode.

        Args:
            postcode: UK postcode
            date: Optional date in YYYY-MM format
            category: Crime category or 'all-crime'

        Returns:
            List of Crime objects
        """
        # First convert postcode to lat/lng using postcodes.io
        coords = await self._postcode_to_coords(postcode)
        if not coords:
            return []

        return await self.get_crimes_at_location(
            lat=coords["lat"],
            lng=coords["lng"],
            date=date,
            category=category,
        )

    async def _postcode_to_coords(self, postcode: str) -> Optional[dict]:
        """Convert UK postcode to coordinates using postcodes.io."""
        import httpx

        postcode = postcode.replace(" ", "").upper()
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://api.postcodes.io/postcodes/{postcode}"
                )
                if response.status_code == 200:
                    data = response.json()
                    result = data.get("result", {})
                    return {
                        "lat": result.get("latitude"),
                        "lng": result.get("longitude"),
                    }
        except Exception:
            pass
        return None

    async def get_stop_and_search(
        self,
        lat: float,
        lng: float,
        date: Optional[str] = None,
    ) -> list[StopAndSearch]:
        """Get stop and search data at a location.

        Args:
            lat: Latitude
            lng: Longitude
            date: Optional date in YYYY-MM format

        Returns:
            List of StopAndSearch objects
        """
        try:
            params = {"lat": lat, "lng": lng}
            if date:
                params["date"] = date

            data = await self.get("/stops-street", params=params)

            stops = []
            if isinstance(data, list):
                for item in data:
                    stops.append(self._parse_stop_search(item))

            return stops

        except Exception as e:
            import sys
            error_msg = str(e)[:100]
            print(f"[Police Data] API error: {error_msg}...", file=sys.stderr)
            return []

    async def get_stop_and_search_by_postcode(
        self,
        postcode: str,
        date: Optional[str] = None,
    ) -> list[StopAndSearch]:
        """Get stop and search data near a postcode.

        Args:
            postcode: UK postcode
            date: Optional date in YYYY-MM format

        Returns:
            List of StopAndSearch objects
        """
        coords = await self._postcode_to_coords(postcode)
        if not coords:
            return []

        return await self.get_stop_and_search(
            lat=coords["lat"],
            lng=coords["lng"],
            date=date,
        )

    async def get_crime_categories(self) -> list[dict]:
        """Get list of available crime categories.

        Returns:
            List of category dicts with 'url' and 'name' keys
        """
        try:
            data = await self.get("/crime-categories")
            return data if isinstance(data, list) else []
        except Exception:
            return []

    async def get_forces(self) -> list[dict]:
        """Get list of police forces.

        Returns:
            List of force dicts with 'id' and 'name' keys
        """
        try:
            data = await self.get("/forces")
            return data if isinstance(data, list) else []
        except Exception:
            return []

    async def get_crime_summary(
        self,
        postcode: str,
        months: int = 3,
    ) -> dict:
        """Get a summary of crimes near a postcode.

        Args:
            postcode: UK postcode
            months: Number of recent months to include

        Returns:
            Summary dict with crime counts by category
        """
        crimes = await self.get_crimes_by_postcode(postcode)

        # Group by category
        summary: dict[str, int] = {}
        for crime in crimes:
            cat = crime.category
            summary[cat] = summary.get(cat, 0) + 1

        return {
            "postcode": postcode,
            "total_crimes": len(crimes),
            "by_category": summary,
        }
