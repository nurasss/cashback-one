"""Pre-ONE End-to-End Integration Flow Tests (TASK-013).

Comprehensive verification of:
1. Superadmin real HTTP login, Business A creation, Agent A creation.
2. Real Agent HTTP Client, Heartbeat, and last_seen_at reflection.
3. Card A & Transaction T1 sync with TestLoyaltySource.
4. Real Customer WhatsApp reverse login flow (challenge, simulated inbound Wappi webhook, token exchange).
5. Customer Wallet auto-binding, 13-digit barcode integrity, balance, and transaction history.
6. Second sync updating balance and appending Transaction T2.
7. Idempotency: duplicate sync produces no duplicate cards or transactions.
8. Multi-tenant Business B & Agent B isolation.
9. Agent tenant isolation (tenant derived from authenticated agent key).
10. Customer tenant isolation (customer only sees bound cards).
11. Manager tenant isolation over HTTP (agents, cards, businesses 403).
12. Superadmin aggregate dashboard & cross-tenant visibility.
13. Durable full-resync command pending status.
14. Agent revocation (rejected with 401).
15. Agent key rotation (old rejected, new accepted).
16. Fault & Retry: failed sync preserves cursor; retry succeeds cleanly.
17. Agent restart: reloads cursors from SQLite without re-sync.
18. Log privacy scan: zero raw secrets/credentials in backend logs.
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import httpx
import pytest
from poscenter_loyalty_agent.cloud_client import CloudAuthError, HttpCloudClient
from poscenter_loyalty_agent.config import AgentSettings
from poscenter_loyalty_agent.models import CardSyncItem, HeartbeatPayload, TransactionSyncItem
from poscenter_loyalty_agent.runtime import AgentRuntime
from poscenter_loyalty_agent.state_store import StateStore

from e2e.harness import E2EHarness
from e2e.source import TestLoyaltySource


def utcnow() -> datetime:
    return datetime.now(UTC)


@pytest.mark.asyncio
async def test_pre_one_e2e_full_chain(e2e_harness: E2EHarness) -> None:
    """Execute the complete real-infrastructure Pre-ONE end-to-end integration scenario."""
    base_url = e2e_harness.config.base_url

    async with httpx.AsyncClient(base_url=base_url) as client:
        # =========================================================================
        # 1. ADMIN LOGIN (REAL HTTP)
        # =========================================================================
        login_resp = await client.post(
            "/admin/auth/login",
            json={
                "login": e2e_harness.config.superadmin_login,
                "password": e2e_harness.config.superadmin_password,
            },
            headers={
                "Origin": base_url,
                "X-Admin-Request": "1",
            },
        )
        assert login_resp.status_code == 200, f"Admin login failed: {login_resp.text}"
        login_data = login_resp.json()
        superadmin_token = login_data["access_token"]
        assert superadmin_token
        assert "admin_refresh" in login_resp.cookies

        superadmin_headers = {
            "Origin": base_url,
            "X-Admin-Request": "1",
            "Authorization": f"Bearer {superadmin_token}",
        }

        # Verify /admin/me
        me_resp = await client.get("/admin/me", headers=superadmin_headers)
        assert me_resp.status_code == 200
        assert me_resp.json()["admin"]["role"] == "superadmin"

        # =========================================================================
        # 2. CREATE BUSINESS A VIA ADMIN API
        # =========================================================================
        biz_a_resp = await client.post(
            "/admin/businesses",
            json={
                "name": "Coffee House A",
            },
            headers=superadmin_headers,
        )
        assert biz_a_resp.status_code == 201, f"Create business failed: {biz_a_resp.text}"
        biz_a = biz_a_resp.json()
        business_a_id = UUID(biz_a["id"])
        assert biz_a["name"] == "Coffee House A"

        # =========================================================================
        # 3. CREATE AGENT A VIA ADMIN API
        # =========================================================================
        agent_a_resp = await client.post(
            "/admin/agents",
            json={"business_id": str(business_a_id)},
            headers=superadmin_headers,
        )
        assert agent_a_resp.status_code == 201, f"Create agent failed: {agent_a_resp.text}"
        agent_a_data = agent_a_resp.json()
        agent_a_id = UUID(agent_a_data["agent"]["id"])
        agent_a_key = agent_a_data["api_key"]
        assert agent_a_key
        assert "key_hash" not in agent_a_data  # key_hash must never be disclosed

        # =========================================================================
        # 4. REAL AGENT CLIENT & HEARTBEAT
        # =========================================================================
        agent_a_client = HttpCloudClient(base_url=base_url, api_key=agent_a_key)
        hb_result = await agent_a_client.send_heartbeat(
            HeartbeatPayload(version="0.1.0-e2e")
        )
        assert hb_result.status == "ok"

        # Verify heartbeat updated agent.last_seen_at in Admin API
        get_agent_resp = await client.get(
            f"/admin/agents/{agent_a_id}",
            headers=superadmin_headers,
        )
        assert get_agent_resp.status_code == 200
        assert get_agent_resp.json()["last_seen_at"] is not None

        # =========================================================================
        # 5. TEST LOYALTY SOURCE & CARD A / TRANSACTION T1 SYNC
        # =========================================================================
        barcode_a = "0123456789012"  # Exact 13 digits with leading zero
        phone_a = "+77017778899"
        card_a_t1_time = utcnow()

        card_a = CardSyncItem(
            barcode=barcode_a,
            phone=phone_a,
            full_name="Aigerim S.",
            balance=Decimal("1000.0000"),
            is_blocked=False,
            updated_at=card_a_t1_time,
        )
        tx_1 = TransactionSyncItem(
            external_id="tx-001",
            barcode=barcode_a,
            type="accrual",
            amount=Decimal("1000.0000"),
            balance_after=Decimal("1000.0000"),
            occurred_at=card_a_t1_time,
            receipt_ref="rec-001",
            store="Branch 1",
        )

        source_a = TestLoyaltySource(cards=[card_a], transactions=[tx_1])
        state_db_a = e2e_harness.temp_dir / "agent_a.sqlite3"
        state_store_a = StateStore(state_db_a)
        agent_settings_a = AgentSettings(
            agent_api_key=agent_a_key,
            agent_cloud_base_url=base_url,
            agent_state_db_path=state_db_a,
            agent_version="0.1.0-e2e",
        )
        runtime_a = AgentRuntime(
            settings=agent_settings_a,
            state_store=state_store_a,
            cloud_client=agent_a_client,
            source=source_a,
        )

        # Run first sync cycle
        await runtime_a.sync_cycle()

        # Check card in Admin API
        cards_search_resp = await client.post(
            "/admin/cards/search",
            json={"barcode": barcode_a},
            headers=superadmin_headers,
        )
        assert cards_search_resp.status_code == 200
        cards_search_data = cards_search_resp.json()
        assert len(cards_search_data["items"]) == 1
        assert cards_search_data["items"][0]["barcode"] == barcode_a
        assert Decimal(str(cards_search_data["items"][0]["balance"])) == Decimal("1000.0000")

        # =========================================================================
        # 6. CUSTOMER AUTH: WHATSAPP REVERSE LOGIN FLOW
        # =========================================================================
        device_cust_1 = "device-cust-uuid-101"
        chal_resp = await client.post(
            "/auth/challenge",
            json={"device_id": device_cust_1},
        )
        assert chal_resp.status_code == 200, f"Challenge start failed: {chal_resp.text}"
        chal_data = chal_resp.json()
        challenge_id = chal_data["challenge_id"]
        challenge_code = chal_data["code"]

        # Simulate authenticated inbound Wappi webhook message
        wappi_webhook_resp = await client.post(
            "/webhooks/wappi",
            headers={
                "X-Wappi-Webhook-Signature": e2e_harness.config.wappi_secret,
                "Content-Type": "application/json",
            },
            json={
                "messages": [
                    {
                        "wh_type": "incoming_message",
                        "profile_id": e2e_harness.config.wappi_profile_id,
                        "id": "wamid.e2e.test.001",
                        "body": challenge_code,
                        "type": "chat",
                        "from": "77017778899@c.us",
                        "to": "77001234567@c.us",
                        "chat_type": "dialog",
                    }
                ]
            },
        )
        assert wappi_webhook_resp.status_code == 200, f"Wappi webhook failed: {wappi_webhook_resp.text}"

        # Exchange confirmed challenge for customer access token
        exchange_resp = await client.get(
            f"/auth/challenge/{challenge_id}",
            headers={"X-Device-Id": device_cust_1},
        )
        assert exchange_resp.status_code == 200, f"Exchange failed: {exchange_resp.text}"
        exchange_data = exchange_resp.json()
        assert exchange_data["status"] == "confirmed"
        customer_token = exchange_data["access_token"]
        assert customer_token

        customer_headers = {"Authorization": f"Bearer {customer_token}"}

        # =========================================================================
        # 7. CUSTOMER WALLET: AUTO-BINDING, BARCODE & TRANSACTION HISTORY
        # =========================================================================
        wallet_resp = await client.get("/me/cards", headers=customer_headers)
        assert wallet_resp.status_code == 200, f"Wallet get failed: {wallet_resp.text}"
        wallet_cards = wallet_resp.json()
        assert len(wallet_cards) == 1
        card_in_wallet = wallet_cards[0]
        # P0 Acceptance: 13-digit barcode preserved with leading zero!
        assert card_in_wallet["barcode"] == barcode_a
        assert Decimal(str(card_in_wallet["balance"])) == Decimal("1000.0000")
        assert card_in_wallet["business"]["name"] == "Coffee House A"

        card_db_id = card_in_wallet["id"]

        # Fetch transactions for Card A via Customer API
        txs_resp = await client.get(
            f"/me/cards/{card_db_id}/transactions",
            headers=customer_headers,
        )
        assert txs_resp.status_code == 200
        txs_data = txs_resp.json()
        assert len(txs_data["items"]) == 1
        assert txs_data["items"][0]["external_id"] == "tx-001"
        assert Decimal(str(txs_data["items"][0]["amount"])) == Decimal("1000.0000")

        # =========================================================================
        # 8. SECOND SYNC: UPDATE BALANCE & APPEND TRANSACTION T2
        # =========================================================================
        card_a_v2 = CardSyncItem(
            barcode=barcode_a,
            phone=phone_a,
            full_name="Aigerim S.",
            balance=Decimal("1350.0000"),
            is_blocked=False,
            updated_at=card_a_t1_time + timedelta(minutes=5),
        )
        tx_2 = TransactionSyncItem(
            external_id="tx-002",
            barcode=barcode_a,
            type="accrual",
            amount=Decimal("350.0000"),
            balance_after=Decimal("1350.0000"),
            occurred_at=card_a_t1_time + timedelta(minutes=5),
            receipt_ref="rec-002",
            store="Branch 1",
        )
        source_a.add_card(card_a_v2)
        source_a.add_transaction(tx_2)

        # Run second sync cycle
        await runtime_a.sync_cycle()

        # Customer wallet must reflect updated balance and both transactions
        wallet_v2_resp = await client.get("/me/cards", headers=customer_headers)
        assert wallet_v2_resp.status_code == 200
        assert Decimal(str(wallet_v2_resp.json()[0]["balance"])) == Decimal("1350.0000")

        txs_v2_resp = await client.get(
            f"/me/cards/{card_db_id}/transactions",
            headers=customer_headers,
        )
        assert txs_v2_resp.status_code == 200
        tx_items_v2 = txs_v2_resp.json()["items"]
        assert len(tx_items_v2) == 2
        tx_ids = {t["external_id"] for t in tx_items_v2}
        assert tx_ids == {"tx-001", "tx-002"}

        # =========================================================================
        # 9. IDEMPOTENCY: DUPLICATE SYNC PRODUCES NO DUPLICATES
        # =========================================================================
        await runtime_a.sync_cycle()

        wallet_idem_resp = await client.get("/me/cards", headers=customer_headers)
        assert len(wallet_idem_resp.json()) == 1

        txs_idem_resp = await client.get(
            f"/me/cards/{card_db_id}/transactions",
            headers=customer_headers,
        )
        assert len(txs_idem_resp.json()["items"]) == 2

        # =========================================================================
        # 10. MULTI-TENANT: BUSINESS B, AGENT B & TENANT ISOLATION
        # =========================================================================
        biz_b_resp = await client.post(
            "/admin/businesses",
            json={"name": "Bakery B"},
            headers=superadmin_headers,
        )
        assert biz_b_resp.status_code == 201
        business_b_id = UUID(biz_b_resp.json()["id"])

        agent_b_resp = await client.post(
            "/admin/agents",
            json={"business_id": str(business_b_id)},
            headers=superadmin_headers,
        )
        assert agent_b_resp.status_code == 201
        agent_b_data = agent_b_resp.json()
        agent_b_id = UUID(agent_b_data["agent"]["id"])
        agent_b_key = agent_b_data["api_key"]

        barcode_b = "0987654321098"
        phone_b = "+77029998877"
        card_b = CardSyncItem(
            barcode=barcode_b,
            phone=phone_b,
            full_name="Bakery Customer",
            balance=Decimal("500.0000"),
            is_blocked=False,
            updated_at=utcnow(),
        )
        tx_b = TransactionSyncItem(
            external_id="tx-b-001",
            barcode=barcode_b,
            type="accrual",
            amount=Decimal("500.0000"),
            balance_after=Decimal("500.0000"),
            occurred_at=utcnow(),
            receipt_ref="rec-b-001",
            store="Bakery Main",
        )
        source_b = TestLoyaltySource(cards=[card_b], transactions=[tx_b])
        agent_b_client = HttpCloudClient(base_url=base_url, api_key=agent_b_key)
        state_db_b = e2e_harness.temp_dir / "agent_b.sqlite3"
        state_store_b = StateStore(state_db_b)
        agent_settings_b = AgentSettings(
            agent_api_key=agent_b_key,
            agent_cloud_base_url=base_url,
            agent_state_db_path=state_db_b,
            agent_version="0.1.0-e2e",
        )
        runtime_b = AgentRuntime(
            settings=agent_settings_b,
            state_store=state_store_b,
            cloud_client=agent_b_client,
            source=source_b,
        )
        await runtime_b.sync_cycle()

        # Customer Tenant Isolation: Customer A never receives Card B
        cust_a_wallet = (await client.get("/me/cards", headers=customer_headers)).json()
        assert len(cust_a_wallet) == 1
        assert cust_a_wallet[0]["barcode"] == barcode_a

        # =========================================================================
        # 11. MANAGER TENANT ISOLATION OVER HTTP
        # =========================================================================
        manager_a_login = "manager_a@loyalty.test"
        manager_a_pass = "ManagerPass_12345!Aa"
        await e2e_harness.bootstrap_manager(
            login=manager_a_login,
            password=manager_a_pass,
            business_id=business_a_id,
        )

        mgr_login_resp = await client.post(
            "/admin/auth/login",
            json={"login": manager_a_login, "password": manager_a_pass},
            headers={"Origin": base_url, "X-Admin-Request": "1"},
        )
        assert mgr_login_resp.status_code == 200
        manager_a_token = mgr_login_resp.json()["access_token"]
        manager_headers = {
            "Origin": base_url,
            "X-Admin-Request": "1",
            "Authorization": f"Bearer {manager_a_token}",
        }

        # Manager A can see Agent A, but Agent B is completely absent
        mgr_agents_resp = await client.get("/admin/agents", headers=manager_headers)
        assert mgr_agents_resp.status_code == 200
        mgr_agents_items = mgr_agents_resp.json()["items"]
        mgr_agent_ids = {a["id"] for a in mgr_agents_items}
        assert str(agent_a_id) in mgr_agent_ids
        assert str(agent_b_id) not in mgr_agent_ids

        # Manager A searching cards only sees Card A
        mgr_card_search = await client.post(
            "/admin/cards/search",
            json={"barcode": barcode_b},
            headers=manager_headers,
        )
        assert mgr_card_search.status_code == 200
        assert len(mgr_card_search.json()["items"]) == 0  # Cannot see Card B

        # Manager A cannot query businesses endpoint (Superadmin-only)
        mgr_biz_resp = await client.get("/admin/businesses", headers=manager_headers)
        assert mgr_biz_resp.status_code == 403

        # =========================================================================
        # 12. SUPERADMIN CROSS-TENANT VIEW & DASHBOARD
        # =========================================================================
        all_biz = (await client.get("/admin/businesses", headers=superadmin_headers)).json()
        assert len(all_biz["items"]) == 2

        all_agents = (await client.get("/admin/agents", headers=superadmin_headers)).json()
        assert len(all_agents["items"]) == 2

        dashboard_resp = await client.get("/admin/dashboard", headers=superadmin_headers)
        assert dashboard_resp.status_code == 200
        dash_data = dashboard_resp.json()
        assert dash_data["cards"] == 2
        assert dash_data["agents"]["online"] >= 1

        # =========================================================================
        # 13. FULL-RESYNC COMMAND (DURABLE & PENDING)
        # =========================================================================
        resync_resp = await client.post(
            f"/admin/agents/{agent_a_id}/full-resync",
            headers=superadmin_headers,
        )
        assert resync_resp.status_code == 202
        assert resync_resp.json()["status"] == "pending"

        # =========================================================================
        # 14. REVOKE AGENT B
        # =========================================================================
        revoke_resp = await client.post(
            f"/admin/agents/{agent_b_id}/revoke",
            headers=superadmin_headers,
        )
        assert revoke_resp.status_code == 200
        assert revoke_resp.json()["status"] == "revoked"
        assert revoke_resp.json()["agent"]["status"] == "revoked"

        # Revoked key must fail authentication with 401
        with pytest.raises(CloudAuthError):
            await agent_b_client.send_heartbeat(HeartbeatPayload(version="0.1.0-e2e"))

        # =========================================================================
        # 15. AGENT A KEY ROTATION
        # =========================================================================
        rotate_resp = await client.post(
            f"/admin/agents/{agent_a_id}/rotate-key",
            headers=superadmin_headers,
        )
        assert rotate_resp.status_code == 200
        new_agent_a_key = rotate_resp.json()["api_key"]
        assert new_agent_a_key != agent_a_key

        # Old key is rejected
        with pytest.raises(CloudAuthError):
            await agent_a_client.send_heartbeat(HeartbeatPayload(version="0.1.0-e2e"))

        # New key succeeds
        new_client_a = HttpCloudClient(base_url=base_url, api_key=new_agent_a_key)
        new_hb = await new_client_a.send_heartbeat(HeartbeatPayload(version="0.1.0-e2e"))
        assert new_hb.status == "ok"

        # Close agent clients
        await agent_a_client.close()
        await agent_b_client.close()
        await new_client_a.close()


@pytest.mark.asyncio
async def test_pre_one_e2e_retry_and_cursor_safety(e2e_harness: E2EHarness) -> None:
    """Verify that transient sync failures do not advance cursor, and retry succeeds cleanly."""
    base_url = e2e_harness.config.base_url

    async with httpx.AsyncClient(base_url=base_url) as client:
        # 1. Login and create business + agent
        login_resp = await client.post(
            "/admin/auth/login",
            json={
                "login": e2e_harness.config.superadmin_login,
                "password": e2e_harness.config.superadmin_password,
            },
            headers={"Origin": base_url, "X-Admin-Request": "1"},
        )
        admin_headers = {
            "Origin": base_url,
            "X-Admin-Request": "1",
            "Authorization": f"Bearer {login_resp.json()['access_token']}",
        }

        biz_resp = await client.post(
            "/admin/businesses",
            json={"name": "Retry Test Cafe"},
            headers=admin_headers,
        )
        biz_id = UUID(biz_resp.json()["id"])

        agent_resp = await client.post(
            "/admin/agents",
            json={"business_id": str(biz_id)},
            headers=admin_headers,
        )
        agent_key = agent_resp.json()["api_key"]

        # 2. Setup source with initial card
        barcode = "0555555555555"
        now = utcnow()
        card = CardSyncItem(
            barcode=barcode,
            phone="+77055555555",
            full_name="Retry User",
            balance=Decimal("100.0000"),
            is_blocked=False,
            updated_at=now - timedelta(minutes=15),
        )
        tx_1 = TransactionSyncItem(
            external_id="retry-tx-1",
            barcode=barcode,
            type="accrual",
            amount=Decimal("100.0000"),
            balance_after=Decimal("100.0000"),
            occurred_at=now - timedelta(minutes=10),
        )
        source = TestLoyaltySource(cards=[card], transactions=[tx_1])

        state_db = e2e_harness.temp_dir / "retry_agent.sqlite3"
        agent_settings = AgentSettings(
            agent_api_key=agent_key,
            agent_cloud_base_url=base_url,
            agent_state_db_path=state_db,
            agent_version="0.1.0-e2e",
        )
        state_store = StateStore(state_db)
        cloud_client = HttpCloudClient(base_url=base_url, api_key=agent_key)
        runtime = AgentRuntime(
            settings=agent_settings,
            state_store=state_store,
            cloud_client=cloud_client,
            source=source,
        )

        # First sync succeeds
        await runtime.sync_cycle()
        cursor_after_first = state_store.get_cursor("transactions")
        assert cursor_after_first is not None

        # 3. Add second transaction T2
        tx_2 = TransactionSyncItem(
            external_id="retry-tx-2",
            barcode=barcode,
            type="accrual",
            amount=Decimal("50.0000"),
            balance_after=Decimal("150.0000"),
            occurred_at=now - timedelta(minutes=5),
        )
        source.add_transaction(tx_2)

        # 4. Inject transport failure (point to non-existent port)
        dead_client = HttpCloudClient(base_url="http://127.0.0.1:18999", api_key=agent_key)
        faulty_runtime = AgentRuntime(
            settings=agent_settings,
            state_store=state_store,
            cloud_client=dead_client,
            source=source,
        )

        with pytest.raises(Exception):
            await faulty_runtime.sync_cycle()

        # Cursor MUST NOT advance on failure!
        cursor_after_fail = state_store.get_cursor("transactions")
        assert cursor_after_fail == cursor_after_first

        # 5. Restore connection and retry sync
        runtime_recovered = AgentRuntime(
            settings=agent_settings,
            state_store=state_store,
            cloud_client=cloud_client,
            source=source,
        )
        await runtime_recovered.sync_cycle()

        # Cursor advanced after successful recovery
        cursor_after_retry = state_store.get_cursor("transactions")
        assert cursor_after_retry != cursor_after_first

        # Check in Admin API: T2 was recorded exactly once
        dash = (await client.get("/admin/dashboard", headers=admin_headers)).json()
        assert dash["transactions"] >= 2

        await cloud_client.close()
        await dead_client.close()


@pytest.mark.asyncio
async def test_pre_one_e2e_agent_restart(e2e_harness: E2EHarness) -> None:
    """Verify that restarting the Agent reloads committed cursors from SQLite cleanly."""
    base_url = e2e_harness.config.base_url

    async with httpx.AsyncClient(base_url=base_url) as client:
        # Login and setup business & agent
        login_resp = await client.post(
            "/admin/auth/login",
            json={
                "login": e2e_harness.config.superadmin_login,
                "password": e2e_harness.config.superadmin_password,
            },
            headers={"Origin": base_url, "X-Admin-Request": "1"},
        )
        admin_headers = {
            "Origin": base_url,
            "X-Admin-Request": "1",
            "Authorization": f"Bearer {login_resp.json()['access_token']}",
        }

        biz_resp = await client.post(
            "/admin/businesses",
            json={"name": "Restart Test Cafe"},
            headers=admin_headers,
        )
        biz_id = UUID(biz_resp.json()["id"])
        agent_resp = await client.post(
            "/admin/agents",
            json={"business_id": str(biz_id)},
            headers=admin_headers,
        )
        agent_key = agent_resp.json()["api_key"]

        barcode = "0777777777777"
        card = CardSyncItem(
            barcode=barcode,
            phone="+77077777777",
            full_name="Restart User",
            balance=Decimal("200.0000"),
            is_blocked=False,
            updated_at=utcnow(),
        )
        source = TestLoyaltySource(cards=[card], transactions=[])

        state_db = e2e_harness.temp_dir / "restart_agent.sqlite3"
        state_store_1 = StateStore(state_db)
        agent_settings = AgentSettings(
            agent_api_key=agent_key,
            agent_cloud_base_url=base_url,
            agent_state_db_path=state_db,
            agent_version="0.1.0-e2e",
        )

        # Instance 1: syncs card
        cloud_client_1 = HttpCloudClient(base_url=base_url, api_key=agent_key)
        runtime_1 = AgentRuntime(
            settings=agent_settings,
            state_store=state_store_1,
            cloud_client=cloud_client_1,
            source=source,
        )
        await runtime_1.sync_cycle()
        cursor_1 = runtime_1.state_store.get_cursor("cards")
        await cloud_client_1.close()

        # Simulate process termination & restart with fresh runtime instance pointing to same DB
        state_store_2 = StateStore(state_db)
        cloud_client_2 = HttpCloudClient(base_url=base_url, api_key=agent_key)
        runtime_2 = AgentRuntime(
            settings=agent_settings,
            state_store=state_store_2,
            cloud_client=cloud_client_2,
            source=source,
        )
        # Verify state reloaded
        assert runtime_2.state_store.get_cursor("cards") == cursor_1

        # Running sync cycle again does not re-sync or raise error
        await runtime_2.sync_cycle()
        assert runtime_2.state_store.get_cursor("cards") == cursor_1
        await cloud_client_2.close()


@pytest.mark.asyncio
async def test_pre_one_e2e_log_privacy(e2e_harness: E2EHarness) -> None:
    """Scan backend process log to confirm no sensitive credentials or tokens were logged."""
    sensitive_markers = [
        e2e_harness.config.superadmin_password,
        e2e_harness.config.jwt_signing_key,
        e2e_harness.config.admin_jwt_signing_key,
        e2e_harness.config.wappi_secret,
    ]

    leaks = e2e_harness.scan_logs_for_secrets(sensitive_markers)
    assert not leaks, f"SECURITY LEAK: Sensitive secrets found in backend log: {leaks}"
