"""Guards that must run before a request leaves the process.

SSRF checking and URL normalization. Extracted from ClayHome's
``packages/core/net.py`` and ``packages/core/urls.py``.
"""
