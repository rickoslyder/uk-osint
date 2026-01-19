"""API clients for UK OSINT data sources."""

from .base import BaseAPIClient
from .companies_house import CompaniesHouseClient
from .mot_history import MOTHistoryClient
from .contracts_finder import ContractsFinderClient
from .charity_commission import CharityCommissionClient, Charity, Trustee
from .fca_register import FCARegisterClient, FCAFirm, FCAIndividual
from .dvla_vehicle import DVLAVehicleClient, DVLAVehicle
from .electoral_commission import ElectoralCommissionClient, PoliticalDonation
from .police_data import PoliceDataClient, Crime, StopAndSearch

__all__ = [
    "BaseAPIClient",
    # Existing
    "CompaniesHouseClient",
    "MOTHistoryClient",
    "ContractsFinderClient",
    # New
    "CharityCommissionClient",
    "Charity",
    "Trustee",
    "FCARegisterClient",
    "FCAFirm",
    "FCAIndividual",
    "DVLAVehicleClient",
    "DVLAVehicle",
    "ElectoralCommissionClient",
    "PoliticalDonation",
    "PoliceDataClient",
    "Crime",
    "StopAndSearch",
]
