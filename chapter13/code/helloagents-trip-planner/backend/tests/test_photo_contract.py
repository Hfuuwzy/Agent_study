"""Photo fallback endpoint contract tests driven through the public HTTP API."""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from app.api.main import app
from app.runtime.factory import AppRuntime, RuntimeFactory, get_app_runtime
from tests.stubs import StubAmapTool, StubLLM, StubUnsplash


class NoResultUnsplash(StubUnsplash):
    """Unsplash stub that reports no matching photo."""

    def get_photo_url(self, query: str) -> str | None:
        self.calls.append(query)
        return None


class FailingUnsplash(StubUnsplash):
    """Unsplash stub that simulates a service failure."""

    def get_photo_url(self, query: str) -> str | None:
        self.calls.append(query)
        raise RuntimeError("图片服务不可用")


class PhotoContractTest(unittest.TestCase):
    """Verify photo fallback semantics through GET /api/poi/photo."""

    def setUp(self) -> None:
        self.amap = StubAmapTool()
        self.unsplash = StubUnsplash()
        self.runtime = self._runtime_for(self.unsplash)
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self) -> None:
        try:
            self.client.__exit__(None, None, None)
        finally:
            self.runtime.close()
            app.dependency_overrides.clear()

    def _runtime_for(self, unsplash: StubUnsplash) -> AppRuntime:
        """Build and inject an offline runtime for one photo-service stub."""
        runtime = AppRuntime(
            factory=RuntimeFactory(
                llm_factory=lambda: StubLLM(),
                amap_tool_factory=lambda: self.amap,
                unsplash_factory=lambda: unsplash,
            )
        )
        app.dependency_overrides[get_app_runtime] = lambda: runtime
        return runtime

    def _replace_unsplash(self, unsplash: StubUnsplash) -> None:
        """Replace the injected runtime and close the previous runtime first."""
        self.runtime.close()
        self.unsplash = unsplash
        self.runtime = self._runtime_for(unsplash)

    def test_photo_hit_returns_real_photo_contract(self) -> None:
        """A matching photo returns HTTP 200 and a non-placeholder response."""
        # Given: the injected Unsplash stub returns a real photo URL.
        # When: the public photo endpoint is requested for an attraction.
        response = self.client.get("/api/poi/photo", params={"name": "外滩"})

        # Then: the hit contract preserves the real URL without warnings.
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertTrue(body["photo_url"])
        self.assertEqual(body["photo_url"], self.unsplash.photo_url)
        self.assertFalse(body["is_placeholder"])
        self.assertEqual(body["warnings"], [])
        self.assertTrue(self.unsplash.calls)

    def test_photo_miss_returns_neutral_placeholder_contract(self) -> None:
        """A miss returns a neutral placeholder rather than an unrelated city image."""
        # Given: the injected Unsplash stub returns no matching photo.
        self._replace_unsplash(NoResultUnsplash())

        # When: the public photo endpoint is requested for an attraction.
        response = self.client.get("/api/poi/photo", params={"name": "外滩"})

        # Then: the miss remains HTTP 200 with explicit neutral fallback semantics.
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["success"])
        self.assertIsNone(body["photo_url"], "a miss must not use an unrelated city image")
        self.assertTrue(body["is_placeholder"])
        self.assertTrue(body["warnings"])
        self.assertTrue(self.unsplash.calls)

    def test_photo_service_exception_returns_failure_placeholder_contract(self) -> None:
        """A service exception is converted into an HTTP 200 failure fallback."""
        # Given: the injected Unsplash stub raises while looking up a photo.
        self._replace_unsplash(FailingUnsplash())

        # When: the public photo endpoint is requested for an attraction.
        response = self.client.get("/api/poi/photo", params={"name": "外滩"})

        # Then: the endpoint reports failure while keeping the response renderable.
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertFalse(body["success"])
        self.assertIsNone(body["photo_url"])
        self.assertTrue(body["is_placeholder"])
        self.assertTrue(body["warnings"])
        self.assertTrue(self.unsplash.calls)


if __name__ == "__main__":
    unittest.main()
