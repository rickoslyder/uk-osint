"""Core functionality for UK OSINT Nexus."""

from .search import UnifiedSearch
from .correlator import EntityCorrelator

__all__ = ["UnifiedSearch", "EntityCorrelator"]
