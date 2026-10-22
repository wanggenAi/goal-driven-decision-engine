"""Evidence-first goal-driven decision engine."""

from .engine import ValidationError, score_document

__all__ = ["ValidationError", "score_document"]
__version__ = "0.2.0"
