"""Placeholder substitution for prompt templates.

Templates are full of literal JSON/shell braces, so str.format() is unusable.
Substitution is a SINGLE pass over the template: substituted content is never
re-scanned, so a JD or LLM-drafted persona that itself contains "{jd}" or
"{conversation}" cannot pull other fields into itself.
"""
import re

_PLACEHOLDER = re.compile(r"\{(\w+)\}")


def render(template, **kwargs):
    return _PLACEHOLDER.sub(
        lambda m: str(kwargs[m.group(1)]) if m.group(1) in kwargs else m.group(0),
        template)
