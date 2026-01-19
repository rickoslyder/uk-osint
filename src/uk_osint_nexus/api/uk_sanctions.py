"""UK Sanctions List (OFSI) client.

Data Source: https://www.gov.uk/government/publications/financial-sanctions-consolidated-list-of-targets
Rate Limit: N/A (downloadable data)
Authentication: None required

Coverage:
- Individuals and entities subject to UK financial sanctions
- Includes UN, EU-origin, and UK domestic sanctions
- Asset freeze targets
- Names, aliases, dates of birth, nationalities

Note: This downloads and searches the consolidated list.
The list is updated frequently; consider caching.
"""

from datetime import date, datetime
from typing import Optional
import xml.etree.ElementTree as ET

from pydantic import BaseModel

from .base import BaseAPIClient


class SanctionedEntity(BaseModel):
    """A sanctioned individual or entity."""

    source: str = "uk_sanctions"

    # Basic details
    group_id: Optional[str] = None
    name: str
    entity_type: str  # 'Individual', 'Entity', 'Ship'

    # For individuals
    title: Optional[str] = None
    name_parts: Optional[dict] = None  # forename, surname, etc.
    gender: Optional[str] = None
    date_of_birth: Optional[str] = None  # May be partial
    place_of_birth: Optional[str] = None
    nationality: Optional[str] = None
    passport_details: Optional[str] = None
    national_id: Optional[str] = None

    # For entities
    entity_subtype: Optional[str] = None  # 'Company', 'Ship', etc.

    # Aliases
    aliases: list[str] = []

    # Addresses
    addresses: list[dict] = []

    # Sanction details
    regime: Optional[str] = None  # 'Russia', 'Iran', 'Counter-Terrorism', etc.
    listed_on: Optional[date] = None
    last_updated: Optional[date] = None
    uk_statement: Optional[str] = None  # Reason for listing

    # Legal basis
    legal_basis: Optional[str] = None
    un_reference: Optional[str] = None

    raw_data: Optional[dict] = None


class UKSanctionsClient(BaseAPIClient):
    """Client for searching the UK Consolidated Sanctions List."""

    # Direct download URL for the consolidated list
    SANCTIONS_LIST_URL = "https://assets.publishing.service.gov.uk/media/consolidated-list-xml"
    BACKUP_URL = "https://ofsistorage.blob.core.windows.net/publishlive/2022format/ConList.xml"

    def __init__(self):
        super().__init__(
            base_url="https://assets.publishing.service.gov.uk",
            api_key=None,
            rate_limit=0.5,
        )
        self._cached_data: Optional[list[SanctionedEntity]] = None
        self._cache_time: Optional[datetime] = None
        self._cache_duration = 3600  # 1 hour cache

    @property
    def source_name(self) -> str:
        return "uk_sanctions"

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse date string."""
        if not date_str:
            return None
        try:
            # Handle various formats
            for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"]:
                try:
                    return datetime.strptime(date_str.split("T")[0], fmt.split("T")[0]).date()
                except ValueError:
                    continue
            return None
        except Exception:
            return None

    def _parse_entity_from_xml(self, element: ET.Element, ns: dict) -> Optional[SanctionedEntity]:
        """Parse a single entity from XML."""
        try:
            group_id = element.get("GroupId")

            # Determine entity type
            individual = element.find(".//Individual", ns)
            entity = element.find(".//Entity", ns)

            if individual is not None:
                return self._parse_individual(element, individual, group_id, ns)
            elif entity is not None:
                return self._parse_entity_record(element, entity, group_id, ns)

            return None
        except Exception:
            return None

    def _parse_individual(
        self,
        target: ET.Element,
        individual: ET.Element,
        group_id: str,
        ns: dict
    ) -> SanctionedEntity:
        """Parse individual from XML."""
        # Get names
        names = []
        name_parts = {}
        for name in individual.findall(".//Name", ns):
            name_type = name.get("NameType", "")
            parts = []
            for part in name.findall(".//NamePart", ns):
                part_text = part.text or ""
                part_type = part.get("NamePartType", "")
                parts.append(part_text)
                if part_type:
                    name_parts[part_type] = part_text
            if parts:
                names.append(" ".join(parts))

        primary_name = names[0] if names else "Unknown"
        aliases = names[1:] if len(names) > 1 else []

        # Get DOB
        dob = None
        dob_elem = individual.find(".//DOB", ns)
        if dob_elem is not None:
            dob = dob_elem.text

        # Get nationality
        nationality = None
        nat_elem = individual.find(".//Nationality", ns)
        if nat_elem is not None:
            nationality = nat_elem.text

        # Get addresses
        addresses = self._parse_addresses(target, ns)

        # Get regime
        regime = None
        regime_elem = target.find(".//Regime", ns)
        if regime_elem is not None:
            regime = regime_elem.text

        return SanctionedEntity(
            source=self.source_name,
            group_id=group_id,
            name=primary_name,
            entity_type="Individual",
            name_parts=name_parts if name_parts else None,
            date_of_birth=dob,
            nationality=nationality,
            aliases=aliases,
            addresses=addresses,
            regime=regime,
            raw_data={"group_id": group_id},
        )

    def _parse_entity_record(
        self,
        target: ET.Element,
        entity: ET.Element,
        group_id: str,
        ns: dict
    ) -> SanctionedEntity:
        """Parse entity (non-individual) from XML."""
        # Get names
        names = []
        for name in entity.findall(".//Name", ns):
            parts = []
            for part in name.findall(".//NamePart", ns):
                parts.append(part.text or "")
            if parts:
                names.append(" ".join(parts))

        primary_name = names[0] if names else "Unknown"
        aliases = names[1:] if len(names) > 1 else []

        # Get entity subtype
        subtype = None
        subtype_elem = entity.find(".//EntitySubType", ns)
        if subtype_elem is not None:
            subtype = subtype_elem.text

        # Get addresses
        addresses = self._parse_addresses(target, ns)

        # Get regime
        regime = None
        regime_elem = target.find(".//Regime", ns)
        if regime_elem is not None:
            regime = regime_elem.text

        return SanctionedEntity(
            source=self.source_name,
            group_id=group_id,
            name=primary_name,
            entity_type="Entity",
            entity_subtype=subtype,
            aliases=aliases,
            addresses=addresses,
            regime=regime,
            raw_data={"group_id": group_id},
        )

    def _parse_addresses(self, target: ET.Element, ns: dict) -> list[dict]:
        """Parse addresses from target element."""
        addresses = []
        for addr in target.findall(".//Address", ns):
            addr_dict = {}
            for child in addr:
                tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                addr_dict[tag] = child.text
            if addr_dict:
                addresses.append(addr_dict)
        return addresses

    async def _load_sanctions_list(self) -> list[SanctionedEntity]:
        """Download and parse the sanctions list."""
        # Check cache
        if self._cached_data and self._cache_time:
            age = (datetime.now() - self._cache_time).total_seconds()
            if age < self._cache_duration:
                return self._cached_data

        import httpx

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                # Try primary URL first
                response = await client.get(self.BACKUP_URL)
                if response.status_code != 200:
                    return []

                xml_content = response.text

            # Parse XML
            root = ET.fromstring(xml_content)

            # Handle namespaces
            ns = {}
            if root.tag.startswith("{"):
                ns_uri = root.tag[1:root.tag.index("}")]
                ns = {"": ns_uri}
                ET.register_namespace("", ns_uri)

            entities = []

            # Find all targets
            for target in root.iter():
                if "Target" in target.tag or "FinancialSanctionsTarget" in target.tag:
                    entity = self._parse_entity_from_xml(target, ns)
                    if entity:
                        entities.append(entity)

            # Cache the results
            self._cached_data = entities
            self._cache_time = datetime.now()

            return entities

        except Exception as e:
            import sys
            print(f"[UK Sanctions] Error loading list: {str(e)[:100]}", file=sys.stderr)
            return self._cached_data or []

    async def search(self, query: str, **kwargs) -> list[SanctionedEntity]:
        """Search the sanctions list by name."""
        return await self.search_by_name(query, **kwargs)

    async def search_by_name(
        self,
        name: str,
        include_aliases: bool = True,
        entity_type: Optional[str] = None,
    ) -> list[SanctionedEntity]:
        """Search sanctions list by name.

        Args:
            name: Name to search for
            include_aliases: Whether to search aliases too
            entity_type: Filter by 'Individual' or 'Entity'

        Returns:
            List of matching SanctionedEntity objects
        """
        entities = await self._load_sanctions_list()

        name_lower = name.lower()
        results = []

        for entity in entities:
            # Filter by entity type if specified
            if entity_type and entity.entity_type != entity_type:
                continue

            # Check main name
            if name_lower in entity.name.lower():
                results.append(entity)
                continue

            # Check aliases
            if include_aliases:
                for alias in entity.aliases:
                    if name_lower in alias.lower():
                        results.append(entity)
                        break

        return results

    async def check_sanctions(
        self,
        name: str,
        date_of_birth: Optional[str] = None,
    ) -> dict:
        """Check if a name appears on the sanctions list.

        Args:
            name: Name to check
            date_of_birth: Optional DOB for better matching

        Returns:
            Dict with check results
        """
        matches = await self.search_by_name(name)

        # If DOB provided, filter matches
        if date_of_birth and matches:
            dob_matches = [
                m for m in matches
                if m.date_of_birth and date_of_birth in m.date_of_birth
            ]
            if dob_matches:
                matches = dob_matches

        return {
            "name": name,
            "is_sanctioned": len(matches) > 0,
            "match_count": len(matches),
            "matches": matches,
            "check_date": datetime.now().isoformat(),
        }

    async def get_by_regime(self, regime: str) -> list[SanctionedEntity]:
        """Get all sanctions for a specific regime.

        Args:
            regime: Regime name (e.g., 'Russia', 'Iran')

        Returns:
            List of SanctionedEntity objects
        """
        entities = await self._load_sanctions_list()

        regime_lower = regime.lower()
        return [
            e for e in entities
            if e.regime and regime_lower in e.regime.lower()
        ]

    async def get_statistics(self) -> dict:
        """Get statistics about the sanctions list.

        Returns:
            Dict with statistics
        """
        entities = await self._load_sanctions_list()

        individuals = [e for e in entities if e.entity_type == "Individual"]
        entities_list = [e for e in entities if e.entity_type == "Entity"]

        # Count by regime
        regimes: dict[str, int] = {}
        for e in entities:
            regime = e.regime or "Unknown"
            regimes[regime] = regimes.get(regime, 0) + 1

        return {
            "total_entries": len(entities),
            "individuals": len(individuals),
            "entities": len(entities_list),
            "regimes": regimes,
            "last_loaded": self._cache_time.isoformat() if self._cache_time else None,
        }
