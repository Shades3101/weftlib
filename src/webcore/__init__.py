"""webcore — web access as pure logic.

This package performs **no I/O**. It builds request descriptions and parses
response payloads; the caller executes them with whatever HTTP client it
already has.

That is not an aesthetic preference. JARVIS tools may only reach the network
through ``ctx.http``, the egress-policed client its Tool Runtime supplies, and
are forbidden from importing an HTTP client or opening a socket. A library that
fetched anything itself could not be imported there at all. The same rule makes
the package trivially portable: it has no opinion about sync vs async, about
your HTTP client, cache, or framework.

The one deliberate exception is :mod:`webcore.safety`, which resolves DNS —
that *is* the SSRF check. It is a pure function returning a verdict, exposed so
a transport can consult it before it connects.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
