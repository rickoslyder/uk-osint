"""FastAPI server for UK OSINT Nexus web interface."""

import json
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from ..core.correlator import EntityCorrelator
from ..core.search import DataSources, SearchOptions, UnifiedSearch
from ..export import ExportFormat, Exporter

# Get paths
WEB_DIR = Path(__file__).parent
STATIC_DIR = WEB_DIR / "static"
TEMPLATES_DIR = WEB_DIR / "templates"

# Create FastAPI app
app = FastAPI(
    title="UK OSINT Nexus",
    description="Unified UK Open Source Intelligence Tool",
    version="0.1.0",
)

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Templates
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Global search instance
_search: Optional[UnifiedSearch] = None


def get_search() -> UnifiedSearch:
    """Get or create search instance."""
    global _search
    if _search is None:
        _search = UnifiedSearch()
    return _search


def json_serializer(obj):
    """Custom JSON serializer for dates."""
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    return str(obj)


# Request/Response models
class SearchRequest(BaseModel):
    query: str
    companies: bool = True
    officers: bool = True
    vehicles: bool = True
    legal: bool = True
    contracts: bool = True
    max_results: int = 20


class CompanyRequest(BaseModel):
    query: str
    include_officers: bool = True
    include_filings: bool = False


# Routes
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render main search page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/search")
async def api_search(
    q: str = Query(..., description="Search query"),
    companies: bool = Query(True, description="Search Companies House"),
    vehicles: bool = Query(True, description="Search MOT History"),
    legal: bool = Query(True, description="Search BAILII"),
    contracts: bool = Query(True, description="Search Contracts Finder"),
    max_results: int = Query(20, ge=1, le=100, description="Max results per source"),
    correlate: bool = Query(True, description="Find correlations"),
):
    """Search across all data sources."""
    # Build data sources
    sources = DataSources.NONE
    if companies:
        sources |= DataSources.COMPANIES_HOUSE
    if vehicles:
        sources |= DataSources.MOT_HISTORY
    if legal:
        sources |= DataSources.BAILII
    if contracts:
        sources |= DataSources.CONTRACTS_FINDER

    if sources == DataSources.NONE:
        raise HTTPException(status_code=400, detail="At least one data source must be enabled")

    options = SearchOptions(
        sources=sources,
        max_results_per_source=max_results,
    )

    searcher = get_search()
    result = await searcher.search(q, options)

    # Build response
    response = {
        "query": result.query,
        "timestamp": result.timestamp.isoformat(),
        "total_results": result.total_results,
        "companies": [json.loads(json.dumps(c.model_dump(), default=json_serializer)) for c in result.companies],
        "officers": [json.loads(json.dumps(o.model_dump(), default=json_serializer)) for o in result.officers],
        "vehicles": [json.loads(json.dumps(v.model_dump(), default=json_serializer)) for v in result.vehicles],
        "legal_cases": [json.loads(json.dumps(l.model_dump(), default=json_serializer)) for l in result.legal_cases],
        "contracts": [json.loads(json.dumps(c.model_dump(), default=json_serializer)) for c in result.contracts],
        "errors": result.errors,
        "correlations": [],
    }

    # Add correlations
    if correlate and result.has_results:
        correlator = EntityCorrelator()
        profile = correlator.build_profile(
            name=q,
            companies=result.companies,
            officers=result.officers,
            legal_cases=result.legal_cases,
            contracts=result.contracts,
            vehicles=result.vehicles,
        )
        response["correlations"] = [
            {
                "source_type": link.source_entity.entity_type.value,
                "target_type": link.target_entity.entity_type.value,
                "link_type": link.link_type,
                "confidence": link.confidence,
                "evidence": link.evidence,
            }
            for link in profile.links
        ]

    return JSONResponse(content=response)


@app.get("/api/company/{company_number}")
async def api_company(
    company_number: str,
    include_officers: bool = Query(True),
    include_filings: bool = Query(False),
):
    """Get detailed company information."""
    searcher = get_search()
    ch_client = searcher._get_companies_house()

    try:
        company = await ch_client.get_company(company_number)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Company not found: {str(e)}")

    response = json.loads(json.dumps(company.model_dump(), default=json_serializer))

    if include_officers:
        officers = await ch_client.get_company_officers(company_number)
        response["officers"] = [
            json.loads(json.dumps(o.model_dump(), default=json_serializer))
            for o in officers
        ]

    if include_filings:
        filings = await ch_client.get_company_filing_history(company_number, items_per_page=20)
        response["filings"] = filings

    return JSONResponse(content=response)


@app.get("/api/vehicle/{registration}")
async def api_vehicle(registration: str):
    """Get vehicle MOT history."""
    searcher = get_search()
    mot_client = searcher._get_mot_history()

    vehicles = await mot_client.get_vehicle_mot_history(registration)

    if not vehicles:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    return JSONResponse(
        content=json.loads(json.dumps(vehicles[0].model_dump(), default=json_serializer))
    )


@app.get("/api/legal")
async def api_legal(
    q: str = Query(..., description="Search query"),
    court: Optional[str] = Query(None, description="Court filter"),
    max_results: int = Query(20, ge=1, le=100),
):
    """Search BAILII legal records."""
    searcher = get_search()
    bailii = searcher._get_bailii()

    cases = await bailii.search(q, court=court, max_results=max_results)

    return JSONResponse(
        content={
            "query": q,
            "court": court,
            "total": len(cases),
            "cases": [
                json.loads(json.dumps(c.model_dump(), default=json_serializer))
                for c in cases
            ],
        }
    )


@app.get("/api/contracts")
async def api_contracts(
    q: Optional[str] = Query(None, description="Keyword search"),
    buyer: Optional[str] = Query(None, description="Buyer name"),
    supplier: Optional[str] = Query(None, description="Supplier name"),
    status: Optional[str] = Query(None, description="Status filter"),
    max_results: int = Query(20, ge=1, le=100),
):
    """Search Contracts Finder."""
    searcher = get_search()
    cf_client = searcher._get_contracts_finder()

    contracts = await cf_client.search_contracts(
        query=q,
        buyer_name=buyer,
        supplier_name=supplier,
        status=status,
        page_size=max_results,
    )

    return JSONResponse(
        content={
            "query": q,
            "buyer": buyer,
            "supplier": supplier,
            "status": status,
            "total": len(contracts),
            "contracts": [
                json.loads(json.dumps(c.model_dump(), default=json_serializer))
                for c in contracts
            ],
        }
    )


@app.get("/api/export")
async def api_export(
    q: str = Query(..., description="Search query"),
    format: str = Query("json", description="Export format: json, csv, markdown, html"),
):
    """Export search results."""
    # Perform search
    searcher = get_search()
    result = await searcher.search(q)

    # Export
    exporter = Exporter()
    try:
        export_format = ExportFormat(format.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid format: {format}")

    output = exporter.export_search_result(result, export_format)

    # Set content type
    content_types = {
        ExportFormat.JSON: "application/json",
        ExportFormat.CSV: "text/csv",
        ExportFormat.MARKDOWN: "text/markdown",
        ExportFormat.HTML: "text/html",
    }

    return JSONResponse(
        content={"format": format, "content": output},
        media_type=content_types.get(export_format, "text/plain"),
    )


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "version": "0.1.0"}


def run_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """Run the web server."""
    import uvicorn

    uvicorn.run(
        "uk_osint_nexus.web.server:app",
        host=host,
        port=port,
        reload=reload,
    )


if __name__ == "__main__":
    run_server()
