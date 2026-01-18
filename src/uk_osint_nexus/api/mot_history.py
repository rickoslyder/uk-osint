"""MOT History API client.

API Documentation: https://dvsa.github.io/mot-history-api-documentation/
Rate Limit: Varies by plan (default reasonable limits)
Authentication: API key via x-api-key header

FREE endpoints used:
- /trade/vehicles/mot-tests - Get MOT history by registration

Note: This API requires registration at
https://www.smartsurvey.co.uk/s/MOT_History_TradeAPI_Access_and_Support/
"""

from datetime import date
from typing import Optional

from ..models.entities import Vehicle
from .base import BaseAPIClient


class MOTHistoryClient(BaseAPIClient):
    """Client for the DVSA MOT History API."""

    BASE_URL = "https://beta.check-mot.service.gov.uk"

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(
            base_url=self.BASE_URL,
            api_key=None,  # Don't use Basic auth
            rate_limit=1.0,  # Conservative rate limit
        )
        self._api_key = api_key

    def _get_headers(self) -> dict[str, str]:
        """Get headers with x-api-key authentication."""
        headers = {
            "Accept": "application/json",
            "User-Agent": "UK-OSINT-Nexus/0.1.0",
        }
        if self._api_key:
            headers["x-api-key"] = self._api_key
        return headers

    @property
    def source_name(self) -> str:
        return "mot_history"

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse date string to date object."""
        if not date_str:
            return None
        try:
            # MOT API uses various date formats
            if "." in date_str:
                # Format: 2024.01.15
                return date.fromisoformat(date_str.replace(".", "-"))
            elif "T" in date_str:
                # ISO format with time
                return date.fromisoformat(date_str.split("T")[0])
            else:
                return date.fromisoformat(date_str)
        except ValueError:
            return None

    def _parse_vehicle(self, data: dict) -> Vehicle:
        """Parse vehicle data from MOT API response."""
        # Extract MOT history
        mot_history = []
        for test in data.get("motTests", []):
            mot_record = {
                "test_date": test.get("completedDate"),
                "expiry_date": test.get("expiryDate"),
                "odometer_value": test.get("odometerValue"),
                "odometer_unit": test.get("odometerUnit"),
                "test_result": test.get("testResult"),
                "mot_test_number": test.get("motTestNumber"),
                "defects": [],
            }

            # Parse defects (renamed from 'rfrAndComments' in newer API versions)
            defects = test.get("defects", []) or test.get("rfrAndComments", [])
            for defect in defects:
                mot_record["defects"].append(
                    {
                        "type": defect.get("type"),
                        "text": defect.get("text"),
                        "dangerous": defect.get("dangerous", False),
                    }
                )

            mot_history.append(mot_record)

        # Determine current MOT status from most recent test
        mot_status = None
        mot_expiry = None
        if mot_history:
            latest = mot_history[0]
            mot_status = latest.get("test_result")
            mot_expiry = self._parse_date(latest.get("expiry_date"))

        return Vehicle(
            source=self.source_name,
            registration_number=data.get("registration", "").upper(),
            make=data.get("make"),
            model=data.get("model"),
            colour=data.get("primaryColour"),
            fuel_type=data.get("fuelType"),
            year_of_manufacture=int(data["manufactureYear"])
            if data.get("manufactureYear")
            else None,
            date_of_first_registration=self._parse_date(data.get("firstUsedDate")),
            mot_status=mot_status,
            mot_expiry_date=mot_expiry,
            mot_history=mot_history,
            raw_data=data,
        )

    async def search(self, query: str, **kwargs) -> list[Vehicle]:
        """Search by vehicle registration number."""
        return await self.get_vehicle_mot_history(query)

    async def get_vehicle_mot_history(self, registration: str) -> list[Vehicle]:
        """Get MOT history for a vehicle by registration number.

        Args:
            registration: UK vehicle registration number (e.g., 'AB12CDE')

        Returns:
            List containing the vehicle with MOT history (single item)
        """
        # Normalize registration - remove spaces, uppercase
        registration = registration.replace(" ", "").upper()

        try:
            data = await self.get(f"/trade/vehicles/mot-tests?registration={registration}")

            # API returns a list of vehicles (usually 1)
            vehicles = []
            if isinstance(data, list):
                for item in data:
                    vehicles.append(self._parse_vehicle(item))
            elif isinstance(data, dict):
                vehicles.append(self._parse_vehicle(data))

            return vehicles
        except Exception:
            # Return empty list if vehicle not found
            return []

    async def get_mot_history_by_vin(self, vin: str) -> list[Vehicle]:
        """Get MOT history by Vehicle Identification Number (VIN).

        Args:
            vin: 17-character Vehicle Identification Number

        Returns:
            List containing the vehicle with MOT history
        """
        # Normalize VIN - uppercase, no spaces
        vin = vin.replace(" ", "").upper()

        try:
            data = await self.get(f"/trade/vehicles/mot-tests?vin={vin}")

            vehicles = []
            if isinstance(data, list):
                for item in data:
                    vehicles.append(self._parse_vehicle(item))
            elif isinstance(data, dict):
                vehicles.append(self._parse_vehicle(data))

            return vehicles
        except Exception:
            return []

    async def check_mot_status(self, registration: str) -> dict:
        """Quick check of current MOT status for a vehicle.

        Args:
            registration: UK vehicle registration number

        Returns:
            Dict with status information
        """
        vehicles = await self.get_vehicle_mot_history(registration)

        if not vehicles:
            return {
                "registration": registration.upper(),
                "found": False,
                "mot_status": "unknown",
                "message": "Vehicle not found in MOT database",
            }

        vehicle = vehicles[0]
        return {
            "registration": vehicle.registration_number,
            "found": True,
            "make": vehicle.make,
            "model": vehicle.model,
            "mot_status": vehicle.mot_status,
            "mot_expiry_date": str(vehicle.mot_expiry_date) if vehicle.mot_expiry_date else None,
            "test_count": len(vehicle.mot_history),
        }
