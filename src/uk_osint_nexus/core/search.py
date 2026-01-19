"""Unified search interface across all data sources."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Flag, auto
from typing import Any, Optional

from ..api.companies_house import CompaniesHouseClient
from ..api.contracts_finder import ContractsFinderClient
from ..api.mot_history import MOTHistoryClient
from ..api.charity_commission import CharityCommissionClient, Charity
from ..api.fca_register import FCARegisterClient, FCAFirm
from ..api.dvla_vehicle import DVLAVehicleClient
from ..api.electoral_commission import ElectoralCommissionClient, PoliticalDonation
from ..api.police_data import PoliceDataClient, Crime

# New API clients
from ..api.insolvency_service import InsolvencyServiceClient, InsolvencyRecord
from ..api.companies_house_extended import (
    CompaniesHouseExtendedClient,
    DisqualifiedDirector,
    PersonWithSignificantControl,
)
from ..api.land_registry import LandRegistryClient, PropertyTransaction
from ..api.uk_sanctions import UKSanctionsClient, SanctionedEntity
from ..api.food_standards import FoodStandardsClient, FoodEstablishment
from ..api.gazette import GazetteClient, GazetteNotice
from ..api.cqc import CQCClient, CQCLocation

from ..models.entities import (
    Company,
    Contract,
    EntityType,
    LegalCase,
    Officer,
    SearchResult,
    Vehicle,
)
from ..scrapers.bailii import BAILIIScraper
from ..utils.config import get_config


class DataSources(Flag):
    """Flags for selecting which data sources to search."""

    NONE = 0
    COMPANIES_HOUSE = auto()
    MOT_HISTORY = auto()
    BAILII = auto()
    CONTRACTS_FINDER = auto()
    CHARITY_COMMISSION = auto()
    FCA_REGISTER = auto()
    DVLA_VEHICLE = auto()
    ELECTORAL_COMMISSION = auto()
    POLICE_DATA = auto()

    # New data sources
    INSOLVENCY_SERVICE = auto()
    DISQUALIFIED_DIRECTORS = auto()
    PSC_REGISTER = auto()
    LAND_REGISTRY = auto()
    UK_SANCTIONS = auto()
    FOOD_STANDARDS = auto()
    GAZETTE = auto()
    CQC = auto()

    # Convenience combinations - original
    ALL_ORIGINAL = (COMPANIES_HOUSE | MOT_HISTORY | BAILII | CONTRACTS_FINDER |
                    CHARITY_COMMISSION | FCA_REGISTER | DVLA_VEHICLE | ELECTORAL_COMMISSION)
    ALL_WITH_POLICE = ALL_ORIGINAL | POLICE_DATA

    # Convenience combinations - with new sources
    ALL = (COMPANIES_HOUSE | MOT_HISTORY | BAILII | CONTRACTS_FINDER |
           CHARITY_COMMISSION | FCA_REGISTER | DVLA_VEHICLE | ELECTORAL_COMMISSION |
           INSOLVENCY_SERVICE | LAND_REGISTRY | UK_SANCTIONS | FOOD_STANDARDS |
           GAZETTE | CQC)

    ALL_EXTENDED = ALL | POLICE_DATA | DISQUALIFIED_DIRECTORS | PSC_REGISTER

    # Domain-specific combinations
    BUSINESS = COMPANIES_HOUSE | CONTRACTS_FINDER | CHARITY_COMMISSION | FCA_REGISTER
    BUSINESS_EXTENDED = BUSINESS | DISQUALIFIED_DIRECTORS | PSC_REGISTER | GAZETTE
    FINANCIAL = FCA_REGISTER | COMPANIES_HOUSE | UK_SANCTIONS
    LEGAL = BAILII | GAZETTE | INSOLVENCY_SERVICE
    VEHICLES = MOT_HISTORY | DVLA_VEHICLE
    POLITICAL = ELECTORAL_COMMISSION
    PROPERTY = LAND_REGISTRY
    HEALTHCARE = CQC | FOOD_STANDARDS
    REGULATORY = UK_SANCTIONS | INSOLVENCY_SERVICE | DISQUALIFIED_DIRECTORS

    # Person-focused searches
    PERSON_DUE_DILIGENCE = (COMPANIES_HOUSE | INSOLVENCY_SERVICE | DISQUALIFIED_DIRECTORS |
                            UK_SANCTIONS | GAZETTE | BAILII)


@dataclass
class SearchOptions:
    """Options for unified search."""

    sources: DataSources = DataSources.ALL
    max_results_per_source: int = 20
    include_officers: bool = True  # Include officer search for person queries
    timeout: float = 30.0


@dataclass
class UnifiedSearchResult:
    """Results from a unified search across all sources."""

    query: str
    timestamp: datetime = field(default_factory=datetime.utcnow)

    # Original data types
    companies: list[Company] = field(default_factory=list)
    officers: list[Officer] = field(default_factory=list)
    vehicles: list[Vehicle] = field(default_factory=list)
    legal_cases: list[LegalCase] = field(default_factory=list)
    contracts: list[Contract] = field(default_factory=list)

    # Added in previous session
    charities: list[Any] = field(default_factory=list)  # Charity objects
    fca_firms: list[Any] = field(default_factory=list)  # FCAFirm objects
    fca_individuals: list[Any] = field(default_factory=list)  # FCAIndividual objects
    donations: list[Any] = field(default_factory=list)  # PoliticalDonation objects
    crimes: list[Any] = field(default_factory=list)  # Crime objects

    # New data types
    insolvency_records: list[Any] = field(default_factory=list)  # InsolvencyRecord objects
    disqualified_directors: list[Any] = field(default_factory=list)  # DisqualifiedDirector objects
    psc_records: list[Any] = field(default_factory=list)  # PersonWithSignificantControl objects
    property_transactions: list[Any] = field(default_factory=list)  # PropertyTransaction objects
    sanctioned_entities: list[Any] = field(default_factory=list)  # SanctionedEntity objects
    food_establishments: list[Any] = field(default_factory=list)  # FoodEstablishment objects
    gazette_notices: list[Any] = field(default_factory=list)  # GazetteNotice objects
    cqc_locations: list[Any] = field(default_factory=list)  # CQCLocation objects

    errors: dict[str, str] = field(default_factory=dict)

    @property
    def total_results(self) -> int:
        """Total number of results across all sources."""
        return (
            len(self.companies)
            + len(self.officers)
            + len(self.vehicles)
            + len(self.legal_cases)
            + len(self.contracts)
            + len(self.charities)
            + len(self.fca_firms)
            + len(self.fca_individuals)
            + len(self.donations)
            + len(self.crimes)
            + len(self.insolvency_records)
            + len(self.disqualified_directors)
            + len(self.psc_records)
            + len(self.property_transactions)
            + len(self.sanctioned_entities)
            + len(self.food_establishments)
            + len(self.gazette_notices)
            + len(self.cqc_locations)
        )

    @property
    def has_results(self) -> bool:
        """Check if any results were found."""
        return self.total_results > 0

    def to_search_results(self) -> list[SearchResult]:
        """Convert to list of SearchResult objects for correlation."""
        results = []

        for company in self.companies:
            results.append(
                SearchResult(
                    entity_type=EntityType.COMPANY,
                    source=company.source,
                    entity=company,
                    matched_query=self.query,
                )
            )

        for officer in self.officers:
            results.append(
                SearchResult(
                    entity_type=EntityType.PERSON,
                    source=officer.source,
                    entity=officer,
                    matched_query=self.query,
                )
            )

        for vehicle in self.vehicles:
            results.append(
                SearchResult(
                    entity_type=EntityType.VEHICLE,
                    source=vehicle.source,
                    entity=vehicle,
                    matched_query=self.query,
                )
            )

        for case in self.legal_cases:
            results.append(
                SearchResult(
                    entity_type=EntityType.LEGAL_CASE,
                    source=case.source,
                    entity=case,
                    matched_query=self.query,
                )
            )

        for contract in self.contracts:
            results.append(
                SearchResult(
                    entity_type=EntityType.CONTRACT,
                    source=contract.source,
                    entity=contract,
                    matched_query=self.query,
                )
            )

        return results


class UnifiedSearch:
    """Unified search across all UK OSINT data sources."""

    def __init__(
        self,
        companies_house_key: Optional[str] = None,
        mot_history_key: Optional[str] = None,
        charity_commission_key: Optional[str] = None,
        fca_key: Optional[str] = None,
        fca_email: Optional[str] = None,
        dvla_key: Optional[str] = None,
    ):
        """Initialize unified search.

        Args:
            companies_house_key: Optional API key for Companies House
            mot_history_key: Optional API key for MOT History
            charity_commission_key: Optional API key for Charity Commission
            fca_key: Optional API key for FCA Register
            fca_email: Optional email for FCA Register
            dvla_key: Optional API key for DVLA Vehicle Enquiry
        """
        config = get_config()

        self._ch_key = companies_house_key or config.companies_house_api_key
        self._mot_key = mot_history_key or config.mot_history_api_key
        self._charity_key = charity_commission_key or getattr(config, 'charity_commission_api_key', None)
        self._fca_key = fca_key or getattr(config, 'fca_api_key', None)
        self._fca_email = fca_email or getattr(config, 'fca_email', None)
        self._dvla_key = dvla_key or getattr(config, 'dvla_api_key', None)

        # Lazy initialization of clients
        self._companies_house: Optional[CompaniesHouseClient] = None
        self._mot_history: Optional[MOTHistoryClient] = None
        self._bailii: Optional[BAILIIScraper] = None
        self._contracts_finder: Optional[ContractsFinderClient] = None
        self._charity_commission: Optional[CharityCommissionClient] = None
        self._fca_register: Optional[FCARegisterClient] = None
        self._dvla_vehicle: Optional[DVLAVehicleClient] = None
        self._electoral_commission: Optional[ElectoralCommissionClient] = None
        self._police_data: Optional[PoliceDataClient] = None

        # New clients
        self._insolvency_service: Optional[InsolvencyServiceClient] = None
        self._companies_house_extended: Optional[CompaniesHouseExtendedClient] = None
        self._land_registry: Optional[LandRegistryClient] = None
        self._uk_sanctions: Optional[UKSanctionsClient] = None
        self._food_standards: Optional[FoodStandardsClient] = None
        self._gazette: Optional[GazetteClient] = None
        self._cqc: Optional[CQCClient] = None

    # Original client getters

    def _get_companies_house(self) -> CompaniesHouseClient:
        """Get or create Companies House client."""
        if self._companies_house is None:
            self._companies_house = CompaniesHouseClient(api_key=self._ch_key)
        return self._companies_house

    def _get_mot_history(self) -> MOTHistoryClient:
        """Get or create MOT History client."""
        if self._mot_history is None:
            self._mot_history = MOTHistoryClient(api_key=self._mot_key)
        return self._mot_history

    def _get_bailii(self) -> BAILIIScraper:
        """Get or create BAILII scraper."""
        if self._bailii is None:
            self._bailii = BAILIIScraper()
        return self._bailii

    def _get_contracts_finder(self) -> ContractsFinderClient:
        """Get or create Contracts Finder client."""
        if self._contracts_finder is None:
            self._contracts_finder = ContractsFinderClient()
        return self._contracts_finder

    def _get_charity_commission(self) -> CharityCommissionClient:
        """Get or create Charity Commission client."""
        if self._charity_commission is None:
            self._charity_commission = CharityCommissionClient(api_key=self._charity_key)
        return self._charity_commission

    def _get_fca_register(self) -> FCARegisterClient:
        """Get or create FCA Register client."""
        if self._fca_register is None:
            self._fca_register = FCARegisterClient(api_key=self._fca_key, email=self._fca_email)
        return self._fca_register

    def _get_dvla_vehicle(self) -> DVLAVehicleClient:
        """Get or create DVLA Vehicle client."""
        if self._dvla_vehicle is None:
            self._dvla_vehicle = DVLAVehicleClient(api_key=self._dvla_key)
        return self._dvla_vehicle

    def _get_electoral_commission(self) -> ElectoralCommissionClient:
        """Get or create Electoral Commission client."""
        if self._electoral_commission is None:
            self._electoral_commission = ElectoralCommissionClient()
        return self._electoral_commission

    def _get_police_data(self) -> PoliceDataClient:
        """Get or create Police Data client."""
        if self._police_data is None:
            self._police_data = PoliceDataClient()
        return self._police_data

    # New client getters

    def _get_insolvency_service(self) -> InsolvencyServiceClient:
        """Get or create Insolvency Service client."""
        if self._insolvency_service is None:
            self._insolvency_service = InsolvencyServiceClient()
        return self._insolvency_service

    def _get_companies_house_extended(self) -> CompaniesHouseExtendedClient:
        """Get or create Companies House Extended client."""
        if self._companies_house_extended is None:
            self._companies_house_extended = CompaniesHouseExtendedClient(api_key=self._ch_key)
        return self._companies_house_extended

    def _get_land_registry(self) -> LandRegistryClient:
        """Get or create Land Registry client."""
        if self._land_registry is None:
            self._land_registry = LandRegistryClient()
        return self._land_registry

    def _get_uk_sanctions(self) -> UKSanctionsClient:
        """Get or create UK Sanctions client."""
        if self._uk_sanctions is None:
            self._uk_sanctions = UKSanctionsClient()
        return self._uk_sanctions

    def _get_food_standards(self) -> FoodStandardsClient:
        """Get or create Food Standards client."""
        if self._food_standards is None:
            self._food_standards = FoodStandardsClient()
        return self._food_standards

    def _get_gazette(self) -> GazetteClient:
        """Get or create Gazette client."""
        if self._gazette is None:
            self._gazette = GazetteClient()
        return self._gazette

    def _get_cqc(self) -> CQCClient:
        """Get or create CQC client."""
        if self._cqc is None:
            self._cqc = CQCClient()
        return self._cqc

    async def close(self) -> None:
        """Close all clients."""
        clients = [
            self._companies_house,
            self._mot_history,
            self._bailii,
            self._contracts_finder,
            self._charity_commission,
            self._fca_register,
            self._dvla_vehicle,
            self._electoral_commission,
            self._police_data,
            # New clients
            self._insolvency_service,
            self._companies_house_extended,
            self._land_registry,
            self._uk_sanctions,
            self._food_standards,
            self._gazette,
            self._cqc,
        ]
        for client in clients:
            if client:
                await client.close()

    async def search(
        self,
        query: str,
        options: Optional[SearchOptions] = None,
    ) -> UnifiedSearchResult:
        """Search across all enabled data sources.

        Args:
            query: Search query (name, company, registration number, etc.)
            options: Search options

        Returns:
            UnifiedSearchResult with results from all sources
        """
        if options is None:
            options = SearchOptions()

        result = UnifiedSearchResult(query=query)

        # Build list of search tasks based on enabled sources
        tasks = []
        task_names = []

        # Original sources
        if DataSources.COMPANIES_HOUSE in options.sources:
            tasks.append(self._search_companies_house(query, options))
            task_names.append("companies_house")

        if DataSources.MOT_HISTORY in options.sources:
            tasks.append(self._search_mot_history(query, options))
            task_names.append("mot_history")

        if DataSources.BAILII in options.sources:
            tasks.append(self._search_bailii(query, options))
            task_names.append("bailii")

        if DataSources.CONTRACTS_FINDER in options.sources:
            tasks.append(self._search_contracts_finder(query, options))
            task_names.append("contracts_finder")

        if DataSources.CHARITY_COMMISSION in options.sources:
            tasks.append(self._search_charity_commission(query, options))
            task_names.append("charity_commission")

        if DataSources.FCA_REGISTER in options.sources:
            tasks.append(self._search_fca_register(query, options))
            task_names.append("fca_register")

        if DataSources.DVLA_VEHICLE in options.sources:
            tasks.append(self._search_dvla_vehicle(query, options))
            task_names.append("dvla_vehicle")

        if DataSources.ELECTORAL_COMMISSION in options.sources:
            tasks.append(self._search_electoral_commission(query, options))
            task_names.append("electoral_commission")

        if DataSources.POLICE_DATA in options.sources:
            tasks.append(self._search_police_data(query, options))
            task_names.append("police_data")

        # New sources
        if DataSources.INSOLVENCY_SERVICE in options.sources:
            tasks.append(self._search_insolvency_service(query, options))
            task_names.append("insolvency_service")

        if DataSources.DISQUALIFIED_DIRECTORS in options.sources:
            tasks.append(self._search_disqualified_directors(query, options))
            task_names.append("disqualified_directors")

        if DataSources.PSC_REGISTER in options.sources:
            # PSC search requires a company number, skip for general name queries
            pass

        if DataSources.LAND_REGISTRY in options.sources:
            tasks.append(self._search_land_registry(query, options))
            task_names.append("land_registry")

        if DataSources.UK_SANCTIONS in options.sources:
            tasks.append(self._search_uk_sanctions(query, options))
            task_names.append("uk_sanctions")

        if DataSources.FOOD_STANDARDS in options.sources:
            tasks.append(self._search_food_standards(query, options))
            task_names.append("food_standards")

        if DataSources.GAZETTE in options.sources:
            tasks.append(self._search_gazette(query, options))
            task_names.append("gazette")

        if DataSources.CQC in options.sources:
            tasks.append(self._search_cqc(query, options))
            task_names.append("cqc")

        # Execute all searches in parallel
        if tasks:
            try:
                results = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=options.timeout,
                )

                # Process results
                for name, res in zip(task_names, results):
                    if isinstance(res, Exception):
                        result.errors[name] = str(res)
                    elif isinstance(res, dict):
                        # Original types
                        if "companies" in res:
                            result.companies.extend(res["companies"])
                        if "officers" in res:
                            result.officers.extend(res["officers"])
                        if "vehicles" in res:
                            result.vehicles.extend(res["vehicles"])
                        if "legal_cases" in res:
                            result.legal_cases.extend(res["legal_cases"])
                        if "contracts" in res:
                            result.contracts.extend(res["contracts"])
                        if "charities" in res:
                            result.charities.extend(res["charities"])
                        if "fca_firms" in res:
                            result.fca_firms.extend(res["fca_firms"])
                        if "fca_individuals" in res:
                            result.fca_individuals.extend(res["fca_individuals"])
                        if "donations" in res:
                            result.donations.extend(res["donations"])
                        if "crimes" in res:
                            result.crimes.extend(res["crimes"])
                        # New types
                        if "insolvency_records" in res:
                            result.insolvency_records.extend(res["insolvency_records"])
                        if "disqualified_directors" in res:
                            result.disqualified_directors.extend(res["disqualified_directors"])
                        if "psc_records" in res:
                            result.psc_records.extend(res["psc_records"])
                        if "property_transactions" in res:
                            result.property_transactions.extend(res["property_transactions"])
                        if "sanctioned_entities" in res:
                            result.sanctioned_entities.extend(res["sanctioned_entities"])
                        if "food_establishments" in res:
                            result.food_establishments.extend(res["food_establishments"])
                        if "gazette_notices" in res:
                            result.gazette_notices.extend(res["gazette_notices"])
                        if "cqc_locations" in res:
                            result.cqc_locations.extend(res["cqc_locations"])

            except asyncio.TimeoutError:
                result.errors["timeout"] = f"Search timed out after {options.timeout}s"

        return result

    # Original search methods

    async def _search_companies_house(
        self,
        query: str,
        options: SearchOptions,
    ) -> dict:
        """Search Companies House for companies and officers."""
        client = self._get_companies_house()
        results = {"companies": [], "officers": []}

        # Search for companies
        try:
            companies = await client.search_companies(
                query,
                items_per_page=options.max_results_per_source,
            )
            results["companies"] = companies
        except Exception as e:
            results["company_error"] = str(e)

        # Also search for officers if enabled
        if options.include_officers:
            try:
                officers = await client.search_officers(
                    query,
                    items_per_page=options.max_results_per_source,
                )
                results["officers"] = officers
            except Exception as e:
                results["officer_error"] = str(e)

        return results

    async def _search_mot_history(
        self,
        query: str,
        options: SearchOptions,
    ) -> dict:
        """Search MOT History for vehicles."""
        # Only search if query looks like a registration number
        # UK registrations are typically 2-8 characters, alphanumeric
        clean_query = query.replace(" ", "").upper()

        if not (2 <= len(clean_query) <= 8 and clean_query.isalnum()):
            return {"vehicles": []}

        client = self._get_mot_history()
        results = {"vehicles": []}

        try:
            vehicles = await client.get_vehicle_mot_history(clean_query)
            results["vehicles"] = vehicles
        except Exception as e:
            results["error"] = str(e)

        return results

    async def _search_bailii(
        self,
        query: str,
        options: SearchOptions,
    ) -> dict:
        """Search BAILII for legal cases."""
        scraper = self._get_bailii()
        results = {"legal_cases": []}

        try:
            cases = await scraper.search(
                query,
                max_results=options.max_results_per_source,
            )
            results["legal_cases"] = cases
        except Exception as e:
            results["error"] = str(e)

        return results

    async def _search_contracts_finder(
        self,
        query: str,
        options: SearchOptions,
    ) -> dict:
        """Search Contracts Finder for government contracts."""
        client = self._get_contracts_finder()
        results = {"contracts": []}

        try:
            contracts = await client.search_contracts(
                query=query,
                page_size=options.max_results_per_source,
            )
            results["contracts"] = contracts
        except Exception as e:
            results["error"] = str(e)

        return results

    async def _search_charity_commission(
        self,
        query: str,
        options: SearchOptions,
    ) -> dict:
        """Search Charity Commission for charities."""
        client = self._get_charity_commission()
        results = {"charities": []}

        try:
            charities = await client.search_charities(
                query,
                limit=options.max_results_per_source,
            )
            results["charities"] = charities
        except Exception as e:
            results["error"] = str(e)

        return results

    async def _search_fca_register(
        self,
        query: str,
        options: SearchOptions,
    ) -> dict:
        """Search FCA Register for firms and individuals."""
        client = self._get_fca_register()
        results = {"fca_firms": [], "fca_individuals": []}

        try:
            firms = await client.search_firms(
                query,
                limit=options.max_results_per_source,
            )
            results["fca_firms"] = firms
        except Exception as e:
            results["firm_error"] = str(e)

        # Also search for individuals if enabled
        if options.include_officers:
            try:
                individuals = await client.search_individuals(
                    query,
                    limit=options.max_results_per_source,
                )
                results["fca_individuals"] = individuals
            except Exception as e:
                results["individual_error"] = str(e)

        return results

    async def _search_dvla_vehicle(
        self,
        query: str,
        options: SearchOptions,
    ) -> dict:
        """Search DVLA for vehicle details."""
        # Only search if query looks like a registration number
        clean_query = query.replace(" ", "").upper()

        if not (2 <= len(clean_query) <= 8 and clean_query.isalnum()):
            return {"vehicles": []}

        client = self._get_dvla_vehicle()
        results = {"vehicles": []}

        try:
            vehicles = await client.search(clean_query)
            results["vehicles"] = vehicles
        except Exception as e:
            results["error"] = str(e)

        return results

    async def _search_electoral_commission(
        self,
        query: str,
        options: SearchOptions,
    ) -> dict:
        """Search Electoral Commission for political donations."""
        client = self._get_electoral_commission()
        results = {"donations": []}

        try:
            donations = await client.search_donations(
                query,
                rows=options.max_results_per_source,
            )
            results["donations"] = donations
        except Exception as e:
            results["error"] = str(e)

        return results

    async def _search_police_data(
        self,
        query: str,
        options: SearchOptions,
    ) -> dict:
        """Search Police Data for crimes by postcode."""
        # Only search if query looks like a UK postcode
        clean_query = query.replace(" ", "").upper()

        # Basic postcode validation - 5-8 chars, alphanumeric
        if not (5 <= len(clean_query) <= 8 and clean_query.isalnum()):
            return {"crimes": []}

        client = self._get_police_data()
        results = {"crimes": []}

        try:
            crimes = await client.get_crimes_by_postcode(query)
            results["crimes"] = crimes
        except Exception as e:
            results["error"] = str(e)

        return results

    # New search methods

    async def _search_insolvency_service(
        self,
        query: str,
        options: SearchOptions,
    ) -> dict:
        """Search Insolvency Service for bankruptcies and IVAs."""
        client = self._get_insolvency_service()
        results = {"insolvency_records": []}

        try:
            # Parse query to try to extract surname and forenames
            parts = query.strip().split()
            if len(parts) >= 2:
                # Assume last part is surname
                surname = parts[-1]
                forenames = " ".join(parts[:-1])
                records = await client.search_by_name(surname, forenames)
            else:
                # Single word - use as surname
                records = await client.search_by_name(query)
            results["insolvency_records"] = records
        except Exception as e:
            results["error"] = str(e)

        return results

    async def _search_disqualified_directors(
        self,
        query: str,
        options: SearchOptions,
    ) -> dict:
        """Search for disqualified directors."""
        client = self._get_companies_house_extended()
        results = {"disqualified_directors": []}

        try:
            directors = await client.search_disqualified_officers(
                query,
                items_per_page=options.max_results_per_source,
            )
            results["disqualified_directors"] = directors
        except Exception as e:
            results["error"] = str(e)

        return results

    async def _search_land_registry(
        self,
        query: str,
        options: SearchOptions,
    ) -> dict:
        """Search Land Registry for property transactions."""
        # Only search if query looks like a UK postcode
        clean_query = query.replace(" ", "").upper()

        # Basic postcode validation
        if not (5 <= len(clean_query) <= 8 and clean_query.isalnum()):
            return {"property_transactions": []}

        client = self._get_land_registry()
        results = {"property_transactions": []}

        try:
            transactions = await client.search_by_postcode(
                query,
                limit=options.max_results_per_source,
            )
            results["property_transactions"] = transactions
        except Exception as e:
            results["error"] = str(e)

        return results

    async def _search_uk_sanctions(
        self,
        query: str,
        options: SearchOptions,
    ) -> dict:
        """Search UK Sanctions list."""
        client = self._get_uk_sanctions()
        results = {"sanctioned_entities": []}

        try:
            entities = await client.search_by_name(query)
            results["sanctioned_entities"] = entities
        except Exception as e:
            results["error"] = str(e)

        return results

    async def _search_food_standards(
        self,
        query: str,
        options: SearchOptions,
    ) -> dict:
        """Search Food Standards Agency."""
        client = self._get_food_standards()
        results = {"food_establishments": []}

        try:
            # Try as business name first, then as postcode
            establishments = await client.search_establishments(
                name=query,
                page_size=options.max_results_per_source,
            )
            results["food_establishments"] = establishments
        except Exception as e:
            results["error"] = str(e)

        return results

    async def _search_gazette(
        self,
        query: str,
        options: SearchOptions,
    ) -> dict:
        """Search The Gazette for official notices."""
        client = self._get_gazette()
        results = {"gazette_notices": []}

        try:
            notices = await client.search_notices(
                query,
                results_per_page=options.max_results_per_source,
            )
            results["gazette_notices"] = notices
        except Exception as e:
            results["error"] = str(e)

        return results

    async def _search_cqc(
        self,
        query: str,
        options: SearchOptions,
    ) -> dict:
        """Search CQC for care providers."""
        client = self._get_cqc()
        results = {"cqc_locations": []}

        try:
            locations = await client.search_locations(
                name=query,
                per_page=options.max_results_per_source,
            )
            results["cqc_locations"] = locations
        except Exception as e:
            results["error"] = str(e)

        return results

    # Convenience methods for targeted searches

    async def search_company(self, name_or_number: str) -> UnifiedSearchResult:
        """Search specifically for a company."""
        options = SearchOptions(
            sources=DataSources.BUSINESS_EXTENDED,
            include_officers=True,
        )
        return await self.search(name_or_number, options)

    async def search_person(self, name: str) -> UnifiedSearchResult:
        """Search for a person across all relevant sources."""
        options = SearchOptions(
            sources=DataSources.PERSON_DUE_DILIGENCE,
            include_officers=True,
        )
        return await self.search(name, options)

    async def search_vehicle(self, registration: str) -> UnifiedSearchResult:
        """Search for a vehicle by registration."""
        options = SearchOptions(
            sources=DataSources.VEHICLES,  # MOT_HISTORY | DVLA_VEHICLE
            include_officers=False,
        )
        return await self.search(registration, options)

    async def search_legal(self, query: str) -> UnifiedSearchResult:
        """Search for legal cases and insolvency."""
        options = SearchOptions(
            sources=DataSources.LEGAL,
            include_officers=False,
        )
        return await self.search(query, options)

    async def search_charity(self, name: str) -> UnifiedSearchResult:
        """Search for charities."""
        options = SearchOptions(
            sources=DataSources.CHARITY_COMMISSION,
            include_officers=False,
        )
        return await self.search(name, options)

    async def search_financial(self, name: str) -> UnifiedSearchResult:
        """Search for financial services firms and sanctions."""
        options = SearchOptions(
            sources=DataSources.FINANCIAL,
            include_officers=True,
        )
        return await self.search(name, options)

    async def search_political(self, query: str) -> UnifiedSearchResult:
        """Search for political donations."""
        options = SearchOptions(
            sources=DataSources.POLITICAL,
            include_officers=False,
        )
        return await self.search(query, options)

    async def search_location(self, postcode: str) -> UnifiedSearchResult:
        """Search for data by postcode (property, crime, food hygiene, healthcare)."""
        options = SearchOptions(
            sources=DataSources.POLICE_DATA | DataSources.LAND_REGISTRY | DataSources.FOOD_STANDARDS | DataSources.CQC,
            include_officers=False,
        )
        return await self.search(postcode, options)

    async def search_property(self, postcode: str) -> UnifiedSearchResult:
        """Search for property transactions."""
        options = SearchOptions(
            sources=DataSources.PROPERTY,
            include_officers=False,
        )
        return await self.search(postcode, options)

    async def search_healthcare(self, query: str) -> UnifiedSearchResult:
        """Search for healthcare providers and food establishments."""
        options = SearchOptions(
            sources=DataSources.HEALTHCARE,
            include_officers=False,
        )
        return await self.search(query, options)

    async def search_regulatory(self, name: str) -> UnifiedSearchResult:
        """Search for regulatory records (sanctions, insolvency, disqualifications)."""
        options = SearchOptions(
            sources=DataSources.REGULATORY,
            include_officers=False,
        )
        return await self.search(name, options)

    async def due_diligence(self, name: str) -> UnifiedSearchResult:
        """Comprehensive due diligence search across all sources."""
        options = SearchOptions(
            sources=DataSources.ALL_EXTENDED,
            include_officers=True,
            timeout=60.0,  # Longer timeout for comprehensive search
        )
        return await self.search(name, options)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
