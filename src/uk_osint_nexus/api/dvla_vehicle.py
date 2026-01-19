"""DVLA Vehicle Enquiry Service (VES) API client.

API Documentation: https://developer-portal.driver-vehicle-licensing.api.gov.uk/
Rate Limit: Based on subscription plan
Authentication: API key via x-api-key header

FREE endpoints used:
- POST /vehicle-enquiry/v1/vehicles - Get vehicle details by registration

Coverage:
- All UK registered vehicles
- Tax status and due dates
- MOT status and expiry (basic)
- Vehicle specifications (make, colour, fuel, emissions)

Note: This complements the MOT History API by providing
tax status and additional vehicle specifications.
"""

from datetime import date
from typing import Optional

from pydantic import BaseModel

from .base import BaseAPIClient


class DVLAVehicle(BaseModel):
    """Vehicle details from DVLA."""

    source: str = "dvla_vehicle"
    registration_number: str
    make: Optional[str] = None
    colour: Optional[str] = None
    fuel_type: Optional[str] = None

    # Tax details
    tax_status: Optional[str] = None  # 'Taxed', 'SORN', 'Untaxed'
    tax_due_date: Optional[date] = None

    # MOT status (basic - use MOT History API for full details)
    mot_status: Optional[str] = None  # 'Valid', 'Not valid'
    mot_expiry_date: Optional[date] = None

    # Specifications
    year_of_manufacture: Optional[int] = None
    engine_capacity: Optional[int] = None  # cc
    co2_emissions: Optional[int] = None  # g/km

    # Vehicle type
    vehicle_type: Optional[str] = None  # 'Car', 'Motorcycle', 'Van', etc.
    wheelplan: Optional[str] = None

    # Dates
    date_of_first_registration: Optional[date] = None
    month_of_first_registration: Optional[str] = None

    # Type approval
    type_approval: Optional[str] = None

    # Revenue weight for goods vehicles
    revenue_weight: Optional[int] = None

    # Marker for exported/scrapped vehicles
    marked_for_export: bool = False

    raw_data: Optional[dict] = None


class DVLAVehicleClient(BaseAPIClient):
    """Client for the DVLA Vehicle Enquiry Service API."""

    BASE_URL = "https://driver-vehicle-licensing.api.gov.uk/vehicle-enquiry/v1"

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(
            base_url=self.BASE_URL,
            api_key=None,  # Don't use Basic auth
            rate_limit=2.0,  # Conservative rate limit
        )
        self._api_key = api_key

    @property
    def source_name(self) -> str:
        return "dvla_vehicle"

    def _get_headers(self) -> dict:
        """Override to use x-api-key header."""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self._api_key:
            headers["x-api-key"] = self._api_key
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

    def _parse_vehicle(self, data: dict) -> DVLAVehicle:
        """Parse vehicle data from DVLA API response."""
        return DVLAVehicle(
            source=self.source_name,
            registration_number=data.get("registrationNumber", "").upper(),
            make=data.get("make"),
            colour=data.get("colour"),
            fuel_type=data.get("fuelType"),
            tax_status=data.get("taxStatus"),
            tax_due_date=self._parse_date(data.get("taxDueDate")),
            mot_status=data.get("motStatus"),
            mot_expiry_date=self._parse_date(data.get("motExpiryDate")),
            year_of_manufacture=data.get("yearOfManufacture"),
            engine_capacity=data.get("engineCapacity"),
            co2_emissions=data.get("co2Emissions"),
            vehicle_type=data.get("typeApproval"),  # Maps to vehicle category
            wheelplan=data.get("wheelplan"),
            date_of_first_registration=self._parse_date(data.get("dateOfLastV5CIssued")),
            month_of_first_registration=data.get("monthOfFirstRegistration"),
            type_approval=data.get("typeApproval"),
            revenue_weight=data.get("revenueWeight"),
            marked_for_export=data.get("markedForExport", False),
            raw_data=data,
        )

    async def search(self, query: str, **kwargs) -> list[DVLAVehicle]:
        """Search by vehicle registration number."""
        vehicle = await self.get_vehicle(query)
        return [vehicle] if vehicle else []

    async def get_vehicle(self, registration: str) -> Optional[DVLAVehicle]:
        """Get vehicle details by registration number.

        Args:
            registration: UK vehicle registration number (e.g., 'AB12CDE')

        Returns:
            DVLAVehicle with details or None if not found
        """
        # Normalize registration - remove spaces, uppercase
        registration = registration.replace(" ", "").upper()

        try:
            # DVLA VES uses POST with JSON body
            data = await self.post(
                "/vehicles",
                json_data={"registrationNumber": registration}
            )

            if not data:
                return None

            return self._parse_vehicle(data)

        except Exception as e:
            import sys
            error_msg = str(e)[:100]
            print(f"[DVLA Vehicle] API error: {error_msg}...", file=sys.stderr)
            return None

    async def check_tax_status(self, registration: str) -> dict:
        """Quick check of current tax status for a vehicle.

        Args:
            registration: UK vehicle registration number

        Returns:
            Dict with tax status information
        """
        vehicle = await self.get_vehicle(registration)

        if not vehicle:
            return {
                "registration": registration.upper(),
                "found": False,
                "tax_status": "unknown",
                "message": "Vehicle not found",
            }

        return {
            "registration": vehicle.registration_number,
            "found": True,
            "make": vehicle.make,
            "colour": vehicle.colour,
            "tax_status": vehicle.tax_status,
            "tax_due_date": str(vehicle.tax_due_date) if vehicle.tax_due_date else None,
            "mot_status": vehicle.mot_status,
            "mot_expiry_date": str(vehicle.mot_expiry_date) if vehicle.mot_expiry_date else None,
        }

    async def is_taxed(self, registration: str) -> bool:
        """Check if a vehicle is currently taxed.

        Args:
            registration: UK vehicle registration number

        Returns:
            True if taxed, False otherwise
        """
        vehicle = await self.get_vehicle(registration)
        return vehicle.tax_status == "Taxed" if vehicle else False

    async def is_mot_valid(self, registration: str) -> bool:
        """Check if a vehicle has a valid MOT.

        Args:
            registration: UK vehicle registration number

        Returns:
            True if MOT is valid, False otherwise
        """
        vehicle = await self.get_vehicle(registration)
        return vehicle.mot_status == "Valid" if vehicle else False
