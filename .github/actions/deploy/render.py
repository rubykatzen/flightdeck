#!/usr/bin/env python3
"""Pure-Python equivalent of `envsubst` for rendering config templates on
the runner (values are already known there post-decryption; no need to
push plaintext to the host just to shell out to envsubst there).

Matches real envsubst's actual behavior: only `$VAR`/`${VAR}` shell-identifier
references are substituted, missing variables become an empty string, and
anything that isn't a valid identifier reference (including bash-only
`${VAR:-default}` fallback syntax) is left untouched - envsubst doesn't
support that syntax either.
"""
import re

VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)")


def render_template(text, values):
    def substitute(match):
        name = match.group(1) or match.group(2)
        return values.get(name, "")

    return VAR_RE.sub(substitute, text)
