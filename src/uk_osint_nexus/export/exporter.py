"""Export search results to various formats."""

import csv
import json
from datetime import date, datetime
from enum import Enum
from io import StringIO
from pathlib import Path
from typing import Any, Optional, Union

from ..core.correlator import EntityLink, EntityProfile
from ..core.search import UnifiedSearchResult
from ..models.entities import Company, Contract, LegalCase, Officer, Vehicle


class ExportFormat(str, Enum):
    """Supported export formats."""

    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"
    HTML = "html"


class Exporter:
    """Export OSINT data to various formats."""

    def __init__(self):
        pass

    def _serialize_value(self, value: Any) -> Any:
        """Serialize a value for export."""
        if isinstance(value, (date, datetime)):
            return value.isoformat()
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if isinstance(value, list):
            return [self._serialize_value(v) for v in value]
        if isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}
        return value

    def export_search_result(
        self,
        result: UnifiedSearchResult,
        format: ExportFormat = ExportFormat.JSON,
        output_path: Optional[Path] = None,
    ) -> str:
        """Export a unified search result.

        Args:
            result: The search result to export
            format: Export format
            output_path: Optional path to save the file

        Returns:
            Formatted string output
        """
        if format == ExportFormat.JSON:
            output = self._to_json(result)
        elif format == ExportFormat.CSV:
            output = self._to_csv(result)
        elif format == ExportFormat.MARKDOWN:
            output = self._to_markdown(result)
        elif format == ExportFormat.HTML:
            output = self._to_html(result)
        else:
            raise ValueError(f"Unsupported format: {format}")

        if output_path:
            output_path.write_text(output, encoding="utf-8")

        return output

    def export_profile(
        self,
        profile: EntityProfile,
        format: ExportFormat = ExportFormat.JSON,
        output_path: Optional[Path] = None,
    ) -> str:
        """Export an entity profile.

        Args:
            profile: The entity profile to export
            format: Export format
            output_path: Optional path to save the file

        Returns:
            Formatted string output
        """
        if format == ExportFormat.JSON:
            output = self._profile_to_json(profile)
        elif format == ExportFormat.MARKDOWN:
            output = self._profile_to_markdown(profile)
        elif format == ExportFormat.HTML:
            output = self._profile_to_html(profile)
        else:
            raise ValueError(f"Unsupported format for profiles: {format}")

        if output_path:
            output_path.write_text(output, encoding="utf-8")

        return output

    def _to_json(self, result: UnifiedSearchResult) -> str:
        """Convert search result to JSON."""
        data = {
            "query": result.query,
            "timestamp": result.timestamp.isoformat(),
            "total_results": result.total_results,
            "companies": [self._serialize_value(c.model_dump()) for c in result.companies],
            "officers": [self._serialize_value(o.model_dump()) for o in result.officers],
            "vehicles": [self._serialize_value(v.model_dump()) for v in result.vehicles],
            "legal_cases": [self._serialize_value(l.model_dump()) for l in result.legal_cases],
            "contracts": [self._serialize_value(c.model_dump()) for c in result.contracts],
            "errors": result.errors,
        }
        return json.dumps(data, indent=2, default=str)

    def _to_csv(self, result: UnifiedSearchResult) -> str:
        """Convert search result to CSV (flattened)."""
        output = StringIO()

        # Companies
        if result.companies:
            output.write("=== COMPANIES ===\n")
            writer = csv.writer(output)
            writer.writerow([
                "company_number", "company_name", "status", "type",
                "date_of_creation", "sic_codes", "address"
            ])
            for c in result.companies:
                writer.writerow([
                    c.company_number,
                    c.company_name,
                    c.company_status,
                    c.company_type,
                    c.date_of_creation,
                    ";".join(c.sic_codes),
                    str(c.registered_office_address) if c.registered_office_address else "",
                ])
            output.write("\n")

        # Officers
        if result.officers:
            output.write("=== OFFICERS ===\n")
            writer = csv.writer(output)
            writer.writerow([
                "name", "role", "company_name", "company_number",
                "appointed_on", "resigned_on", "nationality"
            ])
            for o in result.officers:
                writer.writerow([
                    o.name,
                    o.role,
                    o.company_name,
                    o.company_number,
                    o.appointed_on,
                    o.resigned_on,
                    o.nationality,
                ])
            output.write("\n")

        # Vehicles
        if result.vehicles:
            output.write("=== VEHICLES ===\n")
            writer = csv.writer(output)
            writer.writerow([
                "registration", "make", "model", "colour",
                "fuel_type", "year", "mot_status", "mot_expiry"
            ])
            for v in result.vehicles:
                writer.writerow([
                    v.registration_number,
                    v.make,
                    v.model,
                    v.colour,
                    v.fuel_type,
                    v.year_of_manufacture,
                    v.mot_status,
                    v.mot_expiry_date,
                ])
            output.write("\n")

        # Legal Cases
        if result.legal_cases:
            output.write("=== LEGAL CASES ===\n")
            writer = csv.writer(output)
            writer.writerow([
                "citation", "case_name", "court", "date", "url"
            ])
            for l in result.legal_cases:
                writer.writerow([
                    l.neutral_citation,
                    l.case_name,
                    l.court,
                    l.date_judgment,
                    l.full_text_url,
                ])
            output.write("\n")

        # Contracts
        if result.contracts:
            output.write("=== CONTRACTS ===\n")
            writer = csv.writer(output)
            writer.writerow([
                "notice_id", "title", "buyer", "supplier",
                "value", "status", "published_date"
            ])
            for c in result.contracts:
                writer.writerow([
                    c.notice_id,
                    c.title,
                    c.buyer_name,
                    c.supplier_name,
                    c.awarded_value or c.value_high,
                    c.status,
                    c.published_date,
                ])

        return output.getvalue()

    def _to_markdown(self, result: UnifiedSearchResult) -> str:
        """Convert search result to Markdown."""
        lines = [
            f"# OSINT Search Report: {result.query}",
            f"",
            f"**Generated:** {result.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"**Total Results:** {result.total_results}",
            f"",
        ]

        # Companies
        if result.companies:
            lines.extend([
                "## Companies",
                "",
                "| Number | Name | Status | Type | Created |",
                "|--------|------|--------|------|---------|",
            ])
            for c in result.companies:
                lines.append(
                    f"| {c.company_number} | {c.company_name} | {c.company_status or '-'} | "
                    f"{c.company_type or '-'} | {c.date_of_creation or '-'} |"
                )
            lines.append("")

        # Officers
        if result.officers:
            lines.extend([
                "## Officers/Directors",
                "",
                "| Name | Role | Company | Appointed | Status |",
                "|------|------|---------|-----------|--------|",
            ])
            for o in result.officers:
                status = "Active" if o.is_active else "Resigned"
                lines.append(
                    f"| {o.name} | {o.role} | {o.company_name or '-'} | "
                    f"{o.appointed_on or '-'} | {status} |"
                )
            lines.append("")

        # Vehicles
        if result.vehicles:
            lines.extend([
                "## Vehicles",
                "",
                "| Registration | Make | Model | Colour | MOT Status | MOT Expiry |",
                "|--------------|------|-------|--------|------------|------------|",
            ])
            for v in result.vehicles:
                lines.append(
                    f"| {v.registration_number} | {v.make or '-'} | {v.model or '-'} | "
                    f"{v.colour or '-'} | {v.mot_status or '-'} | {v.mot_expiry_date or '-'} |"
                )
            lines.append("")

        # Legal Cases
        if result.legal_cases:
            lines.extend([
                "## Legal Cases",
                "",
                "| Citation | Case Name | Court | Date |",
                "|----------|-----------|-------|------|",
            ])
            for l in result.legal_cases:
                name = l.case_name[:50] + "..." if len(l.case_name) > 50 else l.case_name
                lines.append(
                    f"| {l.neutral_citation or '-'} | {name} | "
                    f"{l.court or '-'} | {l.date_judgment or '-'} |"
                )
            lines.append("")

        # Contracts
        if result.contracts:
            lines.extend([
                "## Government Contracts",
                "",
                "| Title | Buyer | Supplier | Value | Status |",
                "|-------|-------|----------|-------|--------|",
            ])
            for c in result.contracts:
                title = c.title[:40] + "..." if len(c.title) > 40 else c.title
                value = f"£{c.awarded_value:,.0f}" if c.awarded_value else "-"
                lines.append(
                    f"| {title} | {c.buyer_name or '-'} | {c.supplier_name or '-'} | "
                    f"{value} | {c.status or '-'} |"
                )
            lines.append("")

        # Errors
        if result.errors:
            lines.extend([
                "## Errors",
                "",
            ])
            for source, error in result.errors.items():
                lines.append(f"- **{source}**: {error}")
            lines.append("")

        return "\n".join(lines)

    def _to_html(self, result: UnifiedSearchResult) -> str:
        """Convert search result to HTML report."""
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>OSINT Report: {result.query}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #1a365d; border-bottom: 3px solid #3182ce; padding-bottom: 10px; }}
        h2 {{ color: #2d3748; margin-top: 30px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
        th {{ background: #3182ce; color: white; padding: 12px; text-align: left; }}
        td {{ padding: 10px; border-bottom: 1px solid #e2e8f0; }}
        tr:hover {{ background: #f7fafc; }}
        .meta {{ color: #718096; margin-bottom: 20px; }}
        .status-active {{ color: #38a169; font-weight: bold; }}
        .status-inactive {{ color: #e53e3e; }}
        .error {{ background: #fff5f5; border-left: 4px solid #e53e3e; padding: 10px; margin: 10px 0; }}
        .summary {{ background: #ebf8ff; padding: 15px; border-radius: 5px; margin-bottom: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>OSINT Search Report</h1>
        <div class="meta">
            <strong>Query:</strong> {result.query}<br>
            <strong>Generated:</strong> {result.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}
        </div>
        <div class="summary">
            <strong>Total Results:</strong> {result.total_results}
        </div>
"""

        # Companies
        if result.companies:
            html += """
        <h2>Companies</h2>
        <table>
            <tr><th>Number</th><th>Name</th><th>Status</th><th>Type</th><th>Created</th></tr>
"""
            for c in result.companies:
                status_class = "status-active" if c.is_active else "status-inactive"
                html += f"""
            <tr>
                <td>{c.company_number}</td>
                <td>{c.company_name}</td>
                <td class="{status_class}">{c.company_status or '-'}</td>
                <td>{c.company_type or '-'}</td>
                <td>{c.date_of_creation or '-'}</td>
            </tr>
"""
            html += "        </table>\n"

        # Officers
        if result.officers:
            html += """
        <h2>Officers/Directors</h2>
        <table>
            <tr><th>Name</th><th>Role</th><th>Company</th><th>Appointed</th><th>Status</th></tr>
"""
            for o in result.officers:
                status = "Active" if o.is_active else "Resigned"
                status_class = "status-active" if o.is_active else "status-inactive"
                html += f"""
            <tr>
                <td>{o.name}</td>
                <td>{o.role}</td>
                <td>{o.company_name or '-'}</td>
                <td>{o.appointed_on or '-'}</td>
                <td class="{status_class}">{status}</td>
            </tr>
"""
            html += "        </table>\n"

        # Vehicles
        if result.vehicles:
            html += """
        <h2>Vehicles</h2>
        <table>
            <tr><th>Registration</th><th>Make</th><th>Model</th><th>Colour</th><th>MOT Status</th><th>MOT Expiry</th></tr>
"""
            for v in result.vehicles:
                mot_class = "status-active" if v.mot_status == "PASSED" else "status-inactive"
                html += f"""
            <tr>
                <td>{v.registration_number}</td>
                <td>{v.make or '-'}</td>
                <td>{v.model or '-'}</td>
                <td>{v.colour or '-'}</td>
                <td class="{mot_class}">{v.mot_status or '-'}</td>
                <td>{v.mot_expiry_date or '-'}</td>
            </tr>
"""
            html += "        </table>\n"

        # Legal Cases
        if result.legal_cases:
            html += """
        <h2>Legal Cases</h2>
        <table>
            <tr><th>Citation</th><th>Case Name</th><th>Court</th><th>Date</th><th>Link</th></tr>
"""
            for l in result.legal_cases:
                name = l.case_name[:60] + "..." if len(l.case_name) > 60 else l.case_name
                link = f'<a href="{l.full_text_url}" target="_blank">View</a>' if l.full_text_url else "-"
                html += f"""
            <tr>
                <td>{l.neutral_citation or '-'}</td>
                <td>{name}</td>
                <td>{l.court or '-'}</td>
                <td>{l.date_judgment or '-'}</td>
                <td>{link}</td>
            </tr>
"""
            html += "        </table>\n"

        # Contracts
        if result.contracts:
            html += """
        <h2>Government Contracts</h2>
        <table>
            <tr><th>Title</th><th>Buyer</th><th>Supplier</th><th>Value</th><th>Status</th></tr>
"""
            for c in result.contracts:
                title = c.title[:50] + "..." if len(c.title) > 50 else c.title
                value = f"£{c.awarded_value:,.0f}" if c.awarded_value else "-"
                html += f"""
            <tr>
                <td>{title}</td>
                <td>{c.buyer_name or '-'}</td>
                <td>{c.supplier_name or '-'}</td>
                <td>{value}</td>
                <td>{c.status or '-'}</td>
            </tr>
"""
            html += "        </table>\n"

        # Errors
        if result.errors:
            html += "        <h2>Errors</h2>\n"
            for source, error in result.errors.items():
                html += f'        <div class="error"><strong>{source}:</strong> {error}</div>\n'

        html += """
    </div>
</body>
</html>
"""
        return html

    def _profile_to_json(self, profile: EntityProfile) -> str:
        """Convert entity profile to JSON."""
        data = {
            "primary_name": profile.primary_name,
            "entity_type": profile.entity_type.value,
            "sources": profile.sources,
            "total_records": profile.total_records,
            "created_at": profile.created_at.isoformat(),
            "companies": [self._serialize_value(c.model_dump()) for c in profile.companies],
            "officers": [self._serialize_value(o.model_dump()) for o in profile.officers],
            "legal_cases": [self._serialize_value(l.model_dump()) for l in profile.legal_cases],
            "contracts": [self._serialize_value(c.model_dump()) for c in profile.contracts],
            "vehicles": [self._serialize_value(v.model_dump()) for v in profile.vehicles],
            "addresses": [self._serialize_value(a.model_dump()) for a in profile.addresses],
            "links": [
                {
                    "source_type": l.source_entity.entity_type.value,
                    "target_type": l.target_entity.entity_type.value,
                    "link_type": l.link_type,
                    "confidence": l.confidence,
                    "evidence": l.evidence,
                }
                for l in profile.links
            ],
        }
        return json.dumps(data, indent=2, default=str)

    def _profile_to_markdown(self, profile: EntityProfile) -> str:
        """Convert entity profile to Markdown."""
        lines = [
            f"# Entity Profile: {profile.primary_name}",
            f"",
            f"**Type:** {profile.entity_type.value}",
            f"**Sources:** {', '.join(profile.sources)}",
            f"**Total Records:** {profile.total_records}",
            f"**Generated:** {profile.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"",
        ]

        # Addresses
        if profile.addresses:
            lines.extend(["## Known Addresses", ""])
            for addr in profile.addresses:
                lines.append(f"- {addr}")
            lines.append("")

        # Links/Correlations
        if profile.links:
            lines.extend(["## Cross-Source Correlations", ""])
            for link in profile.links:
                confidence_pct = int(link.confidence * 100)
                lines.append(
                    f"- **{confidence_pct}%** {link.source_entity.entity_type.value} → "
                    f"{link.target_entity.entity_type.value} ({link.link_type})"
                )
                for ev in link.evidence:
                    lines.append(f"  - {ev}")
            lines.append("")

        return "\n".join(lines)

    def _profile_to_html(self, profile: EntityProfile) -> str:
        """Convert entity profile to HTML."""
        # Similar structure to _to_html but for profiles
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Entity Profile: {profile.primary_name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; }}
        h1 {{ color: #1a365d; }}
        .meta {{ color: #718096; }}
        .link {{ background: #f7fafc; padding: 10px; margin: 5px 0; border-radius: 5px; }}
        .confidence {{ display: inline-block; padding: 2px 8px; border-radius: 3px; color: white; }}
        .high {{ background: #38a169; }}
        .medium {{ background: #d69e2e; }}
        .low {{ background: #e53e3e; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Entity Profile: {profile.primary_name}</h1>
        <p class="meta">
            <strong>Type:</strong> {profile.entity_type.value} |
            <strong>Sources:</strong> {', '.join(profile.sources)} |
            <strong>Records:</strong> {profile.total_records}
        </p>
        <h2>Correlations</h2>
        {"".join(f'''
        <div class="link">
            <span class="confidence {'high' if l.confidence >= 0.8 else 'medium' if l.confidence >= 0.6 else 'low'}">{int(l.confidence*100)}%</span>
            {l.source_entity.entity_type.value} → {l.target_entity.entity_type.value} ({l.link_type})
        </div>
        ''' for l in profile.links)}
    </div>
</body>
</html>
"""
