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
from poscenter_loyalty_agent.logging import sanitize_message
from poscenter_loyalty_agent.models import (
    AgentCommandCompletePayload,
    AgentCommandItem,
    CardsSyncPayload,
    HeartbeatPayload,
    TransactionsSyncPayload,
)
from poscenter_loyalty_agent.one_cursor import is_cursor_ahead_or_equal
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
        self._sync_trigger_event = asyncio.Event()
        self._pending_commands: list[AgentCommandItem] = []
        self._pending_completions: list[tuple[AgentCommandItem, AgentCommandCompletePayload]] = []
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
                await self._poll_and_enqueue_commands()
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

    async def _poll_and_enqueue_commands(self) -> None:
        """Poll Cloud for pending commands and flush any retryable completions."""
        await self._flush_pending_completions()

        try:
            res = await self.cloud_client.claim_commands()
        except CloudAuthError as exc:
            logger.error("Commands claim auth failed: %s", exc)
            return
        except Exception as exc:
            logger.warning("Temporary error polling commands (will retry next heartbeat): %s", exc)
            return

        if not res.commands:
            return

        for cmd in res.commands:
            self._pending_commands.append(cmd)

        self._sync_trigger_event.set()

    async def _flush_pending_completions(self) -> None:
        """Retry sending any unconfirmed command completions from earlier network failures."""
        if not self._pending_completions:
            return

        remaining: list[tuple[AgentCommandItem, AgentCommandCompletePayload]] = []
        for cmd, payload in self._pending_completions:
            try:
                await self.cloud_client.complete_command(cmd.id, payload)
                logger.info("Command completed: type=%s status=%s", cmd.type, payload.status)
            except CloudRetryableError:
                remaining.append((cmd, payload))
            except Exception as exc:
                logger.warning("Discarding uncompletable command %s (%s): %s", cmd.id, cmd.type, exc)

        self._pending_completions = remaining

    async def _complete_command_with_retry(
        self,
        command: AgentCommandItem,
        status: str,
        error: str | None,
    ) -> None:
        """Send command completion to Cloud with immediate retry on network errors, falling back to background retry."""
        payload = AgentCommandCompletePayload(status=status, error=error)
        max_retries = 3
        delay = 1.0

        for attempt in range(max_retries):
            if self._shutdown_event.is_set():
                break
            try:
                await self.cloud_client.complete_command(command.id, payload)
                logger.info("Command completed: type=%s status=%s", command.type, status)
                return
            except CloudRetryableError as exc:
                logger.warning(
                    "Temporary error completing command %s (attempt %d/%d): %s",
                    command.id,
                    attempt + 1,
                    max_retries,
                    exc,
                )
                await self._sleep_cancellable(delay)
                delay = min(delay * 2, 5.0)
            except Exception as exc:
                logger.warning("Non-retryable error completing command %s: %s", command.id, exc)
                return

        self._pending_completions.append((command, payload))

    async def _wait_for_next_interval_or_trigger(self, seconds: float) -> None:
        """Wait for interval timeout, shutdown event, or sync trigger (e.g. newly arrived command)."""
        if self._shutdown_event.is_set() or self._sync_trigger_event.is_set():
            return
        trigger_task = asyncio.create_task(self._sync_trigger_event.wait())
        shutdown_task = asyncio.create_task(self._shutdown_event.wait())
        sleep_task = asyncio.create_task(self.sleep_fn(seconds))
        done, pending = await asyncio.wait(
            [trigger_task, shutdown_task, sleep_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for t in pending:
            t.cancel()
            try:
                await t
            except (asyncio.CancelledError, Exception):
                pass

    async def _sync_loop(self) -> None:
        """Main synchronization loop with retry, backoff, pagination, and remote command execution."""
        logger.debug("Sync loop started.")
        while not self._shutdown_event.is_set():
            # 1. Check for queued remote commands (sync_now, full_resync)
            cmd = self._pending_commands.pop(0) if self._pending_commands else None
            if cmd is not None:
                # Clear trigger when command is taken into work (if no more commands pending)
                if not self._pending_commands:
                    self._sync_trigger_event.clear()

                logger.info("Command received: type=%s id=%s", cmd.type, cmd.id)
                is_full = (cmd.type == "full_resync")
                try:
                    await self.sync_cycle(full_resync=is_full)
                    self.retry_state.reset()
                    self.state_store.clear_error()
                    await self._complete_command_with_retry(cmd, status="completed", error=None)
                except Exception as exc:
                    err_msg = sanitize_message(str(exc))[:512]
                    logger.error("Command %s (%s) failed: %s", cmd.id, cmd.type, err_msg)
                    self.state_store.record_error(err_msg)
                    await self._complete_command_with_retry(cmd, status="failed", error=err_msg)
                    # Clear trigger before backoff pause so retry delay is honored
                    self._sync_trigger_event.clear()
                    delay = self.retry_state.next_delay()
                    await self._sleep_cancellable(delay)
                continue

            # 2. Regular sync cycle
            self._sync_trigger_event.clear()
            try:
                await self.sync_cycle(full_resync=False)
                self.retry_state.reset()
                self.state_store.clear_error()

                # Sleep idle interval before next cycle (or wake up on command)
                await self._wait_for_next_interval_or_trigger(float(self.settings.sync_interval_seconds))

            except asyncio.CancelledError:
                break
            except CloudProtocolError as exc:
                err_msg = f"CLOUD_PROTOCOL_ERROR: {exc}"
                logger.warning(err_msg)
                self.state_store.record_error(err_msg)
                self._sync_trigger_event.clear()
                delay = self.retry_state.next_delay(retry_after=exc.retry_after)
                await self._sleep_cancellable(delay)

            except CloudRetryableError as exc:
                err_msg = f"Cloud temporary error: {exc}"
                logger.warning(err_msg)
                self.state_store.record_error(err_msg)
                self._sync_trigger_event.clear()
                delay = self.retry_state.next_delay(retry_after=exc.retry_after)
                await self._sleep_cancellable(delay)

            except SourceProtocolError as exc:
                err_msg = f"SOURCE_PROTOCOL_ERROR: {exc}"
                logger.error(err_msg)
                self.state_store.record_error(err_msg)
                self._sync_trigger_event.clear()
                delay = self.retry_state.next_delay()
                await self._sleep_cancellable(delay)

            except OneMappingNotConfiguredError as exc:
                err_msg = f"ONE_MAPPING_NOT_CONFIGURED: {exc}"
                logger.error(err_msg)
                self.state_store.record_error(err_msg)
                self._sync_trigger_event.clear()
                delay = self.settings.sync_backoff_max_seconds
                await self._sleep_cancellable(delay)

            except SourceCursorStalledError as exc:
                err_msg = f"SOURCE_CURSOR_STALLED: {exc}"
                logger.error(err_msg)
                self.state_store.record_error(err_msg)
                self._sync_trigger_event.clear()
                delay = self.retry_state.next_delay()
                await self._sleep_cancellable(delay)

            except (CloudAuthError, CloudNonRetryableError) as exc:
                err_msg = f"Cloud fatal/rejected error: {exc}"
                logger.error(err_msg)
                self.state_store.record_error(err_msg)
                self._sync_trigger_event.clear()
                delay = self.settings.sync_backoff_max_seconds
                await self._sleep_cancellable(delay)

            except Exception as exc:
                err_msg = f"Unexpected sync error: {exc}"
                logger.exception(err_msg)
                self.state_store.record_error(err_msg)
                self._sync_trigger_event.clear()
                delay = self.retry_state.next_delay()
                await self._sleep_cancellable(delay)

    async def _sleep_cancellable(self, seconds: float) -> None:
        """Sleep for duration or until shutdown or sync trigger is set."""
        if self._shutdown_event.is_set():
            return
        sleep_task = asyncio.create_task(self.sleep_fn(seconds))
        shutdown_task = asyncio.create_task(self._shutdown_event.wait())
        trigger_task = asyncio.create_task(self._sync_trigger_event.wait())
        done, pending = await asyncio.wait(
            [sleep_task, shutdown_task, trigger_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

    async def sync_cycle(self, full_resync: bool = False) -> None:
        """Executes one complete sync pass: cards stream then transactions stream."""
        if full_resync and hasattr(self.source, "prepare_full_resync"):
            self.source.prepare_full_resync()
        try:
            await self._sync_cards_stream(full_resync=full_resync)
            await self._sync_transactions_stream(full_resync=full_resync)
        finally:
            if full_resync and hasattr(self.source, "finish_full_resync"):
                self.source.finish_full_resync()

    async def _sync_cards_stream(self, full_resync: bool = False) -> None:
        """Paginate through pending card batches up to max_pages_per_cycle."""
        pages_synced = 0
        max_pages = 10000 if full_resync else self.settings.max_pages_per_cycle
        saved_prev_cards_cursor = self.state_store.get_cursor("cards")
        page_cursor: str | None = None if full_resync else saved_prev_cards_cursor

        while not self._shutdown_event.is_set() and pages_synced < max_pages:
            current_cursor = page_cursor

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
                    "Syncing %d cards (page=%d/%d, stream=cards%s)",
                    len(batch.items),
                    pages_synced,
                    max_pages,
                    ", full_resync=True" if full_resync else "",
                )
                payload = CardsSyncPayload(cards=batch.items)
                ack = await self.cloud_client.sync_cards(payload)
                logger.info(
                    "Cards ACK received: %d created, %d updated, %d stale ignored",
                    ack.created,
                    ack.updated,
                    ack.ignored_stale,
                )

                now = datetime.now(UTC)
                self.state_store.commit_cursor("cards", batch.next_cursor, synced_at=now)

            # Check for stalled cursor
            if batch.has_more and batch.next_cursor == current_cursor:
                raise SourceCursorStalledError(
                    "SOURCE_CURSOR_STALLED: Cards source returned has_more=True with unchanged cursor."
                )

            page_cursor = batch.next_cursor

            if not batch.has_more:
                break

        if pages_synced >= max_pages and not full_resync:
            logger.info("Cards stream reached max page budget (%d pages); cycle continuing.", max_pages)

    async def _sync_transactions_stream(self, full_resync: bool = False) -> None:
        """Paginate through pending transaction batches up to max_pages_per_cycle."""
        pages_synced = 0
        max_pages = 10000 if full_resync else self.settings.max_pages_per_cycle
        saved_prev_tx_cursor = self.state_store.get_cursor("transactions")
        page_cursor: str | None = None if full_resync else saved_prev_tx_cursor

        while not self._shutdown_event.is_set() and pages_synced < max_pages:
            current_cursor = page_cursor

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
                    "Syncing %d transactions (page=%d/%d, stream=transactions%s)",
                    len(batch.items),
                    pages_synced,
                    max_pages,
                    ", full_resync=True" if full_resync else "",
                )
                payload = TransactionsSyncPayload(transactions=batch.items)
                ack = await self.cloud_client.sync_transactions(payload)
                logger.info(
                    "Transactions ACK received: %d created, %d duplicates",
                    ack.created,
                    ack.duplicates,
                )

                now = datetime.now(UTC)
                if full_resync:
                    if is_cursor_ahead_or_equal(batch.next_cursor, saved_prev_tx_cursor):
                        self.state_store.commit_cursor("transactions", batch.next_cursor, synced_at=now)
                    else:
                        self.state_store.commit_cursor("transactions", saved_prev_tx_cursor, synced_at=now)
                else:
                    self.state_store.commit_cursor("transactions", batch.next_cursor, synced_at=now)

            # Check for stalled cursor
            if batch.has_more and batch.next_cursor == current_cursor:
                raise SourceCursorStalledError(
                    "SOURCE_CURSOR_STALLED: Transactions source returned has_more=True with unchanged cursor."
                )

            page_cursor = batch.next_cursor

            if not batch.has_more:
                break

        if full_resync:
            # Ensure state store cursor is not behind saved_prev_tx_cursor at the end of full_resync
            final_cursor = self.state_store.get_cursor("transactions")
            if not is_cursor_ahead_or_equal(final_cursor, saved_prev_tx_cursor):
                self.state_store.commit_cursor("transactions", saved_prev_tx_cursor, synced_at=datetime.now(UTC))

        if pages_synced >= max_pages and not full_resync:
            logger.info("Transactions stream reached max page budget (%d pages); cycle continuing.", max_pages)
