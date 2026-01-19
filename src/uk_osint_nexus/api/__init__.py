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

# New API clients
from .insolvency_service import InsolvencyServiceClient, InsolvencyRecord
from .companies_house_extended import (
    CompaniesHouseExtendedClient,
    DisqualifiedDirector,
    PersonWithSignificantControl,
    CompanyCharge,
    OverseasEntity,
)
from .land_registry import LandRegistryClient, PropertyTransaction
from .uk_sanctions import UKSanctionsClient, SanctionedEntity
from .food_standards import FoodStandardsClient, FoodEstablishment
from .gazette import GazetteClient, GazetteNotice
from .cqc import CQCClient, CQCLocation, CQCProvider

__all__ = [
    "BaseAPIClient",
    # Existing
    "CompaniesHouseClient",
    "MOTHistoryClient",
    "ContractsFinderClient",
    # Added in previous session
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
    # New clients
    "InsolvencyServiceClient",
    "InsolvencyRecord",
    "CompaniesHouseExtendedClient",
    "DisqualifiedDirector",
    "PersonWithSignificantControl",
    "CompanyCharge",
    "OverseasEntity",
    "LandRegistryClient",
    "PropertyTransaction",
    "UKSanctionsClient",
    "SanctionedEntity",
    "FoodStandardsClient",
    "FoodEstablishment",
    "GazetteClient",
    "GazetteNotice",
    "CQCClient",
    "CQCLocation",
    "CQCProvider",
]
