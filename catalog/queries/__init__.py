"""Query plugins"""
from .missing_attributes import MissingAttributesQuery, MissingAnyAttributesQuery
from .title_checks import TitlePolicyViolationsQuery
from .char_validation import ProhibitedCharsQuery
__all__ = [
    'MissingAttributesQuery',
    'MissingAnyAttributesQuery',
    'TitlePolicyViolationsQuery',
    'ProhibitedCharsQuery',
]
