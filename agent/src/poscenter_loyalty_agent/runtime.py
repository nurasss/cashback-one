"""Agent runtime coordinating sync loop, independent heartbeat, and graceful shutdown."""

from __future__ import annotations

import asyncio
import logging
import signal
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from poscenter_loyalty_agent.cloud_client import (
    CloudAuthError,
    CloudClient,
    CloudNonRetryableError,
    CloudProtocolError,
    CloudRetryableError,
    HttpCloudClient,
)
from poscenter_loyalty_agent.config import AgentSettings
from poscenter_loyalty_agent.models import (
    CardsSyncPayload,
    HeartbeatPayload,
    TransactionsSyncPayload,
)
from poscenter_loyalty_agent.pos_server import PosServer
from poscenter_loyalty_agent.process_lock import AgentAlreadyRunningError, ProcessLock
from poscenter_loyalty_agent.retry import RetryState
from poscenter_loyalty_agent.source import (
    LoyaltySource,
    OneMappingNotConfiguredError,
    SourceProtocolError,
    get_loyalty_source,
)
from poscenter_loyalty_agent.state_store import StateStore

logger = logging.getLogger(__name__)


class SourceCursorStalledError(RuntimeError):
    """Raised when the data source returns has_more=True but cursor has not advanced."""

    def __init__(self, message: str = "SOURCE_CURSOR_STALLED: Source cursor did not advance despite has_more=True.") -> None:
        super().__init__(message)
        self.code = "SOURCE_CURSOR_STALLED"


class AgentRuntime:
    """Core runtime engine managing sync loop and independent heartbeat."""

    def __init__(
        self,
        settings: AgentSettings,
        state_store: StateStore | None = None,
        cloud_client: CloudClient | None = None,
        source: LoyaltySource | None = None,
        sleep_fn: Callable[[float], Any] | None = None,
    ) -> None:
        self.settings = settings
        self.state_store = state_store or StateStore(settings.state_db_path)
        self.cloud_client = cloud_client or HttpCloudClient(
            base_url=str(settings.cloud_api_base_url),
            api_key=settings.agent_api_key,
            timeout=settings.cloud_api_timeout_seconds,
            verify_ssl=settings.cloud_api_verify_ssl,
        )
        self.source = source or get_loyalty_source(settings)
        self.sleep_fn = sleep_fn or asyncio.sleep

        self.process_lock = ProcessLock(settings.lock_file_path)
        self.retry_state = RetryState(
            initial_seconds=settings.sync_backoff_initial_seconds,
            max_seconds=settings.sync_backoff_max_seconds,
            jitter_ratio=settings.sync_backoff_jitter_ratio,
            sleep_fn=self.sleep_fn,
        )

        self._shutdown_event = asyncio.Event()
        self._heartbeat_task: asyncio.Task[None] | None = None
        self._sync_task: asyncio.Task[None] | None = None
        self._is_running = False
        self._pos_server: PosServer | None = None

    @property
    def is_running(self) -> bool:
        return self._is_running

    def request_stop(self) -> None:
        """Signal the runtime to gracefully stop all background tasks."""
        logger.info("Agent shutdown requested.")
        self._shutdown_event.set()

    async def run(self) -> None:
        """Main execution entrypoint: acquires process lock and starts loops."""
        logger.info(
            "Starting POSCENTER Loyalty Agent v%s (adapter_mode=%s, interval=%ss)",
            self.settings.agent_version,
            self.settings.one_adapter_mode,
            self.settings.sync_interval_seconds,
        )

        try:
            self.process_lock.acquire()
        except AgentAlreadyRunningError as exc:
            logger.error("Failed to start agent: %s", exc)
            raise

        self._is_running = True

        # Set up signal handlers if running on Unix in main thread
        self._setup_signals()

        try:
            if self.settings.agent_pos_server_enabled:
                try:
                    self._pos_server = PosServer(self.settings)
                    await asyncio.to_thread(self._pos_server.start)
                except Exception as exc:
                    logger.error("POS startup failed (type=%s); sync continues", type(exc).__name__)
            # Heartbeat and sync loop run concurrently and independently
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop(), name="HeartbeatLoop")
            self._sync_task = asyncio.create_task(self._sync_loop(), name="SyncLoop")

            # Wait until shutdown is signaled or a critical error occurs
            await self._shutdown_event.wait()
        finally:
            await self._cleanup()

    def _setup_signals(self) -> None:
        try:
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, self.request_stop)
        except (NotImplementedError, RuntimeError):
            # Signal handlers cannot be registered on Windows or non-main threads
            pass

    async def _cleanup(self) -> None:
        """Wait for in-flight operations up to shutdown grace period, then cancel tasks and close resources."""
        grace = float(self.settings.shutdown_grace_seconds)
        logger.info("Cleaning up runtime resources (grace period: %.1fs)...", grace)
        self._is_running = False

        if self._pos_server is not None:
            try:
                await asyncio.to_thread(self._pos_server.stop)
            except Exception as exc:
                logger.warning("POS shutdown failed (type=%s)", type(exc).__name__)

        active_tasks = [t for t in (self._sync_task, self._heartbeat_task) if t is not None and not t.done()]
        if active_tasks and grace > 0:
            try:
                # Wait for active tasks to complete in-flight sync/commit
                await asyncio.wait(active_tasks, timeout=grace)
            except Exception as exc:
                logger.warning("Error waiting for active tasks during shutdown: %s", exc)

        # Force cancel any remaining tasks
        for task in (self._sync_task, self._heartbeat_task):
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass

        # Close clients
        try:
            await self.cloud_client.close()
        except Exception as exc:
            logger.warning("Error closing cloud client: %s", exc)

        try:
            await self.source.close()
        except Exception as exc:
            logger.warning("Error closing data source: %s", exc)

        # Release lock
        try:
            self.process_lock.release()
        except Exception as exc:
            logger.warning("Error releasing process lock: %s", exc)

        logger.info("Agent runtime shutdown complete.")

    async def _heartbeat_loop(self) -> None:
        """Independent heartbeat loop that sends health status to Cloud API."""
        logger.debug("Heartbeat loop started.")
        while not self._shutdown_event.is_set():
            try:
                status = self.state_store.get_status()
                payload = HeartbeatPayload(
                    version=self.settings.agent_version,
                    last_successful_sync_at=status.last_successful_sync_at,
                    error=status.last_error,
                )
                await self.cloud_client.send_heartbeat(payload)
                now = datetime.now(UTC)
                self.state_store.record_heartbeat(now)
                logger.debug("Heartbeat sent successfully at %s", now.isoformat())
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("Heartbeat failed (will retry next interval): %s", exc)

            try:
                # Sleep until next heartbeat interval or shutdown
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=float(self.settings.heartbeat_interval_seconds),
                )
            except TimeoutError:
                continue

    async def _sync_loop(self) -> None:
        """Main synchronization loop with retry, backoff, and pagination."""
        logger.debug("Sync loop started.")
        while not self._shutdown_event.is_set():
            try:
                # Execute one full sync cycle (cards + transactions)
                await self.sync_cycle()
                self.retry_state.reset()
                self.state_store.clear_error()

                # Sleep idle interval before next cycle
                try:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=float(self.settings.sync_interval_seconds),
                    )
                except TimeoutError:
                    continue

            except asyncio.CancelledError:
                break
            except CloudProtocolError as exc:
                err_msg = f"CLOUD_PROTOCOL_ERROR: {exc}"
                logger.warning(err_msg)
                self.state_store.record_error(err_msg)
                delay = self.retry_state.next_delay(retry_after=exc.retry_after)
                await self._sleep_cancellable(delay)

            except CloudRetryableError as exc:
                err_msg = f"Cloud temporary error: {exc}"
                logger.warning(err_msg)
                self.state_store.record_error(err_msg)
                delay = self.retry_state.next_delay(retry_after=exc.retry_after)
                await self._sleep_cancellable(delay)

            except SourceProtocolError as exc:
                err_msg = f"SOURCE_PROTOCOL_ERROR: {exc}"
                logger.error(err_msg)
                self.state_store.record_error(err_msg)
                delay = self.retry_state.next_delay()
                await self._sleep_cancellable(delay)

            except OneMappingNotConfiguredError as exc:
                err_msg = f"ONE_MAPPING_NOT_CONFIGURED: {exc}"
                logger.error(err_msg)
                self.state_store.record_error(err_msg)
                # Sleep max backoff when mapping is missing to avoid spamming
                delay = self.settings.sync_backoff_max_seconds
                await self._sleep_cancellable(delay)

            except SourceCursorStalledError as exc:
                err_msg = f"SOURCE_CURSOR_STALLED: {exc}"
                logger.error(err_msg)
                self.state_store.record_error(err_msg)
                delay = self.retry_state.next_delay()
                await self._sleep_cancellable(delay)

            except (CloudAuthError, CloudNonRetryableError) as exc:
                err_msg = f"Cloud fatal/rejected error: {exc}"
                logger.error(err_msg)
                self.state_store.record_error(err_msg)
                delay = self.settings.sync_backoff_max_seconds
                await self._sleep_cancellable(delay)

            except Exception as exc:
                err_msg = f"Unexpected sync error: {exc}"
                logger.exception(err_msg)
                self.state_store.record_error(err_msg)
                delay = self.retry_state.next_delay()
                await self._sleep_cancellable(delay)

    async def _sleep_cancellable(self, seconds: float) -> None:
        """Sleep for duration or until shutdown event is triggered."""
        if self._shutdown_event.is_set():
            return
        sleep_task = asyncio.create_task(self.sleep_fn(seconds))
        shutdown_task = asyncio.create_task(self._shutdown_event.wait())
        done, pending = await asyncio.wait(
            [sleep_task, shutdown_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    async def sync_cycle(self) -> None:
        """Executes one complete sync pass: cards stream then transactions stream."""
        await self._sync_cards_stream()
        await self._sync_transactions_stream()

    async def _sync_cards_stream(self) -> None:
        """Paginate through pending card batches up to max_pages_per_cycle."""
        pages_synced = 0
        max_pages = self.settings.max_pages_per_cycle

        while not self._shutdown_event.is_set() and pages_synced < max_pages:
            current_cursor = self.state_store.get_cursor("cards")
            batch = await self.source.fetch_cards(
                cursor=current_cursor,
                limit=self.settings.batch_size_cards,
            )

            # Protocol violation check: empty items but has_more=True
            if not batch.items and batch.has_more:
                raise SourceProtocolError(
                    "SOURCE_PROTOCOL_ERROR: Cards source returned empty items with has_more=True."
                )

            if batch.items:
                pages_synced += 1
                logger.info(
                    "Syncing %d cards (page=%d/%d, stream=cards)",
                    len(batch.items),
                    pages_synced,
                    max_pages,
                )
                payload = CardsSyncPayload(cards=batch.items)
                ack = await self.cloud_client.sync_cards(payload)
                logger.info(
                    "Cards ACK received: %d created, %d updated, %d stale ignored",
                    ack.created,
                    ack.updated,
                    ack.ignored_stale,
                )

                # Cursor advances ONLY after 2xx ACK from Cloud
                now = datetime.now(UTC)
                self.state_store.commit_cursor("cards", batch.next_cursor, synced_at=now)

            # Check for stalled cursor
            if batch.has_more and batch.next_cursor == current_cursor:
                raise SourceCursorStalledError(
                    "SOURCE_CURSOR_STALLED: Cards source returned has_more=True with unchanged cursor."
                )

            if not batch.has_more:
                break

        if pages_synced >= max_pages:
            logger.info("Cards stream reached max page budget (%d pages); cycle continuing.", max_pages)

    async def _sync_transactions_stream(self) -> None:
        """Paginate through pending transaction batches up to max_pages_per_cycle."""
        pages_synced = 0
        max_pages = self.settings.max_pages_per_cycle

        while not self._shutdown_event.is_set() and pages_synced < max_pages:
            current_cursor = self.state_store.get_cursor("transactions")
            batch = await self.source.fetch_transactions(
                cursor=current_cursor,
                limit=self.settings.batch_size_transactions,
            )

            # Protocol violation check: empty items but has_more=True
            if not batch.items and batch.has_more:
                raise SourceProtocolError(
                    "SOURCE_PROTOCOL_ERROR: Transactions source returned empty items with has_more=True."
                )

            if batch.items:
                pages_synced += 1
                logger.info(
                    "Syncing %d transactions (page=%d/%d, stream=transactions)",
                    len(batch.items),
                    pages_synced,
                    max_pages,
                )
                payload = TransactionsSyncPayload(transactions=batch.items)
                ack = await self.cloud_client.sync_transactions(payload)
                logger.info(
                    "Transactions ACK received: %d created, %d duplicates",
                    ack.created,
                    ack.duplicates,
                )

                # Cursor advances ONLY after 2xx ACK from Cloud
                now = datetime.now(UTC)
                self.state_store.commit_cursor("transactions", batch.next_cursor, synced_at=now)

            # Check for stalled cursor
            if batch.has_more and batch.next_cursor == current_cursor:
                raise SourceCursorStalledError(
                    "SOURCE_CURSOR_STALLED: Transactions source returned has_more=True with unchanged cursor."
                )

            if not batch.has_more:
                break

        if pages_synced >= max_pages:
            logger.info("Transactions stream reached max page budget (%d pages); cycle continuing.", max_pages)
