"""Food Standards Agency (FSA) Food Hygiene Rating API client.

API Documentation: https://api.ratings.food.gov.uk/help
Rate Limit: Not defined, be reasonable
Authentication: None required

Endpoints used:
- /Establishments - Search food businesses
- /Authorities - Local authority info
- /Ratings - Rating definitions

Coverage:
- All food businesses in England, Wales, and Northern Ireland
- Hygiene ratings (0-5 for England/Wales/NI, Pass/Improvement Required for Scotland)
- Inspection dates and local authority details
"""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel

from .base import BaseAPIClient


class FoodEstablishment(BaseModel):
    """A food business establishment with hygiene rating."""

    source: str = "food_standards"

    # Business details
    fhrs_id: Optional[int] = None
    local_authority_business_id: Optional[str] = None
    business_name: str
    business_type: Optional[str] = None
    business_type_id: Optional[int] = None

    # Address
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    address_line_3: Optional[str] = None
    address_line_4: Optional[str] = None
    postcode: Optional[str] = None

    # Location
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Rating
    rating_value: Optional[str] = None  # '0'-'5' or 'Pass'/'Improvement Required'
    rating_key: Optional[str] = None  # 'fhrs_0_en-gb' etc.
    rating_date: Optional[date] = None
    new_rating_pending: bool = False

    # Scores (England, Wales, NI only)
    hygiene_score: Optional[int] = None  # 0, 5, 10, 15, 20, 25
    structural_score: Optional[int] = None
    confidence_in_management_score: Optional[int] = None

    # Local authority
    local_authority_code: Optional[int] = None
    local_authority_name: Optional[str] = None
    local_authority_email: Optional[str] = None

    # Scheme type
    scheme_type: Optional[str] = None  # 'FHRS' or 'FHIS'

    # Right to reply
    right_to_reply: Optional[str] = None

    raw_data: Optional[dict] = None


class FoodStandardsClient(BaseAPIClient):
    """Client for the Food Standards Agency Food Hygiene Rating API."""

    BASE_URL = "https://api.ratings.food.gov.uk"

    def __init__(self):
        super().__init__(
            base_url=self.BASE_URL,
            api_key=None,
            rate_limit=1.0,
        )

    @property
    def source_name(self) -> str:
        return "food_standards"

    def _get_headers(self) -> dict:
        """Override headers - FSA API requires specific headers."""
        return {
            "Accept": "application/json",
            "x-api-version": "2",
        }

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

    def _parse_establishment(self, data: dict) -> FoodEstablishment:
        """Parse establishment from API response."""
        scores = data.get("scores", {})

        return FoodEstablishment(
            source=self.source_name,
            fhrs_id=data.get("FHRSID"),
            local_authority_business_id=data.get("LocalAuthorityBusinessID"),
            business_name=data.get("BusinessName", ""),
            business_type=data.get("BusinessType"),
            business_type_id=data.get("BusinessTypeID"),
            address_line_1=data.get("AddressLine1"),
            address_line_2=data.get("AddressLine2"),
            address_line_3=data.get("AddressLine3"),
            address_line_4=data.get("AddressLine4"),
            postcode=data.get("PostCode"),
            latitude=float(data.get("geocode", {}).get("latitude")) if data.get("geocode", {}).get("latitude") else None,
            longitude=float(data.get("geocode", {}).get("longitude")) if data.get("geocode", {}).get("longitude") else None,
            rating_value=data.get("RatingValue"),
            rating_key=data.get("RatingKey"),
            rating_date=self._parse_date(data.get("RatingDate")),
            new_rating_pending=data.get("NewRatingPending", False),
            hygiene_score=scores.get("Hygiene"),
            structural_score=scores.get("Structural"),
            confidence_in_management_score=scores.get("ConfidenceInManagement"),
            local_authority_code=data.get("LocalAuthorityCode"),
            local_authority_name=data.get("LocalAuthorityName"),
            local_authority_email=data.get("LocalAuthorityEmailAddress"),
            scheme_type=data.get("SchemeType"),
            right_to_reply=data.get("RightToReply"),
            raw_data=data,
        )

    async def search(self, query: str, **kwargs) -> list[FoodEstablishment]:
        """Search establishments by name."""
        return await self.search_establishments(name=query, **kwargs)

    async def search_establishments(
        self,
        name: Optional[str] = None,
        address: Optional[str] = None,
        postcode: Optional[str] = None,
        business_type_id: Optional[int] = None,
        rating_value: Optional[str] = None,
        local_authority_id: Optional[int] = None,
        page_number: int = 1,
        page_size: int = 20,
    ) -> list[FoodEstablishment]:
        """Search food establishments.

        Args:
            name: Business name
            address: Address search
            postcode: Postcode
            business_type_id: Business type ID
            rating_value: Rating value filter
            local_authority_id: Local authority ID
            page_number: Page number
            page_size: Results per page

        Returns:
            List of FoodEstablishment objects
        """
        try:
            params = {
                "pageNumber": page_number,
                "pageSize": page_size,
            }

            if name:
                params["name"] = name
            if address:
                params["address"] = address
            if postcode:
                # Normalize postcode
                params["postcode"] = postcode.replace(" ", "").upper()
            if business_type_id:
                params["businessTypeId"] = business_type_id
            if rating_value:
                params["ratingValue"] = rating_value
            if local_authority_id:
                params["localAuthorityId"] = local_authority_id

            data = await self.get("/Establishments", params=params)

            establishments = []
            for item in data.get("establishments", []):
                establishments.append(self._parse_establishment(item))

            return establishments

        except Exception as e:
            import sys
            print(f"[Food Standards] Search error: {str(e)[:100]}", file=sys.stderr)
            return []

    async def get_establishment(self, fhrs_id: int) -> Optional[FoodEstablishment]:
        """Get a specific establishment by FHRS ID.

        Args:
            fhrs_id: The FHRS ID

        Returns:
            FoodEstablishment or None
        """
        try:
            data = await self.get(f"/Establishments/{fhrs_id}")
            return self._parse_establishment(data)
        except Exception:
            return None

    async def search_by_postcode(
        self,
        postcode: str,
        rating_filter: Optional[str] = None,
    ) -> list[FoodEstablishment]:
        """Search establishments by postcode.

        Args:
            postcode: UK postcode
            rating_filter: Optional rating filter (0-5)

        Returns:
            List of establishments
        """
        return await self.search_establishments(
            postcode=postcode,
            rating_value=rating_filter,
            page_size=50,
        )

    async def get_poor_ratings(
        self,
        postcode: Optional[str] = None,
        local_authority_id: Optional[int] = None,
    ) -> list[FoodEstablishment]:
        """Get establishments with poor hygiene ratings (0-2).

        Args:
            postcode: Optional postcode filter
            local_authority_id: Optional local authority filter

        Returns:
            List of establishments with ratings 0, 1, or 2
        """
        results = []

        for rating in ["0", "1", "2"]:
            establishments = await self.search_establishments(
                postcode=postcode,
                local_authority_id=local_authority_id,
                rating_value=rating,
                page_size=100,
            )
            results.extend(establishments)

        return results

    async def get_business_types(self) -> list[dict]:
        """Get list of business types.

        Returns:
            List of business type dicts with id and name
        """
        try:
            data = await self.get("/BusinessTypes")
            return data.get("businessTypes", [])
        except Exception:
            return []

    async def get_local_authorities(self) -> list[dict]:
        """Get list of local authorities.

        Returns:
            List of local authority dicts
        """
        try:
            data = await self.get("/Authorities")
            return data.get("authorities", [])
        except Exception:
            return []

    async def get_ratings_summary(
        self,
        postcode: Optional[str] = None,
    ) -> dict:
        """Get a summary of ratings for an area.

        Args:
            postcode: Optional postcode to analyze

        Returns:
            Dict with rating distribution
        """
        establishments = await self.search_establishments(
            postcode=postcode,
            page_size=100,
        )

        # Count by rating
        ratings: dict[str, int] = {}
        for est in establishments:
            rating = est.rating_value or "Unknown"
            ratings[rating] = ratings.get(rating, 0) + 1

        return {
            "postcode": postcode,
            "total_establishments": len(establishments),
            "rating_distribution": ratings,
            "average_rating": self._calculate_average_rating(establishments),
        }

    def _calculate_average_rating(self, establishments: list[FoodEstablishment]) -> Optional[float]:
        """Calculate average numeric rating."""
        numeric_ratings = []
        for est in establishments:
            try:
                if est.rating_value and est.rating_value.isdigit():
                    numeric_ratings.append(int(est.rating_value))
            except (ValueError, AttributeError):
                pass

        if not numeric_ratings:
            return None

        return sum(numeric_ratings) / len(numeric_ratings)
