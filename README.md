# UK OSINT Nexus

A unified UK Open Source Intelligence (OSINT) tool that aggregates data from multiple free government APIs and open databases into a single investigative platform.

## Features

- **Unified Search**: Query multiple data sources simultaneously
- **Companies House Integration**: Search UK companies, directors, filing history
- **MOT History**: Vehicle registration lookups with full MOT test history
- **BAILII Legal Records**: Search UK court cases and legislation
- **Contracts Finder**: Government procurement and contract data
- **Cross-Source Correlation**: Automatically link related entities across sources
- **Multiple Export Formats**: JSON, CSV, Markdown, HTML reports

## Data Sources

| Source | Type | API Key Required | Data |
|--------|------|------------------|------|
| Companies House | API | Optional* | Companies, directors, filings |
| MOT History | API | Yes | Vehicle MOT history |
| BAILII | Scraper | No | Court cases, legislation |
| Contracts Finder | API | No | Government contracts |

*Companies House works without an API key for basic searches but is rate-limited.

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/uk-osint-nexus.git
cd uk-osint-nexus

# Install with pip
pip install -e .

# Or install with development dependencies
pip install -e ".[dev]"
```

## Configuration

Create a `.env` file or set environment variables:

```bash
# Optional but recommended - get free API key at:
# https://developer.company-information.service.gov.uk/
export COMPANIES_HOUSE_API_KEY=your_key_here

# Optional - get free API key at:
# https://dvsa.github.io/mot-history-api-documentation/
export MOT_HISTORY_API_KEY=your_key_here
```

## CLI Usage

### Unified Search

Search across all data sources:

```bash
# Search for a company or person
osint search "Acme Limited"

# Search with specific sources
osint search "John Smith" --no-vehicles --no-contracts

# Export results to JSON
osint search "Example Corp" --output results.json

# Limit results per source
osint search "Technology" --max 20
```

### Company Lookup

```bash
# Search by company name
osint company "Tesco"

# Search by company number
osint company 00445790

# Include filing history
osint company "Sainsburys" --filings
```

### Vehicle Lookup

```bash
# Look up by registration
osint vehicle AB12CDE
```

### Legal Search

```bash
# Search BAILII for cases
osint legal "intellectual property"

# Filter by court
osint legal "Smith v Jones" --court uksc

# Limit results
osint legal "breach of contract" --max 20
```

### Contract Search

```bash
# Search by keyword
osint contracts "software development"

# Filter by buyer
osint contracts --buyer "NHS"

# Filter by supplier
osint contracts --supplier "Capita"

# Filter by status
osint contracts --status Open
```

### Configuration

```bash
# Check configuration and API key status
osint config
```

## Python API

```python
import asyncio
from uk_osint_nexus.core.search import UnifiedSearch, SearchOptions, DataSources
from uk_osint_nexus.core.correlator import EntityCorrelator

async def main():
    # Create search client
    async with UnifiedSearch() as searcher:
        # Search all sources
        result = await searcher.search("Acme Limited")

        print(f"Found {result.total_results} results")

        # Access specific results
        for company in result.companies:
            print(f"Company: {company.company_name} ({company.company_number})")

        for officer in result.officers:
            print(f"Officer: {officer.name} - {officer.role}")

        # Correlate results
        correlator = EntityCorrelator()
        profile = correlator.build_profile(
            name="Acme Limited",
            companies=result.companies,
            officers=result.officers,
            legal_cases=result.legal_cases,
            contracts=result.contracts,
            vehicles=result.vehicles,
        )

        # View correlations
        for link in profile.links:
            print(f"Link: {link.source_entity.entity_type} -> {link.target_entity.entity_type}")
            print(f"  Confidence: {link.confidence:.0%}")
            print(f"  Evidence: {link.evidence}")

asyncio.run(main())
```

### Search Specific Sources

```python
from uk_osint_nexus.api.companies_house import CompaniesHouseClient
from uk_osint_nexus.api.contracts_finder import ContractsFinderClient
from uk_osint_nexus.scrapers.bailii import BAILIIScraper

async def search_companies():
    async with CompaniesHouseClient(api_key="your_key") as client:
        # Search companies
        companies = await client.search_companies("Tech")

        # Get company details
        company = await client.get_company("00445790")

        # Get officers
        officers = await client.get_company_officers("00445790")

async def search_contracts():
    async with ContractsFinderClient() as client:
        # Search contracts
        contracts = await client.search_contracts(
            query="IT services",
            buyer_name="NHS",
            status="Awarded",
        )

        # Get supplier profile
        profile = await client.get_supplier_profile("Capita")

async def search_legal():
    async with BAILIIScraper() as scraper:
        # Search cases
        cases = await scraper.search("data protection")

        # Search by party name
        cases = await scraper.search_by_party("Google")
```

### Export Results

```python
from uk_osint_nexus.export import Exporter, ExportFormat
from pathlib import Path

exporter = Exporter()

# Export to JSON
json_output = exporter.export_search_result(result, ExportFormat.JSON)

# Export to file
exporter.export_search_result(
    result,
    ExportFormat.HTML,
    output_path=Path("report.html")
)

# Export entity profile
exporter.export_profile(profile, ExportFormat.MARKDOWN, Path("profile.md"))
```

## Project Structure

```
uk-osint-nexus/
├── src/uk_osint_nexus/
│   ├── api/                 # API clients
│   │   ├── base.py          # Base client with rate limiting
│   │   ├── companies_house.py
│   │   ├── contracts_finder.py
│   │   └── mot_history.py
│   ├── scrapers/            # Web scrapers
│   │   └── bailii.py        # BAILII legal database
│   ├── models/              # Data models
│   │   └── entities.py      # Pydantic models
│   ├── core/                # Core functionality
│   │   ├── search.py        # Unified search
│   │   └── correlator.py    # Entity correlation
│   ├── cli/                 # CLI interface
│   │   └── main.py
│   ├── export/              # Export functionality
│   │   └── exporter.py
│   └── utils/               # Utilities
│       └── config.py
├── tests/
├── pyproject.toml
└── README.md
```

## Rate Limits

The tool respects API rate limits:

| Source | Rate Limit | Notes |
|--------|------------|-------|
| Companies House | 600/5min (2/sec) | Higher limits available on request |
| MOT History | ~60/min | Varies by plan |
| BAILII | ~1/sec | Be respectful |
| Contracts Finder | ~120/min | No strict limit |

## Legal Considerations

- This tool accesses publicly available data
- Respect rate limits and terms of service
- Data may be subject to GDPR and data protection laws
- Use responsibly for legitimate purposes only
- Electoral roll data is restricted and not included in this free version

## Future Enhancements

- [ ] Land Registry integration (requires payment)
- [ ] Electoral roll access (requires commercial API)
- [ ] Graph visualization of entity networks
- [ ] Persistent database for caching and history
- [ ] Alert monitoring for entity changes
- [ ] Browser-based UI

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions welcome! Please read CONTRIBUTING.md for guidelines.

## Acknowledgments

- [Companies House API](https://developer.company-information.service.gov.uk/)
- [DVSA MOT History API](https://dvsa.github.io/mot-history-api-documentation/)
- [BAILII](https://www.bailii.org/)
- [Contracts Finder](https://www.contractsfinder.service.gov.uk/)
