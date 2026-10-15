"""Pytest configuration and fixtures for Pre-ONE End-to-End integration tests."""

import sys
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio

repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root / "backend"))
sys.path.insert(0, str(repo_root / "agent" / "src"))
sys.path.insert(0, str(repo_root))

from e2e.harness import E2EHarness


@pytest_asyncio.fixture
async def e2e_harness() -> AsyncGenerator[E2EHarness, None]:
    """Provide a running real backend HTTP, PostgreSQL and Redis test harness."""
    harness = E2EHarness()
    try:
        await harness.setup()
        yield harness
    finally:
        # Executes even if setup() raises after partial resource allocation.
        await harness.cleanup()
