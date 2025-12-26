"""
Critique middleware for the research agent.

This middleware manages quality critique during document generation.
"""

import logging
import re
from typing import Any
from uuid import UUID

from schemas.models import CritiqueIssue

logger = logging.getLogger(__name__)


class CritiqueMiddleware:
    """
    Middleware for managing document critique.

    This middleware:
    - Tracks quality issues found during review
    - Validates citation coverage
    - Identifies weak claims and contradictions
    - Tracks issue resolution
    """

    def __init__(self):
        """Initialize the critique middleware."""
        self._run_id: UUID | None = None
        self._issues: list[CritiqueIssue] = []
        self._resolved_count: int = 0
        self._revision_count: int = 0

    def set_run(self, run_id: UUID) -> None:
        """
        Set the current run ID for critique context.

        Args:
            run_id: Current run ID
        """
        self._run_id = run_id

    def add_issue(
        self,
        issue_type: str,
        description: str,
        location: str | None = None,
        severity: str = "warning",
        suggestion: str | None = None,
    ) -> CritiqueIssue:
        """
        Add a critique issue.

        Args:
            issue_type: Type of issue (missing_citation, weak_claim, etc.)
            description: Description of the issue
            location: Location in document (section/line)
            severity: Issue severity (info, warning, error)
            suggestion: Suggested fix

        Returns:
            Created CritiqueIssue
        """
        issue = CritiqueIssue(
            issue_type=issue_type,
            description=description,
            location=location,
            severity=severity,
            suggestion=suggestion,
            resolved=False,
        )
        self._issues.append(issue)
        logger.debug(f"Critique issue added: {issue_type} - {description[:50]}")
        return issue

    def resolve_issue(self, issue: CritiqueIssue) -> None:
        """
        Mark an issue as resolved.

        Args:
            issue: The issue to resolve
        """
        issue.resolved = True
        self._resolved_count += 1

    def analyze_document(self, content: str) -> list[CritiqueIssue]:
        """
        Analyze a document for common issues.

        This performs automated checks for:
        - Missing citations on factual claims
        - Unresolved citation placeholders
        - Numerical claims without sources
        - Unsupported strong statements

        Args:
            content: Document content to analyze

        Returns:
            List of issues found
        """
        issues = []

        # Check for unresolved placeholders
        placeholders = re.findall(r'\[cite:[a-f0-9-]+\]', content)
        for placeholder in placeholders:
            issues.append(CritiqueIssue(
                issue_type="unresolved_placeholder",
                description=f"Unresolved citation placeholder: {placeholder}",
                severity="error",
                suggestion="Resolve all [cite:...] placeholders before finalizing",
            ))

        # Check for numerical claims without citations
        sentences = re.split(r'[.!?]\s+', content)
        for i, sentence in enumerate(sentences):
            # Check for numbers/statistics
            has_numbers = bool(re.search(
                r'\d+%|\$\d+|\d+\s*(million|billion|thousand|percent)',
                sentence,
                re.IGNORECASE
            ))
            has_citation = bool(re.search(r'\[\d+\]', sentence))
            has_assumption = bool(re.search(r'\[ASSUMPTION:', sentence))

            if has_numbers and not (has_citation or has_assumption):
                issues.append(CritiqueIssue(
                    issue_type="uncited_statistic",
                    description=f"Numerical claim without citation: '{sentence[:60]}...'",
                    location=f"Sentence {i + 1}",
                    severity="warning",
                    suggestion="Add citation or mark as [ASSUMPTION: reason]",
                ))

            # Check for strong claims without support
            strong_patterns = [
                r'\b(always|never|all|none|every|definitely|certainly|proves?)\b',
                r'\b(best|worst|only|most important|critical)\b',
            ]
            for pattern in strong_patterns:
                if re.search(pattern, sentence, re.IGNORECASE):
                    if not (has_citation or has_assumption):
                        issues.append(CritiqueIssue(
                            issue_type="strong_claim",
                            description=f"Strong claim without evidence: '{sentence[:60]}...'",
                            location=f"Sentence {i + 1}",
                            severity="info",
                            suggestion="Consider softening language or adding supporting evidence",
                        ))
                    break

        # Add issues to tracking
        for issue in issues:
            self._issues.append(issue)

        return issues

    def check_citation_coverage(self, content: str, target: float = 80.0) -> dict[str, Any]:
        """
        Check if citation coverage meets target.

        Args:
            content: Document content
            target: Target coverage percentage

        Returns:
            Coverage report
        """
        sentences = re.split(r'[.!?]\s+', content)
        total = len(sentences)

        cited = sum(1 for s in sentences if re.search(r'\[\d+\]', s))
        assumptions = sum(1 for s in sentences if re.search(r'\[ASSUMPTION:', s))

        coverage = (cited + assumptions) / total * 100 if total > 0 else 0
        meets_target = coverage >= target

        if not meets_target:
            self.add_issue(
                issue_type="low_coverage",
                description=f"Citation coverage ({coverage:.1f}%) below target ({target}%)",
                severity="warning",
                suggestion=f"Add {int((target - coverage) / 100 * total)} more citations",
            )

        return {
            "total_sentences": total,
            "cited": cited,
            "assumptions": assumptions,
            "coverage_percent": round(coverage, 1),
            "target_percent": target,
            "meets_target": meets_target,
        }

    def check_contradictions(self, claims: list[dict]) -> list[CritiqueIssue]:
        """
        Check for potential contradictions between claims.

        Args:
            claims: List of claim dicts with 'text' and 'source' keys

        Returns:
            List of potential contradictions
        """
        contradictions = []

        # Simple heuristic: look for opposing claims
        # In practice, this would use an LLM for semantic analysis
        opposites = [
            ("increase", "decrease"),
            ("higher", "lower"),
            ("more", "less"),
            ("grow", "shrink"),
            ("positive", "negative"),
            ("success", "failure"),
        ]

        for i, claim1 in enumerate(claims):
            for j, claim2 in enumerate(claims[i + 1:], i + 1):
                text1 = claim1.get("text", "").lower()
                text2 = claim2.get("text", "").lower()

                for word1, word2 in opposites:
                    if (word1 in text1 and word2 in text2) or (word2 in text1 and word1 in text2):
                        issue = CritiqueIssue(
                            issue_type="potential_contradiction",
                            description=f"Potential contradiction between claims",
                            location=f"Claims {i + 1} and {j + 1}",
                            severity="warning",
                            suggestion="Review these claims for consistency",
                        )
                        contradictions.append(issue)
                        self._issues.append(issue)
                        break

        return contradictions

    def get_unresolved_issues(self) -> list[CritiqueIssue]:
        """
        Get all unresolved issues.

        Returns:
            List of unresolved CritiqueIssue objects
        """
        return [i for i in self._issues if not i.resolved]

    def get_issues_by_type(self, issue_type: str) -> list[CritiqueIssue]:
        """
        Get issues of a specific type.

        Args:
            issue_type: Type to filter by

        Returns:
            Filtered list of issues
        """
        return [i for i in self._issues if i.issue_type == issue_type]

    def get_issues_by_severity(self, severity: str) -> list[CritiqueIssue]:
        """
        Get issues of a specific severity.

        Args:
            severity: Severity to filter by

        Returns:
            Filtered list of issues
        """
        return [i for i in self._issues if i.severity == severity]

    def increment_revision(self) -> int:
        """
        Increment the revision counter.

        Returns:
            New revision count
        """
        self._revision_count += 1
        return self._revision_count

    def get_stats(self) -> dict[str, Any]:
        """
        Get critique statistics.

        Returns:
            Dictionary with critique stats
        """
        by_type = {}
        by_severity = {}

        for issue in self._issues:
            by_type[issue.issue_type] = by_type.get(issue.issue_type, 0) + 1
            by_severity[issue.severity] = by_severity.get(issue.severity, 0) + 1

        return {
            "total_issues": len(self._issues),
            "resolved_issues": self._resolved_count,
            "unresolved_issues": len(self.get_unresolved_issues()),
            "revision_count": self._revision_count,
            "issues_by_type": by_type,
            "issues_by_severity": by_severity,
        }

    def generate_report(self) -> str:
        """
        Generate a critique report.

        Returns:
            Formatted report string
        """
        stats = self.get_stats()
        unresolved = self.get_unresolved_issues()

        lines = [
            "## Critique Report",
            "",
            f"**Total Issues:** {stats['total_issues']}",
            f"**Resolved:** {stats['resolved_issues']}",
            f"**Unresolved:** {stats['unresolved_issues']}",
            f"**Revisions:** {stats['revision_count']}",
            "",
        ]

        if unresolved:
            lines.append("### Unresolved Issues")
            lines.append("")

            # Group by severity
            for severity in ["error", "warning", "info"]:
                severity_issues = [i for i in unresolved if i.severity == severity]
                if severity_issues:
                    icon = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(severity, "•")
                    lines.append(f"#### {icon} {severity.title()} ({len(severity_issues)})")
                    lines.append("")
                    for issue in severity_issues:
                        lines.append(f"- **{issue.issue_type}**: {issue.description}")
                        if issue.suggestion:
                            lines.append(f"  - *Suggestion:* {issue.suggestion}")
                    lines.append("")
        else:
            lines.append("✅ **All issues resolved!**")

        return "\n".join(lines)

    def reset(self) -> None:
        """Reset critique tracking for a new document."""
        self._issues = []
        self._resolved_count = 0
        self._revision_count = 0
        self._run_id = None


def create_critique_middleware() -> CritiqueMiddleware:
    """
    Factory function to create critique middleware.

    Returns:
        CritiqueMiddleware instance
    """
    return CritiqueMiddleware()
