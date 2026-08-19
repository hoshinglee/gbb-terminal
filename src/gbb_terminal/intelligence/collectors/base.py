from __future__ import annotations

from abc import ABC, abstractmethod

from ..collection_models import CollectorDiscovery, DiscoveredEvidenceDocument, IntelligenceRefreshRequest
from ..models import CompanyIdentity


class EvidenceCollector(ABC):
    name = "Evidence Collector"

    @abstractmethod
    def discover(self, company: CompanyIdentity, request: IntelligenceRefreshRequest) -> CollectorDiscovery:
        raise NotImplementedError

    @abstractmethod
    def download(self, company: CompanyIdentity, document: DiscoveredEvidenceDocument) -> bytes:
        raise NotImplementedError
