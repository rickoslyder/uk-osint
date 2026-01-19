# UK OSINT Nexus

A unified UK Open Source Intelligence (OSINT) tool that aggregates data from multiple free government APIs and open databases into a single investigative platform.

## Features

- **Web Interface**: Browser-based UI at [osint.rbnk.uk](https://osint.rbnk.uk)
- **Unified Search**: Query 17 data sources simultaneously
- **Due Diligence**: Insolvency, sanctions, disqualified directors, gazette notices
- **Business Intelligence**: Companies, charities, FCA-regulated firms, government contracts
- **Legal Research**: Court cases, legislation, official notices
- **Vehicle Lookups**: MOT history and DVLA vehicle enquiries
- **Location Data**: Property prices, food hygiene, healthcare ratings, crime data
- **Cross-Source Correlation**: Automatically link related entities across sources
- **Multiple Export Formats**: JSON, CSV, Markdown, HTML reports
- **CLI & Python API**: Full programmatic access

## Data Sources (17)

### Business & Corporate
| Source | Type | API Key Required | Data |
|--------|------|------------------|------|
| Companies House | API | Optional* | Companies, directors, filings, charges, PSCs |
| Charity Commission | API | No | Registered charities, trustees |
| FCA Register | API | No | Regulated firms and individuals |
| Contracts Finder | API | No | Government contracts and procurement |

### Due Diligence & Risk
| Source | Type | API Key Required | Data |
|--------|------|------------------|------|
| Insolvency Service | Scraper | No | Bankruptcies, IVAs, DROs |
| Disqualified Directors | API | Optional* | Director disqualifications |
| UK Sanctions List (OFSI) | XML Feed | No | Sanctioned individuals and entities |
| The Gazette | Atom Feed | No | Official notices (insolvency, company) |

### Legal & Political
| Source | Type | API Key Required | Data |
|--------|------|------------------|------|
| BAILII | Scraper | No | Court cases, legislation |
| Electoral Commission | API | No | Political donations |

### Vehicles
| Source | Type | API Key Required | Data |
|--------|------|------------------|------|
| MOT History | API | Yes | Vehicle MOT test history |
| DVLA Vehicle Enquiry | API | Yes | Vehicle details, tax, MOT status |

### Location-Based (Postcode)
| Source | Type | API Key Required | Data |
|--------|------|------------------|------|
| Land Registry | SPARQL | No | Property price paid data |
| Food Standards Agency | API | No | Food hygiene ratings |
| CQC | API | No | Healthcare provider ratings |
| Police Data | API | No | Street-level crime data |

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
│   ├── api/                 # API clients (17 data sources)
│   │   ├── base.py          # Base client with rate limiting
│   │   ├── companies_house.py
│   │   ├── companies_house_extended.py  # Disqualified, PSCs, charges
│   │   ├── contracts_finder.py
│   │   ├── mot_history.py
│   │   ├── charity_commission.py
│   │   ├── fca_register.py
│   │   ├── dvla_vehicle.py
│   │   ├── electoral_commission.py
│   │   ├── police_data.py
│   │   ├── insolvency_service.py
│   │   ├── land_registry.py
│   │   ├── uk_sanctions.py
│   │   ├── food_standards.py
│   │   ├── gazette.py
│   │   └── cqc.py
│   ├── scrapers/            # Web scrapers
│   │   └── bailii.py        # BAILII legal database
│   ├── models/              # Data models
│   │   └── entities.py      # Pydantic models
│   ├── core/                # Core functionality
│   │   ├── search.py        # Unified search engine
│   │   └── correlator.py    # Entity correlation
│   ├── web/                 # Web interface
│   │   ├── server.py        # FastAPI server
│   │   ├── templates/       # Jinja2 templates
│   │   └── static/          # CSS, JS assets
│   ├── cli/                 # CLI interface
│   │   └── main.py
│   ├── export/              # Export functionality
│   │   └── exporter.py
│   └── utils/               # Utilities
│       └── config.py
├── tests/
├── Dockerfile
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

- [ ] Graph visualization of entity networks
- [ ] Persistent database for caching and history
- [ ] Alert monitoring for entity changes
- [ ] Electoral roll access (requires commercial API)
- [x] ~~Land Registry integration~~ (implemented via SPARQL)
- [x] ~~Browser-based UI~~ (live at osint.rbnk.uk)

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions welcome! Please read CONTRIBUTING.md for guidelines.

## Acknowledgments

- [Companies House API](https://developer.company-information.service.gov.uk/)
- [DVSA MOT History API](https://dvsa.github.io/mot-history-api-documentation/)
- [DVLA Vehicle Enquiry Service](https://developer-portal.driver-vehicle-licensing.api.gov.uk/)
- [BAILII](https://www.bailii.org/)
- [Contracts Finder](https://www.contractsfinder.service.gov.uk/)
- [Charity Commission](https://register-of-charities.charitycommission.gov.uk/)
- [FCA Register](https://register.fca.org.uk/)
- [Electoral Commission](https://www.electoralcommission.org.uk/)
- [Insolvency Service](https://www.gov.uk/government/organisations/insolvency-service)
- [UK Sanctions List (OFSI)](https://www.gov.uk/government/publications/financial-sanctions-consolidated-list-of-targets)
- [The Gazette](https://www.thegazette.co.uk/)
- [Land Registry Price Paid Data](https://landregistry.data.gov.uk/)
- [Food Standards Agency](https://ratings.food.gov.uk/)
- [Care Quality Commission](https://www.cqc.org.uk/)
- [Police Data API](https://data.police.uk/)
