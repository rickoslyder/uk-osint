"""Core entity models for UK OSINT data."""

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class EntityType(str, Enum):
    """Types of entities in the OSINT system."""

    PERSON = "person"
    COMPANY = "company"
    VEHICLE = "vehicle"
    PROPERTY = "property"
    LEGAL_CASE = "legal_case"
    CONTRACT = "contract"


class Address(BaseModel):
    """UK address model."""

    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    locality: Optional[str] = None
    region: Optional[str] = None
    postal_code: Optional[str] = None
    country: str = "United Kingdom"
    raw_address: Optional[str] = None

    def __str__(self) -> str:
        parts = [
            self.address_line_1,
            self.address_line_2,
            self.locality,
            self.region,
            self.postal_code,
        ]
        return ", ".join(p for p in parts if p)


class Person(BaseModel):
    """Person entity - could be from electoral roll, company records, etc."""

    source: str = Field(description="Data source (e.g., 'companies_house', 'bailii')")
    name: str
    forename: Optional[str] = None
    surname: Optional[str] = None
    date_of_birth: Optional[date] = None
    month_of_birth: Optional[int] = None
    year_of_birth: Optional[int] = None
    nationality: Optional[str] = None
    addresses: list[Address] = Field(default_factory=list)
    occupation: Optional[str] = None
    country_of_residence: Optional[str] = None
    raw_data: dict = Field(default_factory=dict)

    @property
    def display_name(self) -> str:
        if self.forename and self.surname:
            return f"{self.forename} {self.surname}"
        return self.name


class Officer(BaseModel):
    """Company officer (director, secretary, etc.)."""

    source: str = "companies_house"
    officer_id: Optional[str] = None
    name: str
    role: str = Field(description="e.g., 'director', 'secretary'")
    appointed_on: Optional[date] = None
    resigned_on: Optional[date] = None
    date_of_birth: Optional[dict] = None  # {month: int, year: int}
    nationality: Optional[str] = None
    country_of_residence: Optional[str] = None
    occupation: Optional[str] = None
    address: Optional[Address] = None
    company_number: Optional[str] = None
    company_name: Optional[str] = None
    raw_data: dict = Field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        return self.resigned_on is None


class Company(BaseModel):
    """UK registered company."""

    source: str = "companies_house"
    company_number: str
    company_name: str
    company_status: Optional[str] = None
    company_type: Optional[str] = None
    date_of_creation: Optional[date] = None
    date_of_cessation: Optional[date] = None
    registered_office_address: Optional[Address] = None
    sic_codes: list[str] = Field(default_factory=list)
    officers: list[Officer] = Field(default_factory=list)
    previous_names: list[dict] = Field(default_factory=list)
    accounts_next_due: Optional[date] = None
    confirmation_statement_next_due: Optional[date] = None
    has_charges: bool = False
    has_insolvency_history: bool = False
    raw_data: dict = Field(default_factory=dict)

    @property
    def is_active(self) -> bool:
        return self.company_status in ("active", "Active")


class Vehicle(BaseModel):
    """UK registered vehicle."""

    source: str = "dvla"
    registration_number: str
    make: Optional[str] = None
    model: Optional[str] = None
    colour: Optional[str] = None
    fuel_type: Optional[str] = None
    engine_capacity: Optional[int] = None
    year_of_manufacture: Optional[int] = None
    date_of_first_registration: Optional[date] = None
    tax_status: Optional[str] = None
    tax_due_date: Optional[date] = None
    mot_status: Optional[str] = None
    mot_expiry_date: Optional[date] = None
    co2_emissions: Optional[int] = None
    type_approval: Optional[str] = None
    wheelplan: Optional[str] = None
    revenue_weight: Optional[int] = None
    mot_history: list[dict] = Field(default_factory=list)
    raw_data: dict = Field(default_factory=dict)


class LegalCase(BaseModel):
    """Court case from BAILII or other legal sources."""

    source: str = "bailii"
    case_id: Optional[str] = None
    neutral_citation: Optional[str] = None
    case_name: str
    court: Optional[str] = None
    date_heard: Optional[date] = None
    date_judgment: Optional[date] = None
    judges: list[str] = Field(default_factory=list)
    parties: list[str] = Field(default_factory=list)
    subject_keywords: list[str] = Field(default_factory=list)
    summary: Optional[str] = None
    full_text_url: Optional[str] = None
    raw_data: dict = Field(default_factory=dict)


class Contract(BaseModel):
    """Government contract from Contracts Finder."""

    source: str = "contracts_finder"
    notice_id: str
    title: str
    description: Optional[str] = None
    published_date: Optional[datetime] = None
    deadline_date: Optional[datetime] = None
    value_low: Optional[float] = None
    value_high: Optional[float] = None
    currency: str = "GBP"
    buyer_name: Optional[str] = None
    buyer_id: Optional[str] = None
    supplier_name: Optional[str] = None
    awarded_date: Optional[datetime] = None
    awarded_value: Optional[float] = None
    status: Optional[str] = None
    cpv_codes: list[str] = Field(default_factory=list)
    region: Optional[str] = None
    notice_type: Optional[str] = None
    url: Optional[str] = None
    raw_data: dict = Field(default_factory=dict)


class SearchResult(BaseModel):
    """Unified search result from any source."""

    entity_type: EntityType
    source: str
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    entity: Person | Company | Vehicle | LegalCase | Contract
    matched_query: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    def __str__(self) -> str:
        return f"[{self.source}] {self.entity_type.value}: {self.entity}"
