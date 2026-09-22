"""The public surface, pinned.

weft is meant to be imported by projects that are not in this repository, which
makes its top-level names a contract rather than an implementation detail.
These tests fail loudly on an accidental rename or a dropped export — the kind
of change that is invisible here and breaks a consumer on upgrade.
"""

from __future__ import annotations

import importlib

import pytest

import weft

#: Every name `import weft` is expected to provide. Adding to this list is a
#: feature; removing from it or renaming an entry is a breaking change and
#: should have to be done deliberately, by editing this test.
PUBLIC_NAMES = {
    "ApiKey",
    "AsyncTransport",
    "BearerToken",
    "Cache",
    "Credential",
    "FetchMethod",
    "FetchedPage",
    "HttpRequest",
    "HttpResponse",
    "QueryKey",
    "Renderer",
    "SearchHit",
    "SearchRequest",
    "SearchResponse",
    "Transport",
    "UnsafeURLError",
    "__version__",
}

#: Submodules a consumer imports by path. Listed so that a module going missing
#: or being renamed is caught here rather than in someone else's build.
SUBMODULES = [
    "weft.extract",
    "weft.platforms",
    "weft.platforms.github",
    "weft.platforms.reader",
    "weft.platforms.rss",
    "weft.platforms.search",
    "weft.platforms.search.brave",
    "weft.platforms.search.searxng",
    "weft.platforms.youtube",
    "weft.ports",
    "weft.safety",
]


class TestTopLevel:
    def test_all_matches_the_contract(self) -> None:
        assert set(weft.__all__) == PUBLIC_NAMES

    @pytest.mark.parametrize("name", sorted(PUBLIC_NAMES))
    def test_every_advertised_name_resolves(self, name: str) -> None:
        """``__all__`` listing a name it cannot provide breaks ``from weft import *``
        and, worse, misleads anyone reading it for the API."""
        assert hasattr(weft, name), f"weft.__all__ advertises {name!r} but it is missing"

    def test_version_is_a_string(self) -> None:
        assert isinstance(weft.__version__, str)
        assert weft.__version__.count(".") >= 2


class TestSubmodules:
    @pytest.mark.parametrize("module", SUBMODULES)
    def test_importable(self, module: str) -> None:
        assert importlib.import_module(module) is not None


class TestImportCost:
    def test_top_level_import_does_not_pull_in_selectolax(self) -> None:
        """``import weft`` must stay free of the one runtime dependency.

        A caller that only builds GitHub requests should not load an HTML
        parser. Run in a subprocess because by the time this test runs, the
        rest of the suite has long since imported selectolax.
        """
        import subprocess
        import sys

        probe = "import weft, sys; print('selectolax' in sys.modules)"
        result = subprocess.run(  # noqa: S603
            [sys.executable, "-c", probe], capture_output=True, text=True, check=True
        )
        assert result.stdout.strip() == "False"


class TestNoAmbientIO:
    """The library's central claim: importing it opens no sockets.

    JARVIS forbids a tool from importing an HTTP client at all, so an import
    that quietly pulled one in would disqualify weft there. Asserting on the
    imported module set is cruder than an egress check but it runs anywhere.
    """

    FORBIDDEN = {"httpx", "requests", "aiohttp", "urllib3", "http.client"}

    def test_importing_weft_loads_no_http_client(self) -> None:
        import subprocess
        import sys

        probe = (
            "import sys;"
            "import weft, weft.platforms, weft.safety, weft.extract;"
            "import weft.platforms.search.brave, weft.platforms.search.searxng;"
            f"print(sorted({self.FORBIDDEN!r} & set(sys.modules)))"
        )
        result = subprocess.run(  # noqa: S603
            [sys.executable, "-c", probe], capture_output=True, text=True, check=True
        )
        assert result.stdout.strip() == "[]", f"weft imported an HTTP client: {result.stdout}"
