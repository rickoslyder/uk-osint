"""Main CLI interface for UK OSINT Nexus."""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.tree import Tree

from ..core.correlator import EntityCorrelator
from ..core.search import DataSources, SearchOptions, UnifiedSearch

app = typer.Typer(
    name="osint",
    help="UK OSINT Nexus - Unified UK Open Source Intelligence Tool",
    no_args_is_help=True,
)
console = Console()


def run_async(coro):
    """Run an async coroutine."""
    return asyncio.get_event_loop().run_until_complete(coro)


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query (name, company, registration, etc.)"),
    companies: bool = typer.Option(True, "--companies/--no-companies", help="Search Companies House"),
    vehicles: bool = typer.Option(True, "--vehicles/--no-vehicles", help="Search MOT History"),
    legal: bool = typer.Option(True, "--legal/--no-legal", help="Search BAILII legal records"),
    contracts: bool = typer.Option(True, "--contracts/--no-contracts", help="Search Contracts Finder"),
    max_results: int = typer.Option(10, "--max", "-m", help="Max results per source"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Export results to JSON file"),
    correlate: bool = typer.Option(True, "--correlate/--no-correlate", help="Find cross-source links"),
):
    """Search across all UK OSINT data sources."""
    # Build data sources flag
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
        console.print("[red]Error: At least one data source must be enabled[/red]")
        raise typer.Exit(1)

    options = SearchOptions(
        sources=sources,
        max_results_per_source=max_results,
    )

    async def do_search():
        async with UnifiedSearch() as searcher:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(f"Searching for '{query}'...", total=None)
                result = await searcher.search(query, options)
                progress.remove_task(task)

            return result

    result = run_async(do_search())

    # Display results
    console.print()
    console.print(Panel(f"[bold]Search Results for: {query}[/bold]", style="blue"))
    console.print()

    # Companies
    if result.companies:
        table = Table(title=f"Companies ({len(result.companies)})", show_header=True)
        table.add_column("Number", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("Status")
        table.add_column("Type")
        table.add_column("Created")

        for company in result.companies[:max_results]:
            status_style = "green" if company.is_active else "red"
            table.add_row(
                company.company_number,
                company.company_name,
                f"[{status_style}]{company.company_status or 'Unknown'}[/{status_style}]",
                company.company_type or "-",
                str(company.date_of_creation) if company.date_of_creation else "-",
            )
        console.print(table)
        console.print()

    # Officers
    if result.officers:
        table = Table(title=f"Officers/Directors ({len(result.officers)})", show_header=True)
        table.add_column("Name", style="green")
        table.add_column("Role")
        table.add_column("Company")
        table.add_column("Appointed")
        table.add_column("Status")

        for officer in result.officers[:max_results]:
            status = "[green]Active[/green]" if officer.is_active else "[red]Resigned[/red]"
            table.add_row(
                officer.name,
                officer.role,
                officer.company_name or "-",
                str(officer.appointed_on) if officer.appointed_on else "-",
                status,
            )
        console.print(table)
        console.print()

    # Vehicles
    if result.vehicles:
        table = Table(title=f"Vehicles ({len(result.vehicles)})", show_header=True)
        table.add_column("Registration", style="cyan")
        table.add_column("Make", style="green")
        table.add_column("Model")
        table.add_column("Colour")
        table.add_column("MOT Status")
        table.add_column("MOT Expiry")

        for vehicle in result.vehicles:
            mot_style = "green" if vehicle.mot_status == "PASSED" else "red"
            table.add_row(
                vehicle.registration_number,
                vehicle.make or "-",
                vehicle.model or "-",
                vehicle.colour or "-",
                f"[{mot_style}]{vehicle.mot_status or 'Unknown'}[/{mot_style}]",
                str(vehicle.mot_expiry_date) if vehicle.mot_expiry_date else "-",
            )
        console.print(table)
        console.print()

    # Legal Cases
    if result.legal_cases:
        table = Table(title=f"Legal Cases ({len(result.legal_cases)})", show_header=True)
        table.add_column("Citation", style="cyan")
        table.add_column("Case Name", style="green", max_width=40)
        table.add_column("Court")
        table.add_column("Date")

        for case in result.legal_cases[:max_results]:
            table.add_row(
                case.neutral_citation or "-",
                case.case_name[:40] + "..." if len(case.case_name) > 40 else case.case_name,
                case.court or "-",
                str(case.date_judgment) if case.date_judgment else "-",
            )
        console.print(table)
        console.print()

    # Contracts
    if result.contracts:
        table = Table(title=f"Government Contracts ({len(result.contracts)})", show_header=True)
        table.add_column("ID", style="cyan", max_width=15)
        table.add_column("Title", style="green", max_width=35)
        table.add_column("Buyer")
        table.add_column("Value")
        table.add_column("Status")

        for contract in result.contracts[:max_results]:
            value = "-"
            if contract.awarded_value:
                value = f"£{contract.awarded_value:,.0f}"
            elif contract.value_high:
                value = f"£{contract.value_high:,.0f}"

            table.add_row(
                contract.notice_id[:15] if contract.notice_id else "-",
                contract.title[:35] + "..." if len(contract.title) > 35 else contract.title,
                (contract.buyer_name[:20] + "...") if contract.buyer_name and len(contract.buyer_name) > 20 else (contract.buyer_name or "-"),
                value,
                contract.status or "-",
            )
        console.print(table)
        console.print()

    # Errors
    if result.errors:
        console.print("[yellow]Errors during search:[/yellow]")
        for source, error in result.errors.items():
            console.print(f"  [red]{source}[/red]: {error}")
        console.print()

    # Correlations
    if correlate and result.has_results:
        correlator = EntityCorrelator()
        profile = correlator.build_profile(
            name=query,
            companies=result.companies,
            officers=result.officers,
            legal_cases=result.legal_cases,
            contracts=result.contracts,
            vehicles=result.vehicles,
        )

        if profile.links:
            console.print(Panel("[bold]Cross-Source Correlations[/bold]", style="magenta"))
            for link in profile.links[:10]:
                confidence_pct = int(link.confidence * 100)
                style = "green" if confidence_pct >= 80 else "yellow" if confidence_pct >= 60 else "red"
                console.print(
                    f"  [{style}]{confidence_pct}%[/{style}] "
                    f"{link.source_entity.entity_type.value} → "
                    f"{link.target_entity.entity_type.value} "
                    f"([dim]{link.link_type}[/dim])"
                )
                for ev in link.evidence[:2]:
                    console.print(f"       [dim]{ev}[/dim]")
            console.print()

    # Summary
    console.print(f"[bold]Total Results: {result.total_results}[/bold]")

    # Export
    if output:
        export_data = {
            "query": query,
            "timestamp": datetime.utcnow().isoformat(),
            "total_results": result.total_results,
            "companies": [c.model_dump() for c in result.companies],
            "officers": [o.model_dump() for o in result.officers],
            "vehicles": [v.model_dump() for v in result.vehicles],
            "legal_cases": [l.model_dump() for l in result.legal_cases],
            "contracts": [c.model_dump() for c in result.contracts],
            "errors": result.errors,
        }

        def json_serializer(obj):
            if hasattr(obj, "isoformat"):
                return obj.isoformat()
            return str(obj)

        output.write_text(json.dumps(export_data, indent=2, default=json_serializer))
        console.print(f"[green]Results exported to: {output}[/green]")


@app.command()
def company(
    query: str = typer.Argument(..., help="Company name or number"),
    officers: bool = typer.Option(True, "--officers/--no-officers", help="Include officers"),
    filings: bool = typer.Option(False, "--filings", "-f", help="Include recent filings"),
    contracts_flag: bool = typer.Option(True, "--contracts/--no-contracts", help="Search for contracts"),
):
    """Search for a specific company."""
    async def do_search():
        async with UnifiedSearch() as searcher:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(f"Looking up company '{query}'...", total=None)

                # Check if it's a company number
                clean_query = query.upper().replace(" ", "")
                is_number = len(clean_query) <= 8 and clean_query.isalnum()

                ch_client = searcher._get_companies_house()

                if is_number:
                    try:
                        company = await ch_client.get_company(clean_query)
                        companies = [company]
                    except Exception:
                        companies = await ch_client.search_companies(query, items_per_page=5)
                else:
                    companies = await ch_client.search_companies(query, items_per_page=5)

                # Get officers for first company
                company_officers = []
                filing_history = []
                if companies and officers:
                    company_officers = await ch_client.get_company_officers(companies[0].company_number)

                if companies and filings:
                    filing_history = await ch_client.get_company_filing_history(
                        companies[0].company_number, items_per_page=10
                    )

                # Search contracts
                contract_results = []
                if contracts_flag and companies:
                    cf_client = searcher._get_contracts_finder()
                    contract_results = await cf_client.search_contracts(
                        supplier_name=companies[0].company_name,
                        page_size=10,
                    )

                progress.remove_task(task)
                return companies, company_officers, filing_history, contract_results

    companies, company_officers, filing_history, contract_results = run_async(do_search())

    if not companies:
        console.print(f"[red]No company found for: {query}[/red]")
        raise typer.Exit(1)

    company = companies[0]

    # Build display tree
    tree = Tree(f"[bold blue]{company.company_name}[/bold blue]")

    # Basic info
    info = tree.add("[bold]Company Information[/bold]")
    info.add(f"Number: [cyan]{company.company_number}[/cyan]")
    status_style = "green" if company.is_active else "red"
    info.add(f"Status: [{status_style}]{company.company_status}[/{status_style}]")
    info.add(f"Type: {company.company_type or 'Unknown'}")
    if company.date_of_creation:
        info.add(f"Incorporated: {company.date_of_creation}")
    if company.sic_codes:
        info.add(f"SIC Codes: {', '.join(company.sic_codes)}")

    # Address
    if company.registered_office_address:
        addr = tree.add("[bold]Registered Address[/bold]")
        addr.add(str(company.registered_office_address))

    # Officers
    if company_officers:
        off_tree = tree.add(f"[bold]Officers ({len(company_officers)})[/bold]")
        for off in company_officers[:10]:
            status = "[green]Active[/green]" if off.is_active else "[red]Resigned[/red]"
            off_tree.add(f"{off.name} - {off.role} {status}")

    # Filings
    if filing_history:
        fil_tree = tree.add(f"[bold]Recent Filings ({len(filing_history)})[/bold]")
        for filing in filing_history[:5]:
            fil_tree.add(f"{filing.get('date', '?')} - {filing.get('description', 'Unknown')}")

    # Contracts
    if contract_results:
        con_tree = tree.add(f"[bold]Government Contracts ({len(contract_results)})[/bold]")
        for con in contract_results[:5]:
            value = f"£{con.awarded_value:,.0f}" if con.awarded_value else "Unknown value"
            con_tree.add(f"{con.title[:50]}... - {value}")

    console.print()
    console.print(tree)
    console.print()


@app.command()
def vehicle(
    registration: str = typer.Argument(..., help="Vehicle registration number (e.g., AB12CDE)"),
):
    """Look up a vehicle by registration number."""
    async def do_search():
        async with UnifiedSearch() as searcher:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(f"Looking up vehicle '{registration}'...", total=None)
                mot_client = searcher._get_mot_history()
                vehicles = await mot_client.get_vehicle_mot_history(registration)
                progress.remove_task(task)
                return vehicles

    vehicles = run_async(do_search())

    if not vehicles:
        console.print(f"[red]No vehicle found for registration: {registration}[/red]")
        console.print("[dim]Note: MOT history is only available for vehicles that have had an MOT test[/dim]")
        raise typer.Exit(1)

    vehicle = vehicles[0]

    # Build display
    tree = Tree(f"[bold blue]{vehicle.registration_number}[/bold blue]")

    # Basic info
    info = tree.add("[bold]Vehicle Information[/bold]")
    info.add(f"Make: [green]{vehicle.make or 'Unknown'}[/green]")
    info.add(f"Model: {vehicle.model or 'Unknown'}")
    info.add(f"Colour: {vehicle.colour or 'Unknown'}")
    info.add(f"Fuel Type: {vehicle.fuel_type or 'Unknown'}")
    if vehicle.year_of_manufacture:
        info.add(f"Year: {vehicle.year_of_manufacture}")
    if vehicle.date_of_first_registration:
        info.add(f"First Registered: {vehicle.date_of_first_registration}")

    # MOT Status
    mot_style = "green" if vehicle.mot_status == "PASSED" else "red"
    mot_tree = tree.add("[bold]MOT Status[/bold]")
    mot_tree.add(f"Status: [{mot_style}]{vehicle.mot_status or 'Unknown'}[/{mot_style}]")
    if vehicle.mot_expiry_date:
        mot_tree.add(f"Expires: {vehicle.mot_expiry_date}")

    # MOT History
    if vehicle.mot_history:
        hist_tree = tree.add(f"[bold]MOT History ({len(vehicle.mot_history)} tests)[/bold]")
        for test in vehicle.mot_history[:5]:
            result = test.get("test_result", "Unknown")
            result_style = "green" if result == "PASSED" else "red"
            date_str = test.get("test_date", "Unknown date")
            odometer = test.get("odometer_value", "?")
            unit = test.get("odometer_unit", "mi")

            test_node = hist_tree.add(
                f"[{result_style}]{result}[/{result_style}] - {date_str} ({odometer} {unit})"
            )

            # Show defects
            defects = test.get("defects", [])
            for defect in defects[:3]:
                defect_type = defect.get("type", "")
                defect_text = defect.get("text", "")
                if defect_type == "DANGEROUS":
                    test_node.add(f"[red]DANGEROUS: {defect_text}[/red]")
                elif defect_type == "MAJOR":
                    test_node.add(f"[yellow]MAJOR: {defect_text}[/yellow]")
                else:
                    test_node.add(f"[dim]{defect_type}: {defect_text}[/dim]")

    console.print()
    console.print(tree)
    console.print()


@app.command()
def legal(
    query: str = typer.Argument(..., help="Search term (case name, party name, keywords)"),
    court: Optional[str] = typer.Option(None, "--court", "-c", help="Filter by court (uksc, ewca, ewhc, etc.)"),
    max_results: int = typer.Option(10, "--max", "-m", help="Maximum results"),
):
    """Search BAILII for legal cases."""
    async def do_search():
        async with UnifiedSearch() as searcher:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task(f"Searching BAILII for '{query}'...", total=None)
                bailii = searcher._get_bailii()
                cases = await bailii.search(query, court=court, max_results=max_results)
                progress.remove_task(task)
                return cases

    cases = run_async(do_search())

    if not cases:
        console.print(f"[yellow]No cases found for: {query}[/yellow]")
        raise typer.Exit(0)

    table = Table(title=f"Legal Cases for '{query}'", show_header=True)
    table.add_column("Citation", style="cyan")
    table.add_column("Case Name", style="green", max_width=50)
    table.add_column("Court")
    table.add_column("Date")
    table.add_column("URL", max_width=30)

    for case in cases:
        table.add_row(
            case.neutral_citation or "-",
            case.case_name[:50] + "..." if len(case.case_name) > 50 else case.case_name,
            case.court or "-",
            str(case.date_judgment) if case.date_judgment else "-",
            case.full_text_url[:30] + "..." if case.full_text_url and len(case.full_text_url) > 30 else (case.full_text_url or "-"),
        )

    console.print()
    console.print(table)
    console.print()
    console.print(f"[dim]Found {len(cases)} cases[/dim]")


@app.command()
def contracts(
    query: Optional[str] = typer.Argument(None, help="Search keyword"),
    buyer: Optional[str] = typer.Option(None, "--buyer", "-b", help="Filter by buyer name"),
    supplier: Optional[str] = typer.Option(None, "--supplier", "-s", help="Filter by supplier name"),
    status: Optional[str] = typer.Option(None, "--status", help="Filter by status (Open, Closed, Awarded)"),
    max_results: int = typer.Option(10, "--max", "-m", help="Maximum results"),
):
    """Search Contracts Finder for government contracts."""
    async def do_search():
        async with UnifiedSearch() as searcher:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Searching Contracts Finder...", total=None)
                cf = searcher._get_contracts_finder()
                results = await cf.search_contracts(
                    query=query,
                    buyer_name=buyer,
                    supplier_name=supplier,
                    status=status,
                    page_size=max_results,
                )
                progress.remove_task(task)
                return results

    results = run_async(do_search())

    if not results:
        console.print("[yellow]No contracts found[/yellow]")
        raise typer.Exit(0)

    table = Table(title="Government Contracts", show_header=True)
    table.add_column("Title", style="green", max_width=40)
    table.add_column("Buyer", max_width=25)
    table.add_column("Supplier", max_width=25)
    table.add_column("Value")
    table.add_column("Status")
    table.add_column("Published")

    for contract in results:
        value = "-"
        if contract.awarded_value:
            value = f"£{contract.awarded_value:,.0f}"
        elif contract.value_high:
            value = f"≤£{contract.value_high:,.0f}"

        table.add_row(
            contract.title[:40] + "..." if len(contract.title) > 40 else contract.title,
            (contract.buyer_name[:25] + "...") if contract.buyer_name and len(contract.buyer_name) > 25 else (contract.buyer_name or "-"),
            (contract.supplier_name[:25] + "...") if contract.supplier_name and len(contract.supplier_name) > 25 else (contract.supplier_name or "-"),
            value,
            contract.status or "-",
            str(contract.published_date.date()) if contract.published_date else "-",
        )

    console.print()
    console.print(table)
    console.print()
    console.print(f"[dim]Found {len(results)} contracts[/dim]")


@app.command()
def web(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host to bind to"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind to"),
    reload: bool = typer.Option(False, "--reload", "-r", help="Enable auto-reload for development"),
):
    """Start the web interface server."""
    console.print()
    console.print(Panel("[bold]UK OSINT Nexus Web Interface[/bold]", style="blue"))
    console.print()
    console.print(f"Starting server at [cyan]http://{host}:{port}[/cyan]")
    console.print("[dim]Press Ctrl+C to stop[/dim]")
    console.print()

    from ..web.server import run_server
    run_server(host=host, port=port, reload=reload)


@app.command()
def config():
    """Show current configuration and API key status."""
    from ..utils.config import get_config

    cfg = get_config()

    console.print()
    console.print(Panel("[bold]UK OSINT Nexus Configuration[/bold]", style="blue"))
    console.print()

    # API Keys
    console.print("[bold]API Keys:[/bold]")
    ch_status = "[green]Configured[/green]" if cfg.has_companies_house_key() else "[yellow]Not set[/yellow]"
    mot_status = "[green]Configured[/green]" if cfg.has_mot_history_key() else "[yellow]Not set[/yellow]"
    console.print(f"  Companies House: {ch_status}")
    console.print(f"  MOT History: {mot_status}")
    console.print()

    # Sources that don't need keys
    console.print("[bold]Free Sources (no API key needed):[/bold]")
    console.print("  [green]✓[/green] BAILII (legal records)")
    console.print("  [green]✓[/green] Contracts Finder")
    console.print()

    console.print("[bold]Paths:[/bold]")
    console.print(f"  Cache: {cfg.cache_dir}")
    console.print(f"  Database: {cfg.database_path}")
    console.print()

    console.print("[bold]To configure API keys, set environment variables:[/bold]")
    console.print("  export COMPANIES_HOUSE_API_KEY=your_key_here")
    console.print("  export MOT_HISTORY_API_KEY=your_key_here")
    console.print()
    console.print("[dim]Get a Companies House API key at: https://developer.company-information.service.gov.uk/[/dim]")
    console.print("[dim]Get a MOT History API key at: https://dvsa.github.io/mot-history-api-documentation/[/dim]")


if __name__ == "__main__":
    app()
