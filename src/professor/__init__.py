"""
Professor - AI-Powered Code Review & Quality Oversight System

In the age of AI-assisted development, Professor ensures that quality, security,
and correctness remain paramount. Every line of code, whether written by human
or machine, deserves the highest standard of review.
"""

__version__ = "0.1.0"
__author__ = "Professor Team"

from professor.core.models import Finding, Review, Severity
from professor.core.analyzer import Analyzer

__all__ = ["Finding", "Review", "Severity", "Analyzer", "__version__"]
