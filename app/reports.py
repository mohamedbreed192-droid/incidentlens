from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Category = Literal["database", "credentials", "service", "unknown"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Explanation(StrictModel):
    text: str = Field(min_length=1, max_length=1200)
    log_lines: list[int] = Field(min_length=1, max_length=8)
    source_ids: list[str] = Field(min_length=1, max_length=3)


class Check(StrictModel):
    text: str = Field(min_length=1, max_length=600)
    source_ids: list[str] = Field(min_length=1, max_length=3)


class ProviderReport(StrictModel):
    category: Category
    explanations: list[Explanation] = Field(min_length=1, max_length=3)
    checks: list[Check] = Field(min_length=1, max_length=5)


def validate_grounding(report, category, evidence_lines, docs):
    ids = {d.id for d in docs}
    if report.category != category:
        raise ValueError("Provider changed the evidence category")
    for explanation in report.explanations:
        if not set(explanation.log_lines) <= set(evidence_lines):
            raise ValueError("Provider referenced unsupported log lines")
        if not set(explanation.source_ids) <= ids:
            raise ValueError("Provider referenced unavailable sources")
    for check in report.checks:
        if not set(check.source_ids) <= ids:
            raise ValueError("Provider referenced unavailable sources")
    return report
