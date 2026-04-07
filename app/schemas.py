"""
Shared Pydantic models — the typed data contracts passed between agents.

Agent 1 (Extractor)  -> BriefExtraction
Agent 2 (Weakness)   -> list[WeaknessReport]
Agent 3 (Counter)    -> list[Counterargument]
Agent 4 (Synthesizer)-> StrategyReport
"""

from typing import List, Optional
from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# Agent 1 — Extractor output
# ──────────────────────────────────────────────

class Party(BaseModel):
    name: str
    role: str = Field(description="plaintiff, defendant, appellant, appellee, petitioner, respondent, etc.")


class Claim(BaseModel):
    claim_id: int
    text: str = Field(description="The core assertion being made")
    legal_basis: str = Field(description="Statute, precedent, or doctrine cited in support")
    supporting_facts: List[str] = Field(default_factory=list)


class KeyDate(BaseModel):
    description: str = Field(description="What the date refers to, e.g. 'Response deadline', 'Hearing date', 'Filing date'")
    date: str = Field(description="The date as written in the document")
    urgency: str = Field(description="past_due, urgent, upcoming, or informational")


class ContactInfo(BaseModel):
    name: str
    role: str = Field(description="Filing attorney, Clerk of Court, Opposing counsel, Judge, etc.")
    organization: str = ""
    phone: str = ""
    address: str = ""


class BriefExtraction(BaseModel):
    summary: str = Field(description="2-3 sentence plain-English overview of what this document is and what it contains")
    document_type: str = Field(description="motion, notice, complaint, brief, order, fine, subpoena, opinion, etc.")
    action_required: bool = Field(description="True if the document requires the recipient to take action (respond, appear, pay, etc.)")
    action_description: str = Field(default="", description="What specific action is needed, if any")
    key_dates: List[KeyDate] = Field(default_factory=list, description="All deadlines, hearing dates, and important dates found in the document")
    contacts: List[ContactInfo] = Field(default_factory=list, description="Attorneys, clerks, courts, and other contacts found in the document")
    parties: List[Party]
    claims: List[Claim]
    facts: List[str] = Field(description="Key factual allegations from the brief")
    relief_sought: str
    jurisdiction: str
    case_type: str = Field(description="civil, criminal, administrative, etc.")
    procedural_posture: str = Field(description="e.g. motion for summary judgment, appeal from trial court")


# ──────────────────────────────────────────────
# Shared — case citation used by Agents 2 & 3
# ──────────────────────────────────────────────

class CaseCitation(BaseModel):
    title: str
    court: str = ""
    date: str = ""
    relevance: str = Field(description="One-line explanation of why this case matters")


# ──────────────────────────────────────────────
# Agent 2 — Weakness Analyzer output
# ──────────────────────────────────────────────

class WeaknessReport(BaseModel):
    claim_id: int
    weakness_score: float = Field(ge=0.0, le=1.0, description="0.0 = strong, 1.0 = very weak")
    supporting_cases: List[CaseCitation] = Field(default_factory=list)
    contradicting_cases: List[CaseCitation] = Field(default_factory=list)
    reasoning: str


# ──────────────────────────────────────────────
# Agent 3 — Counterargument Predictor output
# ──────────────────────────────────────────────

class Counterargument(BaseModel):
    claim_id: int
    predicted_rebuttal: str
    grounding_cases: List[CaseCitation] = Field(default_factory=list)
    severity: str = Field(description="minor, moderate, or critical")
    suggested_preemption: str = Field(description="How to address this counterargument proactively")


# ──────────────────────────────────────────────
# Agent 4 — Synthesizer output
# ──────────────────────────────────────────────

class StrategyAction(BaseModel):
    priority: int = Field(description="1 = highest priority")
    action: str
    rationale: str
    confidence: float = Field(ge=0.0, le=1.0)
    related_claims: List[int] = Field(default_factory=list)


class StrategyReport(BaseModel):
    overall_assessment: str = Field(description="Case strength rating: 'strong', 'moderate', or 'weak' — this judges the STRENGTH OF THE CASE, not the quality of the analysis")
    actions: List[StrategyAction]
    key_risks: List[str]
    recommended_focus_areas: List[str]
