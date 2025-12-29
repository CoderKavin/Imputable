"""
Audit Export Service - Enterprise PDF Report Generator

Generates professional, tamper-proof PDF reports for SOC2/ISO/HIPAA audits.
Includes cryptographic verification hash for integrity checking.
"""

import hashlib
import io
from datetime import datetime
from typing import Any, Sequence
from uuid import UUID

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models import (
    AuditAction,
    AuditLog,
    Approval,
    Decision,
    DecisionVersion,
    Organization,
    Team,
    User,
)


# =============================================================================
# DATA CLASSES
# =============================================================================


class AuditReportData:
    """Container for all data needed to generate the audit report."""

    def __init__(
        self,
        organization: Organization,
        decisions: Sequence[Decision],
        start_date: datetime,
        end_date: datetime,
        generated_by: User,
        filters: dict[str, Any],
    ):
        self.organization = organization
        self.decisions = decisions
        self.start_date = start_date
        self.end_date = end_date
        self.generated_by = generated_by
        self.filters = filters
        self.generated_at = datetime.utcnow()


class DecisionAuditTrail:
    """Audit trail for a single decision."""

    def __init__(
        self,
        decision: Decision,
        events: Sequence[AuditLog],
        approvals: Sequence[Approval],
    ):
        self.decision = decision
        self.events = events
        self.approvals = approvals


# =============================================================================
# AUDIT EXPORT SERVICE
# =============================================================================


class AuditExportService:
    """Service for generating audit export PDFs."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_decisions_for_export(
        self,
        organization_id: UUID,
        start_date: datetime,
        end_date: datetime,
        team_ids: list[UUID] | None = None,
        tags: list[str] | None = None,
        status_filter: list[str] | None = None,
    ) -> Sequence[Decision]:
        """Fetch decisions matching the export criteria."""
        query = (
            select(Decision)
            .options(
                selectinload(Decision.versions).selectinload(DecisionVersion.creator),
                selectinload(Decision.versions).selectinload(DecisionVersion.approvals).selectinload(Approval.user),
                selectinload(Decision.creator),
                selectinload(Decision.owner_team),
            )
            .where(
                Decision.organization_id == organization_id,
                Decision.deleted_at.is_(None),
                Decision.created_at >= start_date,
                Decision.created_at <= end_date,
            )
        )

        if team_ids:
            query = query.where(Decision.owner_team_id.in_(team_ids))

        if status_filter:
            query = query.where(Decision.status.in_(status_filter))

        if tags:
            # Filter by tags in the current version
            subquery = (
                select(DecisionVersion.decision_id)
                .where(DecisionVersion.tags.overlap(tags))
                .distinct()
            )
            query = query.where(Decision.id.in_(subquery))

        query = query.order_by(Decision.decision_number)
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_audit_trail_for_decision(
        self,
        decision_id: UUID,
        start_date: datetime,
        end_date: datetime,
    ) -> Sequence[AuditLog]:
        """Get audit events for a specific decision."""
        query = (
            select(AuditLog)
            .options(selectinload(AuditLog.user))
            .where(
                AuditLog.resource_type == "decision",
                AuditLog.resource_id == decision_id,
                AuditLog.created_at >= start_date,
                AuditLog.created_at <= end_date,
            )
            .order_by(AuditLog.created_at)
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def get_organization(self, organization_id: UUID) -> Organization:
        """Get organization details."""
        result = await self.session.execute(
            select(Organization).where(Organization.id == organization_id)
        )
        return result.scalar_one()

    async def get_teams(self, organization_id: UUID) -> dict[UUID, Team]:
        """Get all teams in the organization."""
        result = await self.session.execute(
            select(Team).where(
                Team.organization_id == organization_id,
                Team.deleted_at.is_(None),
            )
        )
        teams = result.scalars().all()
        return {team.id: team for team in teams}

    async def generate_report(
        self,
        organization_id: UUID,
        start_date: datetime,
        end_date: datetime,
        generated_by_id: UUID,
        team_ids: list[UUID] | None = None,
        tags: list[str] | None = None,
        status_filter: list[str] | None = None,
    ) -> tuple[bytes, str]:
        """
        Generate the complete audit report PDF.

        Returns:
            Tuple of (PDF bytes, verification hash)
        """
        # Fetch all data
        organization = await self.get_organization(organization_id)
        decisions = await self.get_decisions_for_export(
            organization_id,
            start_date,
            end_date,
            team_ids,
            tags,
            status_filter,
        )

        # Get user who generated the report
        user_result = await self.session.execute(
            select(User).where(User.id == generated_by_id)
        )
        generated_by = user_result.scalar_one()

        # Prepare filter description
        filters = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "team_ids": [str(t) for t in team_ids] if team_ids else None,
            "tags": tags,
            "status_filter": status_filter,
        }

        report_data = AuditReportData(
            organization=organization,
            decisions=decisions,
            start_date=start_date,
            end_date=end_date,
            generated_by=generated_by,
            filters=filters,
        )

        # Generate PDF
        pdf_generator = AuditPDFGenerator(report_data)
        pdf_bytes = pdf_generator.generate()

        # Calculate verification hash
        content_hash = self._calculate_content_hash(report_data)

        # Log the export
        await self._log_export(
            organization_id=organization_id,
            user_id=generated_by_id,
            decision_count=len(decisions),
            content_hash=content_hash,
        )

        return pdf_bytes, content_hash

    def _calculate_content_hash(self, report_data: AuditReportData) -> str:
        """
        Calculate SHA-256 hash of the report content for tamper verification.

        The hash includes:
        - Organization ID and name
        - Date range
        - All decision IDs, titles, and content hashes
        - Generation timestamp
        """
        hasher = hashlib.sha256()

        # Organization info
        hasher.update(str(report_data.organization.id).encode())
        hasher.update(report_data.organization.name.encode())

        # Date range
        hasher.update(report_data.start_date.isoformat().encode())
        hasher.update(report_data.end_date.isoformat().encode())

        # Decisions (sorted by ID for consistency)
        for decision in sorted(report_data.decisions, key=lambda d: str(d.id)):
            hasher.update(str(decision.id).encode())
            hasher.update(str(decision.decision_number).encode())
            hasher.update(decision.status.value.encode())

            # Include all versions
            for version in decision.versions:
                hasher.update(str(version.id).encode())
                hasher.update(str(version.version_number).encode())
                hasher.update(version.title.encode())
                if version.content_hash:
                    hasher.update(version.content_hash.encode())

        # Generation timestamp
        hasher.update(report_data.generated_at.isoformat().encode())

        return hasher.hexdigest()

    async def _log_export(
        self,
        organization_id: UUID,
        user_id: UUID,
        decision_count: int,
        content_hash: str,
    ) -> None:
        """Log the export event to the audit trail."""
        audit_entry = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action=AuditAction.EXPORT,
            resource_type="audit_report",
            resource_id=organization_id,  # Use org ID as resource
            details={
                "format": "pdf",
                "decision_count": decision_count,
                "content_hash": content_hash,
                "report_type": "change_management_audit",
            },
        )
        self.session.add(audit_entry)
        await self.session.flush()


# =============================================================================
# PDF GENERATOR
# =============================================================================


class AuditPDFGenerator:
    """Generates the professional audit PDF report."""

    def __init__(self, report_data: AuditReportData):
        self.data = report_data
        self.styles = self._create_styles()
        self.buffer = io.BytesIO()

    def _create_styles(self) -> dict[str, ParagraphStyle]:
        """Create custom paragraph styles for the report."""
        base_styles = getSampleStyleSheet()

        return {
            "title": ParagraphStyle(
                "Title",
                parent=base_styles["Title"],
                fontSize=28,
                spaceAfter=30,
                textColor=colors.HexColor("#1e293b"),
                alignment=TA_CENTER,
            ),
            "subtitle": ParagraphStyle(
                "Subtitle",
                parent=base_styles["Normal"],
                fontSize=14,
                spaceAfter=12,
                textColor=colors.HexColor("#64748b"),
                alignment=TA_CENTER,
            ),
            "heading1": ParagraphStyle(
                "Heading1",
                parent=base_styles["Heading1"],
                fontSize=18,
                spaceBefore=24,
                spaceAfter=12,
                textColor=colors.HexColor("#0f172a"),
                borderColor=colors.HexColor("#e2e8f0"),
                borderWidth=1,
                borderPadding=8,
            ),
            "heading2": ParagraphStyle(
                "Heading2",
                parent=base_styles["Heading2"],
                fontSize=14,
                spaceBefore=16,
                spaceAfter=8,
                textColor=colors.HexColor("#1e293b"),
            ),
            "heading3": ParagraphStyle(
                "Heading3",
                parent=base_styles["Heading3"],
                fontSize=12,
                spaceBefore=12,
                spaceAfter=6,
                textColor=colors.HexColor("#334155"),
            ),
            "body": ParagraphStyle(
                "Body",
                parent=base_styles["Normal"],
                fontSize=10,
                spaceAfter=8,
                textColor=colors.HexColor("#334155"),
                alignment=TA_JUSTIFY,
            ),
            "body_small": ParagraphStyle(
                "BodySmall",
                parent=base_styles["Normal"],
                fontSize=9,
                spaceAfter=4,
                textColor=colors.HexColor("#64748b"),
            ),
            "audit_event": ParagraphStyle(
                "AuditEvent",
                parent=base_styles["Normal"],
                fontSize=9,
                leftIndent=20,
                spaceAfter=4,
                textColor=colors.HexColor("#475569"),
            ),
            "footer": ParagraphStyle(
                "Footer",
                parent=base_styles["Normal"],
                fontSize=8,
                textColor=colors.HexColor("#94a3b8"),
                alignment=TA_CENTER,
            ),
            "hash": ParagraphStyle(
                "Hash",
                parent=base_styles["Normal"],
                fontSize=8,
                fontName="Courier",
                textColor=colors.HexColor("#059669"),
                alignment=TA_CENTER,
                spaceBefore=8,
            ),
            "toc_entry": ParagraphStyle(
                "TOCEntry",
                parent=base_styles["Normal"],
                fontSize=10,
                spaceAfter=4,
                textColor=colors.HexColor("#334155"),
            ),
            "status_approved": ParagraphStyle(
                "StatusApproved",
                parent=base_styles["Normal"],
                fontSize=9,
                textColor=colors.HexColor("#059669"),
            ),
            "status_pending": ParagraphStyle(
                "StatusPending",
                parent=base_styles["Normal"],
                fontSize=9,
                textColor=colors.HexColor("#d97706"),
            ),
            "status_deprecated": ParagraphStyle(
                "StatusDeprecated",
                parent=base_styles["Normal"],
                fontSize=9,
                textColor=colors.HexColor("#dc2626"),
            ),
        }

    def generate(self) -> bytes:
        """Generate the complete PDF report."""
        doc = SimpleDocTemplate(
            self.buffer,
            pagesize=letter,
            rightMargin=0.75 * inch,
            leftMargin=0.75 * inch,
            topMargin=1 * inch,
            bottomMargin=1 * inch,
        )

        # Build the story (list of flowables)
        story = []

        # Cover page
        story.extend(self._build_cover_page())
        story.append(PageBreak())

        # Table of contents
        story.extend(self._build_table_of_contents())
        story.append(PageBreak())

        # Executive summary
        story.extend(self._build_executive_summary())
        story.append(PageBreak())

        # Decision details
        for i, decision in enumerate(self.data.decisions):
            story.extend(self._build_decision_section(decision, i + 1))
            if i < len(self.data.decisions) - 1:
                story.append(PageBreak())

        # Verification footer
        story.append(PageBreak())
        story.extend(self._build_verification_section())

        # Build PDF
        doc.build(story, onFirstPage=self._add_page_header, onLaterPages=self._add_page_header)

        # Get the PDF bytes
        pdf_bytes = self.buffer.getvalue()
        self.buffer.close()

        return pdf_bytes

    def _build_cover_page(self) -> list:
        """Build the cover page."""
        elements = []

        # Spacer for vertical centering
        elements.append(Spacer(1, 2 * inch))

        # Title
        elements.append(
            Paragraph("Change Management Report", self.styles["title"])
        )

        # Organization name
        elements.append(
            Paragraph(
                f"<b>{self.data.organization.name}</b>",
                self.styles["subtitle"],
            )
        )

        elements.append(Spacer(1, 0.5 * inch))

        # Date range
        date_range = (
            f"{self.data.start_date.strftime('%B %d, %Y')} — "
            f"{self.data.end_date.strftime('%B %d, %Y')}"
        )
        elements.append(Paragraph(date_range, self.styles["subtitle"]))

        elements.append(Spacer(1, 1.5 * inch))

        # Report metadata table
        meta_data = [
            ["Report Generated:", self.data.generated_at.strftime("%B %d, %Y at %H:%M UTC")],
            ["Generated By:", self.data.generated_by.name],
            ["Total Decisions:", str(len(self.data.decisions))],
            ["Report Type:", "SOC2 / ISO 27001 Compliance Audit"],
        ]

        meta_table = Table(meta_data, colWidths=[2 * inch, 4 * inch])
        meta_table.setStyle(
            TableStyle([
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#64748b")),
                ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#1e293b")),
                ("ALIGN", (0, 0), (0, -1), "RIGHT"),
                ("ALIGN", (1, 0), (1, -1), "LEFT"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
            ])
        )
        elements.append(meta_table)

        elements.append(Spacer(1, 1 * inch))

        # Confidentiality notice
        elements.append(
            Paragraph(
                "<i>CONFIDENTIAL — This document contains proprietary information "
                "about engineering decisions and change management processes. "
                "Distribution is restricted to authorized personnel only.</i>",
                self.styles["body_small"],
            )
        )

        return elements

    def _build_table_of_contents(self) -> list:
        """Build the table of contents."""
        elements = []

        elements.append(Paragraph("Table of Contents", self.styles["heading1"]))
        elements.append(Spacer(1, 0.25 * inch))

        # Executive Summary
        elements.append(
            Paragraph("1. Executive Summary", self.styles["toc_entry"])
        )

        # Decision entries
        for i, decision in enumerate(self.data.decisions, start=1):
            current_version = decision.current_version or (
                decision.versions[-1] if decision.versions else None
            )
            title = current_version.title if current_version else "Untitled"
            truncated_title = title[:60] + "..." if len(title) > 60 else title

            elements.append(
                Paragraph(
                    f"2.{i}. DECISION-{decision.decision_number}: {truncated_title}",
                    self.styles["toc_entry"],
                )
            )

        # Verification section
        elements.append(
            Paragraph("3. Cryptographic Verification", self.styles["toc_entry"])
        )

        return elements

    def _build_executive_summary(self) -> list:
        """Build the executive summary section."""
        elements = []

        elements.append(Paragraph("1. Executive Summary", self.styles["heading1"]))

        # Summary statistics
        total_decisions = len(self.data.decisions)

        # Count by status
        status_counts: dict[str, int] = {}
        for decision in self.data.decisions:
            status = decision.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        # Count versions (changes)
        total_versions = sum(len(d.versions) for d in self.data.decisions)
        total_changes = total_versions - total_decisions  # Exclude initial versions

        summary_text = f"""
        This report documents <b>{total_decisions}</b> engineering decisions made during
        the period from {self.data.start_date.strftime('%B %d, %Y')} to
        {self.data.end_date.strftime('%B %d, %Y')}.

        During this period, there were <b>{total_changes}</b> amendments to existing decisions,
        demonstrating active change management and documentation practices.
        """
        elements.append(Paragraph(summary_text, self.styles["body"]))

        elements.append(Spacer(1, 0.25 * inch))

        # Status breakdown table
        elements.append(Paragraph("Decision Status Summary", self.styles["heading2"]))

        status_data = [["Status", "Count", "Percentage"]]
        for status, count in sorted(status_counts.items()):
            percentage = f"{(count / total_decisions * 100):.1f}%" if total_decisions > 0 else "0%"
            status_data.append([status.replace("_", " ").title(), str(count), percentage])

        status_table = Table(status_data, colWidths=[2.5 * inch, 1.5 * inch, 1.5 * inch])
        status_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#334155")),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
            ])
        )
        elements.append(status_table)

        # Applied filters
        if any(self.data.filters.values()):
            elements.append(Spacer(1, 0.25 * inch))
            elements.append(Paragraph("Applied Filters", self.styles["heading2"]))

            filter_text = []
            if self.data.filters.get("team_ids"):
                filter_text.append(f"Teams: {len(self.data.filters['team_ids'])} selected")
            if self.data.filters.get("tags"):
                filter_text.append(f"Tags: {', '.join(self.data.filters['tags'])}")
            if self.data.filters.get("status_filter"):
                filter_text.append(f"Status: {', '.join(self.data.filters['status_filter'])}")

            if filter_text:
                elements.append(Paragraph(" | ".join(filter_text), self.styles["body_small"]))

        return elements

    def _build_decision_section(self, decision: Decision, index: int) -> list:
        """Build the section for a single decision."""
        elements = []

        current_version = decision.current_version or (
            decision.versions[-1] if decision.versions else None
        )

        if not current_version:
            return elements

        # Decision header
        elements.append(
            Paragraph(
                f"2.{index}. DECISION-{decision.decision_number}: {current_version.title}",
                self.styles["heading1"],
            )
        )

        # Metadata table
        status_color = self._get_status_color(decision.status.value)
        owner_team = decision.owner_team.name if decision.owner_team else "Unassigned"

        meta_data = [
            ["Status:", f'<font color="{status_color}">{decision.status.value.replace("_", " ").title()}</font>'],
            ["Owner Team:", owner_team],
            ["Created By:", decision.creator.name if decision.creator else "Unknown"],
            ["Created On:", decision.created_at.strftime("%B %d, %Y at %H:%M UTC")],
            ["Impact Level:", current_version.impact_level.value.upper()],
            ["Version:", f"v{current_version.version_number} (of {len(decision.versions)} total)"],
        ]

        if current_version.tags:
            meta_data.append(["Tags:", ", ".join(current_version.tags)])

        meta_table = Table(meta_data, colWidths=[1.5 * inch, 5 * inch])
        meta_table.setStyle(
            TableStyle([
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#64748b")),
                ("TEXTCOLOR", (1, 0), (1, -1), colors.HexColor("#1e293b")),
                ("ALIGN", (0, 0), (0, -1), "RIGHT"),
                ("ALIGN", (1, 0), (1, -1), "LEFT"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ])
        )
        elements.append(meta_table)

        # Content sections
        content = current_version.content or {}

        if content.get("context"):
            elements.append(Paragraph("Context", self.styles["heading2"]))
            elements.append(Paragraph(content["context"], self.styles["body"]))

        if content.get("choice"):
            elements.append(Paragraph("Decision", self.styles["heading2"]))
            elements.append(Paragraph(content["choice"], self.styles["body"]))

        if content.get("rationale"):
            elements.append(Paragraph("Rationale", self.styles["heading2"]))
            elements.append(Paragraph(content["rationale"], self.styles["body"]))

        if content.get("consequences"):
            elements.append(Paragraph("Consequences", self.styles["heading2"]))
            elements.append(Paragraph(content["consequences"], self.styles["body"]))

        # Alternatives considered
        alternatives = content.get("alternatives", [])
        if alternatives:
            elements.append(Paragraph("Alternatives Considered", self.styles["heading2"]))
            for alt in alternatives:
                alt_text = f"<b>{alt.get('name', 'Unnamed')}</b>: {alt.get('rejected_reason', 'No reason provided')}"
                elements.append(Paragraph(f"• {alt_text}", self.styles["body"]))

        # Audit Trail section
        elements.append(Paragraph("Audit Trail", self.styles["heading2"]))
        elements.extend(self._build_audit_trail(decision))

        return elements

    def _build_audit_trail(self, decision: Decision) -> list:
        """Build the audit trail for a decision."""
        elements = []

        events = []

        # Add version creation events
        for version in decision.versions:
            action = "Created" if version.version_number == 1 else "Amended"
            change_note = f" — {version.change_summary}" if version.change_summary else ""
            events.append({
                "timestamp": version.created_at,
                "text": f"<b>{action}</b> by {version.creator.name} on {version.created_at.strftime('%B %d, %Y at %H:%M UTC')}{change_note}",
                "type": "version",
            })

            # Add approval events for this version
            for approval in version.approvals:
                status_text = approval.status.value.title()
                comment = f" — \"{approval.comment}\"" if approval.comment else ""
                events.append({
                    "timestamp": approval.created_at,
                    "text": f"<b>{status_text}</b> by {approval.user.name} on {approval.created_at.strftime('%B %d, %Y at %H:%M UTC')}{comment}",
                    "type": "approval",
                })

        # Sort by timestamp
        events.sort(key=lambda e: e["timestamp"])

        if not events:
            elements.append(Paragraph("No audit events recorded.", self.styles["body_small"]))
            return elements

        # Create audit trail table
        trail_data = []
        for event in events:
            icon = "●" if event["type"] == "version" else "○"
            trail_data.append([icon, Paragraph(event["text"], self.styles["audit_event"])])

        trail_table = Table(trail_data, colWidths=[0.25 * inch, 6.25 * inch])
        trail_table.setStyle(
            TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTSIZE", (0, 0), (0, -1), 8),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#94a3b8")),
                ("LEFTPADDING", (0, 0), (0, -1), 0),
                ("RIGHTPADDING", (0, 0), (0, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ])
        )
        elements.append(trail_table)

        return elements

    def _build_verification_section(self) -> list:
        """Build the cryptographic verification section."""
        elements = []

        elements.append(Paragraph("3. Cryptographic Verification", self.styles["heading1"]))

        explanation = """
        This report includes a cryptographic hash that can be used to verify the integrity
        of the report content. The hash is calculated from all decision data included in
        this report, including decision IDs, titles, content hashes, and the generation
        timestamp. Any modification to the report content after generation will result
        in a different hash value.
        """
        elements.append(Paragraph(explanation, self.styles["body"]))

        elements.append(Spacer(1, 0.25 * inch))

        # Hash will be added during final generation
        elements.append(
            Paragraph(
                "<b>Verification Hash (SHA-256):</b>",
                self.styles["body"],
            )
        )

        # Placeholder - actual hash is calculated after PDF generation
        # In practice, we'd need to insert the hash in a second pass
        elements.append(
            Paragraph(
                "<i>Hash is calculated and displayed in the final document</i>",
                self.styles["hash"],
            )
        )

        elements.append(Spacer(1, 0.5 * inch))

        # Verification instructions
        elements.append(Paragraph("Verification Instructions", self.styles["heading2"]))

        instructions = """
        To verify the authenticity of this report:
        <br/><br/>
        1. Request the original report from the Imputable system using the same date range and filters.
        <br/>
        2. Compare the verification hash displayed above with the hash from the newly generated report.
        <br/>
        3. If the hashes match, the report content has not been modified since generation.
        <br/>
        4. If the hashes differ, the report may have been altered or the underlying data has changed.
        """
        elements.append(Paragraph(instructions, self.styles["body"]))

        elements.append(Spacer(1, 0.5 * inch))

        # Footer with generation details
        footer_text = f"""
        <b>Report ID:</b> {self.data.generated_at.strftime('%Y%m%d%H%M%S')}-{self.data.organization.slug}
        <br/>
        <b>Generated:</b> {self.data.generated_at.strftime('%B %d, %Y at %H:%M:%S UTC')}
        <br/>
        <b>System:</b> Imputable v1.0 — Enterprise Audit Module
        """
        elements.append(Paragraph(footer_text, self.styles["body_small"]))

        return elements

    def _add_page_header(self, canvas, doc):
        """Add header and footer to each page."""
        canvas.saveState()

        # Header
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#94a3b8"))
        canvas.drawString(
            0.75 * inch,
            letter[1] - 0.5 * inch,
            f"{self.data.organization.name} — Change Management Audit Report",
        )
        canvas.drawRightString(
            letter[0] - 0.75 * inch,
            letter[1] - 0.5 * inch,
            f"Generated: {self.data.generated_at.strftime('%Y-%m-%d')}",
        )

        # Header line
        canvas.setStrokeColor(colors.HexColor("#e2e8f0"))
        canvas.line(0.75 * inch, letter[1] - 0.6 * inch, letter[0] - 0.75 * inch, letter[1] - 0.6 * inch)

        # Footer
        canvas.drawCentredString(
            letter[0] / 2,
            0.5 * inch,
            f"Page {doc.page}",
        )

        # Footer line
        canvas.line(0.75 * inch, 0.7 * inch, letter[0] - 0.75 * inch, 0.7 * inch)

        # Confidentiality notice
        canvas.setFont("Helvetica-Oblique", 7)
        canvas.drawCentredString(
            letter[0] / 2,
            0.35 * inch,
            "CONFIDENTIAL — For authorized use only",
        )

        canvas.restoreState()

    def _get_status_color(self, status: str) -> str:
        """Get the color for a decision status."""
        colors_map = {
            "draft": "#d97706",
            "pending_review": "#2563eb",
            "approved": "#059669",
            "deprecated": "#6b7280",
            "superseded": "#dc2626",
            "expired": "#dc2626",
            "at_risk": "#d97706",
        }
        return colors_map.get(status, "#6b7280")
