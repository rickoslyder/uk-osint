"""HM Land Registry Price Paid Data API client.

API Documentation: https://landregistry.data.gov.uk/
Rate Limit: Not strictly defined
Authentication: None required

Endpoints used:
- SPARQL endpoint for price paid data
- Linked Data API

Coverage:
- All property sales in England and Wales since 1995
- Sale price, property type, new build status
- Address details

Note: This is public open data. Some address details may be
partially anonymised.
"""

from datetime import date
from typing import Optional

from pydantic import BaseModel

from .base import BaseAPIClient


class PropertyTransaction(BaseModel):
    """A property sale transaction."""

    source: str = "land_registry"

    # Transaction details
    transaction_id: Optional[str] = None
    price: int  # Sale price in GBP
    transaction_date: Optional[date] = None

    # Property type
    property_type: Optional[str] = None  # 'D'=Detached, 'S'=Semi, 'T'=Terrace, 'F'=Flat, 'O'=Other
    property_type_name: Optional[str] = None  # Human readable

    # Transaction category
    old_new: Optional[str] = None  # 'Y'=New build, 'N'=Established
    is_new_build: bool = False
    tenure: Optional[str] = None  # 'F'=Freehold, 'L'=Leasehold
    tenure_name: Optional[str] = None

    # Address
    primary_addressable_object: Optional[str] = None  # House name/number
    secondary_addressable_object: Optional[str] = None  # Flat number etc
    street: Optional[str] = None
    locality: Optional[str] = None
    town: Optional[str] = None
    district: Optional[str] = None
    county: Optional[str] = None
    postcode: Optional[str] = None

    # Full address
    full_address: Optional[str] = None

    # PPD Category
    ppd_category: Optional[str] = None  # 'A'=Standard, 'B'=Additional price

    raw_data: Optional[dict] = None


class LandRegistryClient(BaseAPIClient):
    """Client for HM Land Registry Price Paid Data."""

    BASE_URL = "https://landregistry.data.gov.uk"

    PROPERTY_TYPES = {
        "D": "Detached",
        "S": "Semi-detached",
        "T": "Terraced",
        "F": "Flat/Maisonette",
        "O": "Other",
    }

    TENURE_TYPES = {
        "F": "Freehold",
        "L": "Leasehold",
    }

    def __init__(self):
        super().__init__(
            base_url=self.BASE_URL,
            api_key=None,
            rate_limit=1.0,
        )

    @property
    def source_name(self) -> str:
        return "land_registry"

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

    def _parse_transaction(self, data: dict) -> PropertyTransaction:
        """Parse transaction from API response."""
        prop_type = data.get("propertyType", {}).get("value", "").split("/")[-1] if data.get("propertyType") else None
        tenure = data.get("estateType", {}).get("value", "").split("/")[-1] if data.get("estateType") else None

        # Build full address
        address_parts = [
            data.get("paon", {}).get("value"),
            data.get("saon", {}).get("value"),
            data.get("street", {}).get("value"),
            data.get("locality", {}).get("value"),
            data.get("town", {}).get("value"),
            data.get("district", {}).get("value"),
            data.get("county", {}).get("value"),
            data.get("postcode", {}).get("value"),
        ]
        full_address = ", ".join(p for p in address_parts if p)

        return PropertyTransaction(
            source=self.source_name,
            transaction_id=data.get("transactionId", {}).get("value"),
            price=int(data.get("pricePaid", {}).get("value", 0)),
            transaction_date=self._parse_date(data.get("transactionDate", {}).get("value")),
            property_type=prop_type,
            property_type_name=self.PROPERTY_TYPES.get(prop_type),
            old_new=data.get("newBuild", {}).get("value"),
            is_new_build=data.get("newBuild", {}).get("value") == "Y",
            tenure=tenure,
            tenure_name=self.TENURE_TYPES.get(tenure),
            primary_addressable_object=data.get("paon", {}).get("value"),
            secondary_addressable_object=data.get("saon", {}).get("value"),
            street=data.get("street", {}).get("value"),
            locality=data.get("locality", {}).get("value"),
            town=data.get("town", {}).get("value"),
            district=data.get("district", {}).get("value"),
            county=data.get("county", {}).get("value"),
            postcode=data.get("postcode", {}).get("value"),
            full_address=full_address,
            raw_data=data,
        )

    async def search(self, query: str, **kwargs) -> list[PropertyTransaction]:
        """Search by postcode."""
        return await self.search_by_postcode(query, **kwargs)

    async def search_by_postcode(
        self,
        postcode: str,
        limit: int = 50,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
    ) -> list[PropertyTransaction]:
        """Search property transactions by postcode.

        Args:
            postcode: UK postcode (e.g., 'SW1A 1AA')
            limit: Maximum results
            min_price: Minimum sale price filter
            max_price: Maximum sale price filter

        Returns:
            List of PropertyTransaction objects
        """
        try:
            # Normalize postcode
            postcode = postcode.upper().strip()

            # Build SPARQL query
            filters = [f'?postcode = "{postcode}"']
            if min_price:
                filters.append(f"?pricePaid >= {min_price}")
            if max_price:
                filters.append(f"?pricePaid <= {max_price}")

            filter_clause = " && ".join(filters)

            query = f"""
            PREFIX lrppi: <http://landregistry.data.gov.uk/def/ppi/>
            PREFIX lrcommon: <http://landregistry.data.gov.uk/def/common/>

            SELECT ?transactionId ?pricePaid ?transactionDate ?propertyType ?estateType
                   ?newBuild ?paon ?saon ?street ?locality ?town ?district ?county ?postcode
            WHERE {{
                ?transaction lrppi:pricePaid ?pricePaid ;
                             lrppi:transactionDate ?transactionDate ;
                             lrppi:propertyAddress ?address .

                ?address lrcommon:postcode ?postcode .

                OPTIONAL {{ ?transaction lrppi:transactionId ?transactionId }}
                OPTIONAL {{ ?transaction lrppi:propertyType ?propertyType }}
                OPTIONAL {{ ?transaction lrppi:estateType ?estateType }}
                OPTIONAL {{ ?transaction lrppi:newBuild ?newBuild }}
                OPTIONAL {{ ?address lrcommon:paon ?paon }}
                OPTIONAL {{ ?address lrcommon:saon ?saon }}
                OPTIONAL {{ ?address lrcommon:street ?street }}
                OPTIONAL {{ ?address lrcommon:locality ?locality }}
                OPTIONAL {{ ?address lrcommon:town ?town }}
                OPTIONAL {{ ?address lrcommon:district ?district }}
                OPTIONAL {{ ?address lrcommon:county ?county }}

                FILTER({filter_clause})
            }}
            ORDER BY DESC(?transactionDate)
            LIMIT {limit}
            """

            return await self._execute_sparql(query)

        except Exception as e:
            import sys
            print(f"[Land Registry] Search error: {str(e)[:100]}", file=sys.stderr)
            return []

    async def search_by_street(
        self,
        street: str,
        town: Optional[str] = None,
        limit: int = 50,
    ) -> list[PropertyTransaction]:
        """Search property transactions by street name.

        Args:
            street: Street name
            town: Optional town name to narrow results
            limit: Maximum results

        Returns:
            List of PropertyTransaction objects
        """
        try:
            street = street.upper().strip()

            filters = [f'CONTAINS(UCASE(?street), "{street}")']
            if town:
                filters.append(f'CONTAINS(UCASE(?town), "{town.upper()}")')

            filter_clause = " && ".join(filters)

            query = f"""
            PREFIX lrppi: <http://landregistry.data.gov.uk/def/ppi/>
            PREFIX lrcommon: <http://landregistry.data.gov.uk/def/common/>

            SELECT ?transactionId ?pricePaid ?transactionDate ?propertyType ?estateType
                   ?newBuild ?paon ?saon ?street ?locality ?town ?district ?county ?postcode
            WHERE {{
                ?transaction lrppi:pricePaid ?pricePaid ;
                             lrppi:transactionDate ?transactionDate ;
                             lrppi:propertyAddress ?address .

                ?address lrcommon:street ?street .
                OPTIONAL {{ ?address lrcommon:postcode ?postcode }}
                OPTIONAL {{ ?transaction lrppi:transactionId ?transactionId }}
                OPTIONAL {{ ?transaction lrppi:propertyType ?propertyType }}
                OPTIONAL {{ ?transaction lrppi:estateType ?estateType }}
                OPTIONAL {{ ?transaction lrppi:newBuild ?newBuild }}
                OPTIONAL {{ ?address lrcommon:paon ?paon }}
                OPTIONAL {{ ?address lrcommon:saon ?saon }}
                OPTIONAL {{ ?address lrcommon:locality ?locality }}
                OPTIONAL {{ ?address lrcommon:town ?town }}
                OPTIONAL {{ ?address lrcommon:district ?district }}
                OPTIONAL {{ ?address lrcommon:county ?county }}

                FILTER({filter_clause})
            }}
            ORDER BY DESC(?transactionDate)
            LIMIT {limit}
            """

            return await self._execute_sparql(query)

        except Exception as e:
            import sys
            print(f"[Land Registry] Street search error: {str(e)[:100]}", file=sys.stderr)
            return []

    async def _execute_sparql(self, query: str) -> list[PropertyTransaction]:
        """Execute SPARQL query and return parsed results."""
        import httpx

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.BASE_URL}/sparql",
                    params={"query": query, "output": "json"},
                    headers={"Accept": "application/sparql-results+json"},
                    timeout=30.0,
                )

                if response.status_code != 200:
                    return []

                data = response.json()
                results = data.get("results", {}).get("bindings", [])

                transactions = []
                for result in results:
                    transactions.append(self._parse_transaction(result))

                return transactions

        except Exception as e:
            import sys
            print(f"[Land Registry] SPARQL error: {str(e)[:100]}", file=sys.stderr)
            return []

    async def get_average_price(
        self,
        postcode: str,
        property_type: Optional[str] = None,
    ) -> dict:
        """Get average property price for a postcode.

        Args:
            postcode: UK postcode
            property_type: Optional filter (D, S, T, F, O)

        Returns:
            Dict with price statistics
        """
        transactions = await self.search_by_postcode(postcode, limit=100)

        if property_type:
            transactions = [t for t in transactions if t.property_type == property_type]

        if not transactions:
            return {
                "postcode": postcode,
                "count": 0,
                "average_price": None,
                "min_price": None,
                "max_price": None,
            }

        prices = [t.price for t in transactions]
        return {
            "postcode": postcode,
            "count": len(prices),
            "average_price": sum(prices) // len(prices),
            "min_price": min(prices),
            "max_price": max(prices),
            "most_recent": max(t.transaction_date for t in transactions if t.transaction_date),
        }
