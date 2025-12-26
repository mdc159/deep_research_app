"""
Versioning service for document management.

This service provides:
- Document version creation
- Change log generation
- Diff computation between versions
"""

import difflib
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from schemas.config import RunConfig
from schemas.models import Document

logger = logging.getLogger(__name__)


@dataclass
class VersionDiff:
    """Represents differences between two document versions."""

    from_version: int
    to_version: int
    additions: int
    deletions: int
    modifications: int
    unified_diff: str
    summary: str


@dataclass
class ChangeEntry:
    """A single change log entry."""

    timestamp: datetime
    version: int
    change_type: str  # created, revised, critique_addressed, finalized
    description: str
    details: list[str] | None = None


class VersioningService:
    """
    Service for document versioning.

    Handles:
    - Creating new document versions
    - Computing diffs between versions
    - Generating change logs
    - Version metadata tracking
    """

    def __init__(self):
        """Initialize the versioning service."""
        self._change_history: list[ChangeEntry] = []

    def reset(self) -> None:
        """Reset versioning state for a new document."""
        self._change_history = []

    def create_version(
        self,
        run_id: UUID,
        title: str,
        markdown: str,
        config: RunConfig,
        version: int = 1,
        change_type: str = "created",
        change_description: str | None = None,
    ) -> Document:
        """
        Create a new document version.

        Args:
            run_id: Run ID
            title: Document title
            markdown: Document content
            config: Run configuration snapshot
            version: Version number
            change_type: Type of change
            change_description: Optional description

        Returns:
            New Document model
        """
        # Generate change log
        change_log = self._format_change_log(
            version=version,
            change_type=change_type,
            description=change_description or f"Version {version} {change_type}",
        )

        # Record in history
        entry = ChangeEntry(
            timestamp=datetime.utcnow(),
            version=version,
            change_type=change_type,
            description=change_description or f"Document {change_type}",
        )
        self._change_history.append(entry)

        return Document(
            id=uuid4(),
            run_id=run_id,
            version=version,
            title=title,
            markdown=markdown,
            created_at=datetime.utcnow(),
            change_log=change_log,
            config_snapshot=config,
        )

    def create_revision(
        self,
        previous: Document,
        new_markdown: str,
        change_type: str = "revised",
        change_description: str | None = None,
        changes_made: list[str] | None = None,
    ) -> Document:
        """
        Create a new revision of an existing document.

        Args:
            previous: Previous document version
            new_markdown: New content
            change_type: Type of change
            change_description: Description of changes
            changes_made: List of specific changes

        Returns:
            New Document model with incremented version
        """
        new_version = previous.version + 1

        # Compute diff for change log
        diff = self.compute_diff(previous.markdown, new_markdown)

        # Generate description if not provided
        if not change_description:
            change_description = (
                f"Revised: {diff.additions} additions, "
                f"{diff.deletions} deletions, "
                f"{diff.modifications} modifications"
            )

        # Combine previous change log with new entry
        previous_log = previous.change_log or ""
        new_entry = self._format_change_log(
            version=new_version,
            change_type=change_type,
            description=change_description,
            details=changes_made,
        )
        combined_log = previous_log + "\n" + new_entry if previous_log else new_entry

        # Record in history
        entry = ChangeEntry(
            timestamp=datetime.utcnow(),
            version=new_version,
            change_type=change_type,
            description=change_description,
            details=changes_made,
        )
        self._change_history.append(entry)

        return Document(
            id=uuid4(),
            run_id=previous.run_id,
            version=new_version,
            title=previous.title,
            markdown=new_markdown,
            created_at=datetime.utcnow(),
            change_log=combined_log,
            config_snapshot=previous.config_snapshot,
        )

    def _format_change_log(
        self,
        version: int,
        change_type: str,
        description: str,
        details: list[str] | None = None,
    ) -> str:
        """
        Format a change log entry.

        Args:
            version: Version number
            change_type: Type of change
            description: Change description
            details: Optional list of specific changes

        Returns:
            Formatted change log entry
        """
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        lines = [
            f"### Version {version}",
            f"- **Type:** {change_type}",
            f"- **Date:** {timestamp}",
            f"- **Description:** {description}",
        ]

        if details:
            lines.append("- **Changes:**")
            for detail in details:
                lines.append(f"  - {detail}")

        return "\n".join(lines)

    def compute_diff(
        self,
        old_content: str,
        new_content: str,
    ) -> VersionDiff:
        """
        Compute the difference between two versions.

        Args:
            old_content: Previous version content
            new_content: New version content

        Returns:
            VersionDiff with statistics and unified diff
        """
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        # Generate unified diff
        diff_lines = list(difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile='previous',
            tofile='current',
            lineterm='',
        ))

        # Count changes
        additions = sum(1 for line in diff_lines if line.startswith('+') and not line.startswith('+++'))
        deletions = sum(1 for line in diff_lines if line.startswith('-') and not line.startswith('---'))

        # Estimate modifications (paired add/delete in close proximity)
        modifications = min(additions, deletions)
        pure_additions = additions - modifications
        pure_deletions = deletions - modifications

        # Generate summary
        summary_parts = []
        if pure_additions:
            summary_parts.append(f"+{pure_additions} lines")
        if pure_deletions:
            summary_parts.append(f"-{pure_deletions} lines")
        if modifications:
            summary_parts.append(f"~{modifications} lines modified")

        summary = ", ".join(summary_parts) if summary_parts else "No changes"

        return VersionDiff(
            from_version=0,  # Will be set by caller
            to_version=0,
            additions=additions,
            deletions=deletions,
            modifications=modifications,
            unified_diff="".join(diff_lines),
            summary=summary,
        )

    def compute_version_diff(
        self,
        old_doc: Document,
        new_doc: Document,
    ) -> VersionDiff:
        """
        Compute diff between two document versions.

        Args:
            old_doc: Previous document version
            new_doc: New document version

        Returns:
            VersionDiff with version numbers set
        """
        diff = self.compute_diff(old_doc.markdown, new_doc.markdown)
        diff.from_version = old_doc.version
        diff.to_version = new_doc.version
        return diff

    def get_section_changes(
        self,
        old_content: str,
        new_content: str,
    ) -> dict[str, str]:
        """
        Get changes organized by section.

        Args:
            old_content: Previous content
            new_content: New content

        Returns:
            Dict mapping section names to change descriptions
        """
        changes = {}

        # Extract sections (## headings)
        section_pattern = r'^##\s+(.+)$'

        old_sections = self._extract_sections(old_content)
        new_sections = self._extract_sections(new_content)

        all_sections = set(old_sections.keys()) | set(new_sections.keys())

        for section in all_sections:
            old_text = old_sections.get(section, "")
            new_text = new_sections.get(section, "")

            if section not in old_sections:
                changes[section] = "Added"
            elif section not in new_sections:
                changes[section] = "Removed"
            elif old_text != new_text:
                diff = self.compute_diff(old_text, new_text)
                changes[section] = diff.summary
            # else: unchanged, don't include

        return changes

    def _extract_sections(self, content: str) -> dict[str, str]:
        """
        Extract sections from markdown content.

        Args:
            content: Markdown content

        Returns:
            Dict mapping section names to content
        """
        sections = {}
        current_section = "Introduction"
        current_content = []

        for line in content.split('\n'):
            if line.startswith('## '):
                # Save previous section
                if current_content:
                    sections[current_section] = '\n'.join(current_content)
                # Start new section
                current_section = line[3:].strip()
                current_content = []
            else:
                current_content.append(line)

        # Save last section
        if current_content:
            sections[current_section] = '\n'.join(current_content)

        return sections

    def generate_html_diff(
        self,
        old_content: str,
        new_content: str,
    ) -> str:
        """
        Generate an HTML diff for visual comparison.

        Args:
            old_content: Previous content
            new_content: New content

        Returns:
            HTML string with highlighted changes
        """
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()

        differ = difflib.HtmlDiff(wrapcolumn=80)
        html = differ.make_table(
            old_lines,
            new_lines,
            fromdesc='Previous Version',
            todesc='Current Version',
            context=True,
            numlines=3,
        )

        return html

    def get_change_history(self) -> list[ChangeEntry]:
        """
        Get the change history for the current session.

        Returns:
            List of ChangeEntry objects
        """
        return self._change_history.copy()

    def format_change_history(self) -> str:
        """
        Format the change history as markdown.

        Returns:
            Formatted change history
        """
        if not self._change_history:
            return "## Change History\n\nNo changes recorded."

        lines = ["## Change History", ""]

        for entry in sorted(self._change_history, key=lambda e: e.version):
            timestamp = entry.timestamp.strftime("%Y-%m-%d %H:%M")
            lines.append(f"### Version {entry.version} ({timestamp})")
            lines.append(f"- **Type:** {entry.change_type}")
            lines.append(f"- **Description:** {entry.description}")

            if entry.details:
                lines.append("- **Details:**")
                for detail in entry.details:
                    lines.append(f"  - {detail}")

            lines.append("")

        return "\n".join(lines)

    def get_stats(self) -> dict[str, Any]:
        """
        Get versioning statistics.

        Returns:
            Dictionary with stats
        """
        return {
            "versions_created": len(self._change_history),
            "change_types": list(set(e.change_type for e in self._change_history)),
        }
