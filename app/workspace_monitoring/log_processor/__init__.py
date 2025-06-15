"""
Log Processor Module

This module provides various log processors for analyzing Docker Compose logs.
"""

from .processors import DummyLogProcessor, AdvancedLogProcessor

__all__ = ['DummyLogProcessor', 'AdvancedLogProcessor']