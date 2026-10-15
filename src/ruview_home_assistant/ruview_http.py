# SPDX-License-Identifier: MIT
"""Bounded HTTP content decoding shared by the Python worker consumers."""

import json
import math
import zlib


def strict_json(raw):
    """Reject ambiguous keys and numbers that cannot be safely evaluated."""

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate_json_key")
            result[key] = value
        return result

    def number(raw):
        value = float(raw)
        if not math.isfinite(value):
            raise ValueError("nonfinite_json_number")
        return value

    return json.loads(
        raw, object_pairs_hook=pairs, parse_float=number, parse_constant=number
    )


def decode_http_body(raw: bytes, content_encoding: str | None, max_bytes: int) -> bytes:
    """Return exact identity/gzip bytes within both wire and decoded size limits.

    Only one complete gzip member is accepted. No trailing bytes, concatenated
    members or unbounded flush are allowed; zlib validates the member's CRC and
    size trailer before reporting EOF. Callers retain their request deadlines.
    """
    if type(max_bytes) is not int or max_bytes < 0:
        raise ValueError("invalid_body_limit")
    if len(raw) > max_bytes:
        raise ValueError("document_too_large")
    if content_encoding is None:
        encoding = "identity"
    elif isinstance(content_encoding, str):
        encoding = content_encoding.strip().lower() or "identity"
    else:
        raise ValueError("unsupported_content_encoding")
    if encoding == "identity":
        return raw
    if encoding != "gzip":
        raise ValueError("unsupported_content_encoding")

    decoder = zlib.decompressobj(16 + zlib.MAX_WBITS)
    try:
        body = decoder.decompress(raw, max_bytes + 1)
    except zlib.error:
        raise ValueError("invalid_gzip_body") from None
    if len(body) > max_bytes:
        raise ValueError("document_too_large")
    if not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
        raise ValueError("invalid_gzip_body")
    return body
