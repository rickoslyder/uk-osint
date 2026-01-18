"""Entity correlation engine for linking records across data sources."""

from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from typing import Optional

from ..models.entities import (
    Address,
    Company,
    Contract,
    EntityType,
    LegalCase,
    Officer,
    Person,
    SearchResult,
    Vehicle,
)


@dataclass
class EntityLink:
    """A link between two entities from different sources."""

    source_entity: SearchResult
    target_entity: SearchResult
    link_type: str  # e.g., "director_of", "party_in_case", "contract_supplier"
    confidence: float  # 0.0 to 1.0
    evidence: list[str] = field(default_factory=list)


@dataclass
class EntityProfile:
    """Unified profile for an entity aggregated from multiple sources."""

    primary_name: str
    entity_type: EntityType
    sources: list[str] = field(default_factory=list)
    companies: list[Company] = field(default_factory=list)
    officers: list[Officer] = field(default_factory=list)
    legal_cases: list[LegalCase] = field(default_factory=list)
    contracts: list[Contract] = field(default_factory=list)
    vehicles: list[Vehicle] = field(default_factory=list)
    addresses: list[Address] = field(default_factory=list)
    links: list[EntityLink] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def total_records(self) -> int:
        return (
            len(self.companies)
            + len(self.officers)
            + len(self.legal_cases)
            + len(self.contracts)
            + len(self.vehicles)
        )


class EntityCorrelator:
    """Correlates entities across different data sources.

    Uses name matching, address matching, and other heuristics to
    link related records from Companies House, BAILII, Contracts Finder, etc.
    """

    def __init__(self, min_confidence: float = 0.7):
        """Initialize correlator.

        Args:
            min_confidence: Minimum confidence threshold for links (0.0-1.0)
        """
        self.min_confidence = min_confidence

    def _normalize_name(self, name: str) -> str:
        """Normalize a name for comparison."""
        # Remove common suffixes
        suffixes = [
            "LIMITED",
            "LTD",
            "PLC",
            "LLP",
            "INC",
            "INCORPORATED",
            "COMPANY",
            "CO",
            "THE",
            "MR",
            "MRS",
            "MS",
            "DR",
            "PROF",
        ]
        normalized = name.upper().strip()
        for suffix in suffixes:
            normalized = normalized.replace(f" {suffix}", "")
            normalized = normalized.replace(f"{suffix} ", "")
        # Remove punctuation
        normalized = "".join(c for c in normalized if c.isalnum() or c.isspace())
        # Normalize whitespace
        normalized = " ".join(normalized.split())
        return normalized

    def _name_similarity(self, name1: str, name2: str) -> float:
        """Calculate similarity between two names."""
        n1 = self._normalize_name(name1)
        n2 = self._normalize_name(name2)

        # Exact match after normalization
        if n1 == n2:
            return 1.0

        # Use sequence matcher for fuzzy matching
        return SequenceMatcher(None, n1, n2).ratio()

    def _address_similarity(self, addr1: Optional[Address], addr2: Optional[Address]) -> float:
        """Calculate similarity between two addresses."""
        if not addr1 or not addr2:
            return 0.0

        # Compare postal codes (strongest signal)
        if addr1.postal_code and addr2.postal_code:
            pc1 = addr1.postal_code.replace(" ", "").upper()
            pc2 = addr2.postal_code.replace(" ", "").upper()
            if pc1 == pc2:
                return 0.9

        # Compare full address string
        str1 = str(addr1).upper()
        str2 = str(addr2).upper()

        return SequenceMatcher(None, str1, str2).ratio()

    def find_person_company_links(
        self,
        officers: list[Officer],
        companies: list[Company],
    ) -> list[EntityLink]:
        """Find links between officers and companies."""
        links = []

        for officer in officers:
            for company in companies:
                confidence = 0.0
                evidence = []

                # Check company number match
                if officer.company_number and company.company_number:
                    if officer.company_number == company.company_number:
                        confidence = 1.0
                        evidence.append(
                            f"Direct company number match: {officer.company_number}"
                        )

                # Check company name match
                if officer.company_name and company.company_name:
                    name_sim = self._name_similarity(officer.company_name, company.company_name)
                    if name_sim > 0.8:
                        confidence = max(confidence, name_sim)
                        evidence.append(
                            f"Company name match: {officer.company_name} ≈ {company.company_name}"
                        )

                if confidence >= self.min_confidence:
                    links.append(
                        EntityLink(
                            source_entity=SearchResult(
                                entity_type=EntityType.PERSON,
                                source=officer.source,
                                entity=officer,
                                matched_query=officer.name,
                            ),
                            target_entity=SearchResult(
                                entity_type=EntityType.COMPANY,
                                source=company.source,
                                entity=company,
                                matched_query=company.company_name,
                            ),
                            link_type="director_of" if officer.role == "director" else officer.role,
                            confidence=confidence,
                            evidence=evidence,
                        )
                    )

        return links

    def find_company_contract_links(
        self,
        companies: list[Company],
        contracts: list[Contract],
    ) -> list[EntityLink]:
        """Find links between companies and government contracts."""
        links = []

        for company in companies:
            for contract in contracts:
                confidence = 0.0
                evidence = []

                # Check supplier name match
                if contract.supplier_name:
                    name_sim = self._name_similarity(company.company_name, contract.supplier_name)
                    if name_sim > 0.7:
                        confidence = max(confidence, name_sim)
                        evidence.append(
                            f"Supplier name match: {company.company_name} ≈ {contract.supplier_name}"
                        )

                # Check buyer name match (company might be a public body)
                if contract.buyer_name:
                    name_sim = self._name_similarity(company.company_name, contract.buyer_name)
                    if name_sim > 0.7:
                        confidence = max(confidence, name_sim * 0.9)  # Slightly lower for buyers
                        evidence.append(
                            f"Buyer name match: {company.company_name} ≈ {contract.buyer_name}"
                        )

                if confidence >= self.min_confidence:
                    link_type = "contract_supplier"
                    if contract.buyer_name and self._name_similarity(
                        company.company_name, contract.buyer_name
                    ) > self._name_similarity(company.company_name, contract.supplier_name or ""):
                        link_type = "contract_buyer"

                    links.append(
                        EntityLink(
                            source_entity=SearchResult(
                                entity_type=EntityType.COMPANY,
                                source=company.source,
                                entity=company,
                                matched_query=company.company_name,
                            ),
                            target_entity=SearchResult(
                                entity_type=EntityType.CONTRACT,
                                source=contract.source,
                                entity=contract,
                                matched_query=contract.title,
                            ),
                            link_type=link_type,
                            confidence=confidence,
                            evidence=evidence,
                        )
                    )

        return links

    def find_person_legal_links(
        self,
        officers: list[Officer],
        cases: list[LegalCase],
    ) -> list[EntityLink]:
        """Find links between people and legal cases."""
        links = []

        for officer in officers:
            for case in cases:
                confidence = 0.0
                evidence = []

                # Check party names
                for party in case.parties:
                    name_sim = self._name_similarity(officer.name, party)
                    if name_sim > 0.8:
                        confidence = max(confidence, name_sim)
                        evidence.append(f"Party name match: {officer.name} ≈ {party}")

                # Check case name for mentions
                name_sim = self._name_similarity(officer.name, case.case_name)
                if name_sim > 0.5:  # Lower threshold for case names
                    # Boost if surname appears in case name
                    surname = officer.name.split()[-1] if officer.name else ""
                    if surname.upper() in case.case_name.upper():
                        confidence = max(confidence, 0.75)
                        evidence.append(f"Name appears in case: {case.case_name}")

                if confidence >= self.min_confidence:
                    links.append(
                        EntityLink(
                            source_entity=SearchResult(
                                entity_type=EntityType.PERSON,
                                source=officer.source,
                                entity=officer,
                                matched_query=officer.name,
                            ),
                            target_entity=SearchResult(
                                entity_type=EntityType.LEGAL_CASE,
                                source=case.source,
                                entity=case,
                                matched_query=case.case_name,
                            ),
                            link_type="party_in_case",
                            confidence=confidence,
                            evidence=evidence,
                        )
                    )

        return links

    def find_company_legal_links(
        self,
        companies: list[Company],
        cases: list[LegalCase],
    ) -> list[EntityLink]:
        """Find links between companies and legal cases."""
        links = []

        for company in companies:
            for case in cases:
                confidence = 0.0
                evidence = []

                # Check party names
                for party in case.parties:
                    name_sim = self._name_similarity(company.company_name, party)
                    if name_sim > 0.7:
                        confidence = max(confidence, name_sim)
                        evidence.append(f"Party name match: {company.company_name} ≈ {party}")

                # Check case name
                name_sim = self._name_similarity(company.company_name, case.case_name)
                if name_sim > 0.5:
                    confidence = max(confidence, name_sim * 0.9)
                    evidence.append(f"Name in case title: {case.case_name}")

                if confidence >= self.min_confidence:
                    links.append(
                        EntityLink(
                            source_entity=SearchResult(
                                entity_type=EntityType.COMPANY,
                                source=company.source,
                                entity=company,
                                matched_query=company.company_name,
                            ),
                            target_entity=SearchResult(
                                entity_type=EntityType.LEGAL_CASE,
                                source=case.source,
                                entity=case,
                                matched_query=case.case_name,
                            ),
                            link_type="party_in_case",
                            confidence=confidence,
                            evidence=evidence,
                        )
                    )

        return links

    def build_profile(
        self,
        name: str,
        companies: list[Company],
        officers: list[Officer],
        legal_cases: list[LegalCase],
        contracts: list[Contract],
        vehicles: list[Vehicle],
    ) -> EntityProfile:
        """Build a unified profile from search results.

        Args:
            name: Primary name for the profile
            companies: Company results
            officers: Officer/person results
            legal_cases: Legal case results
            contracts: Contract results
            vehicles: Vehicle results

        Returns:
            EntityProfile with all linked data
        """
        # Determine entity type based on results
        if officers and not companies:
            entity_type = EntityType.PERSON
        elif companies:
            entity_type = EntityType.COMPANY
        else:
            entity_type = EntityType.PERSON

        # Collect all sources
        sources = set()
        for c in companies:
            sources.add(c.source)
        for o in officers:
            sources.add(o.source)
        for l in legal_cases:
            sources.add(l.source)
        for ct in contracts:
            sources.add(ct.source)
        for v in vehicles:
            sources.add(v.source)

        # Collect addresses
        addresses = []
        for c in companies:
            if c.registered_office_address:
                addresses.append(c.registered_office_address)
        for o in officers:
            if o.address:
                addresses.append(o.address)

        # Find all links
        links = []
        links.extend(self.find_person_company_links(officers, companies))
        links.extend(self.find_company_contract_links(companies, contracts))
        links.extend(self.find_person_legal_links(officers, legal_cases))
        links.extend(self.find_company_legal_links(companies, legal_cases))

        return EntityProfile(
            primary_name=name,
            entity_type=entity_type,
            sources=list(sources),
            companies=companies,
            officers=officers,
            legal_cases=legal_cases,
            contracts=contracts,
            vehicles=vehicles,
            addresses=addresses,
            links=links,
        )

    def correlate_results(self, results: list[SearchResult]) -> list[EntityLink]:
        """Find all correlations between a list of search results.

        Args:
            results: List of SearchResult from unified search

        Returns:
            List of EntityLink correlations
        """
        # Group by entity type
        companies = [r.entity for r in results if isinstance(r.entity, Company)]
        officers = [r.entity for r in results if isinstance(r.entity, Officer)]
        legal_cases = [r.entity for r in results if isinstance(r.entity, LegalCase)]
        contracts = [r.entity for r in results if isinstance(r.entity, Contract)]

        # Find all cross-source links
        links = []
        links.extend(self.find_person_company_links(officers, companies))
        links.extend(self.find_company_contract_links(companies, contracts))
        links.extend(self.find_person_legal_links(officers, legal_cases))
        links.extend(self.find_company_legal_links(companies, legal_cases))

        # Sort by confidence
        links.sort(key=lambda x: x.confidence, reverse=True)

        return links
