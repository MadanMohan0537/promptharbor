"""Dependency-free prompt release primitives."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from difflib import unified_diff
import hashlib
import json
from typing import Any

ALL_DEPENDENCIES = ("prompt", "model", "retrieval", "tools")

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

@dataclass(frozen=True)
class Bundle:
    prompt: str
    model: dict[str, Any]
    retrieval: dict[str, Any]
    tools: list[dict[str, Any]]
    dependency_scope: tuple[str, ...] = ALL_DEPENDENCIES

    def __post_init__(self) -> None:
        bad = set(self.dependency_scope) - set(ALL_DEPENDENCIES)
        if bad or not self.dependency_scope:
            raise ValueError(f"invalid dependency scope: {sorted(bad)}")

    def manifest(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.dependency_scope}

    @property
    def digest(self) -> str:
        raw = json.dumps(self.manifest(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()

@dataclass(frozen=True)
class Evidence:
    bundle_digest: str
    suite: str
    score: float
    cases: int

    def validates(self, bundle: Bundle, minimum: float) -> bool:
        return self.bundle_digest == bundle.digest and self.cases > 0 and self.score >= minimum

@dataclass(frozen=True)
class Sample:
    route_key: str
    version: str
    quality: float

@dataclass
class Version:
    number: str
    bundle: Bundle
    author: str
    rationale: str
    evidence: Evidence | None = None
    approvals: set[str] = field(default_factory=set)

class Registry:
    def __init__(self) -> None:
        self.versions: dict[str, Version] = {}
        self.audit: list[dict[str, Any]] = []

    def register(self, number: str, bundle: Bundle, author: str, rationale: str) -> Version:
        if number in self.versions or not rationale.strip():
            raise ValueError("version must be unique and rationale non-empty")
        parts = number.split(".")
        if len(parts) != 3 or not all(x.isdigit() for x in parts):
            raise ValueError("version must use numeric semantic versioning")
        item = Version(number, bundle, author, rationale)
        self.versions[number] = item
        self._log("registered", number, author, digest=bundle.digest)
        return item

    def attach_evidence(self, number: str, evidence: Evidence) -> None:
        self.versions[number].evidence = evidence
        self._log("evidence_attached", number, "system", score=evidence.score)

    def approve(self, number: str, reviewer: str) -> None:
        item = self.versions[number]
        if reviewer == item.author:
            raise ValueError("author cannot approve a customer-facing release")
        item.approvals.add(reviewer)
        self._log("approved", number, reviewer)

    def diff(self, old: str, new: str) -> str:
        a = json.dumps(asdict(self.versions[old].bundle), indent=2, sort_keys=True).splitlines()
        b = json.dumps(asdict(self.versions[new].bundle), indent=2, sort_keys=True).splitlines()
        return "\n".join(unified_diff(a, b, fromfile=old, tofile=new, lineterm=""))

    def _log(self, event: str, version: str, actor: str, **details: Any) -> None:
        self.audit.append({"at": _now(), "event": event, "version": version, "actor": actor, **details})

class ReleaseManager:
    def __init__(self, registry: Registry, minimum_score: float = .8) -> None:
        self.registry = registry
        self.minimum_score = minimum_score
        self.stable: str | None = None
        self.candidate: str | None = None
        self.percent = 0

    def promote(self, version: str, percent: int = 10) -> None:
        item = self.registry.versions[version]
        if not item.approvals:
            raise ValueError("reviewer approval required")
        if item.evidence is None or not item.evidence.validates(item.bundle, self.minimum_score):
            raise ValueError("current passing evaluation evidence required")
        if not 1 <= percent <= 100:
            raise ValueError("canary percent must be 1..100")
        self.candidate, self.percent = version, percent
        self.registry._log("canary_started", version, "system", percent=percent)

    def route(self, key: str) -> str:
        if not self.stable:
            raise ValueError("stable version is not configured")
        bucket = int(hashlib.sha256(key.encode()).hexdigest()[:8], 16) % 100
        return self.candidate if self.candidate and bucket < self.percent else self.stable

    def observe(self, samples: list[Sample], max_drop: float = .05) -> bool:
        if not self.candidate or not self.stable:
            return False
        candidate = [s.quality for s in samples if s.version == self.candidate]
        stable = [s.quality for s in samples if s.version == self.stable]
        if not candidate or not stable:
            return False
        drop = sum(stable)/len(stable) - sum(candidate)/len(candidate)
        if drop > max_drop:
            failed = self.candidate
            self.candidate, self.percent = None, 0
            self.registry._log("auto_rollback", failed, "monitor", quality_drop=round(drop, 4))
            return True
        return False
