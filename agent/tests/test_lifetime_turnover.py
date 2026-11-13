from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from poscenter_loyalty_agent.config import AgentSettings
from poscenter_loyalty_agent.models import CardSyncItem
from poscenter_loyalty_agent.one_com_source import OneComLoyaltySource
from poscenter_loyalty_agent.state_store import StateStore, compute_card_hmac


def test_card_sync_item_spend_total_serialization():
    """Verify Decimal string serialization without scientific notation and 0 vs None handling."""
    now = datetime.now(UTC)

    # 1. Zero turnover - confirmed zero
    item_zero = CardSyncItem(
        barcode="200000000001",
        balance=Decimal("150.0000"),
        updated_at=now,
        spend_total=Decimal("0.0000"),
    )
    dump_zero = item_zero.model_dump(mode="json")
    assert dump_zero["spend_total"] == "0.0000"
    assert isinstance(dump_zero["spend_total"], str)

    # 2. Positive turnover with 4 decimal places
    item_pos = CardSyncItem(
        barcode="200000000001",
        balance=Decimal("150.0000"),
        updated_at=now,
        spend_total=Decimal("1250000.5000"),
    )
    dump_pos = item_pos.model_dump(mode="json")
    assert dump_pos["spend_total"] == "1250000.5000"
    assert isinstance(dump_pos["spend_total"], str)

    # 3. None turnover - omitted/unknown
    item_none = CardSyncItem(
        barcode="200000000001",
        balance=Decimal("150.0000"),
        updated_at=now,
        spend_total=None,
    )
    dump_none = item_none.model_dump(mode="json")
    assert dump_none["spend_total"] is None

    # Exclude none mode
    dump_exclude = item_none.model_dump(mode="json", exclude_none=True)
    assert "spend_total" not in dump_exclude


def test_card_sync_item_spend_total_validation():
    """Verify Pydantic validation rejects negative or excessively precise decimals."""
    now = datetime.now(UTC)

    # Negative turnover rejected by model
    with pytest.raises(ValidationError):
        CardSyncItem(
            barcode="200000000001",
            balance=Decimal("150.0000"),
            updated_at=now,
            spend_total=Decimal("-10.0000"),
        )

    # More than 4 decimal places rejected
    with pytest.raises(ValidationError):
        CardSyncItem(
            barcode="200000000001",
            balance=Decimal("150.0000"),
            updated_at=now,
            spend_total=Decimal("100.12345"),
        )


def test_hmac_backwards_compatibility_and_turnover_change():
    """Verify HMAC calculation matches legacy when spend_total is None, and changes when spend_total changes."""
    key = b"test_secret_key_1234567890"

    barcode = "200000000001"
    phone = "+77011112233"
    name = "Иван Иванов"
    is_blocked = False
    balance = Decimal("100.0000")

    # Legacy payload without spend_total
    legacy_payload = f"{barcode}|{phone}|{name}|{is_blocked}|{balance}"
    legacy_hash = compute_card_hmac(key, legacy_payload)

    # When spend_total is None, one_com_source uses spend_suffix = ""
    spend_total_none = None
    suffix_none = f"|{spend_total_none:f}" if spend_total_none is not None else ""
    payload_none = f"{barcode}|{phone}|{name}|{is_blocked}|{balance}{suffix_none}"
    assert payload_none == legacy_payload
    assert compute_card_hmac(key, payload_none) == legacy_hash

    # When spend_total is 0.0000
    spend_zero = Decimal("0.0000")
    suffix_zero = f"|{spend_zero:f}"
    payload_zero = f"{barcode}|{phone}|{name}|{is_blocked}|{balance}{suffix_zero}"
    hash_zero = compute_card_hmac(key, payload_zero)
    assert hash_zero != legacy_hash

    # When turnover changes from 0 to 50000, hash must change even if balance is identical
    spend_fifty_k = Decimal("50000.0000")
    suffix_fifty_k = f"|{spend_fifty_k:f}"
    payload_fifty_k = f"{barcode}|{phone}|{name}|{is_blocked}|{balance}{suffix_fifty_k}"
    hash_fifty_k = compute_card_hmac(key, payload_fifty_k)

    assert hash_fifty_k != hash_zero
    assert hash_fifty_k != legacy_hash


def test_config_defaults_and_toggle():
    """Verify agent_lifetime_turnover_enabled is False by default and respects settings."""
    default_settings = AgentSettings(
        agent_env="test",
        agent_key="test_agent_key_12345",
        cloud_base_url="https://cloud.example.com",
    )
    assert default_settings.agent_lifetime_turnover_enabled is False
    assert default_settings.agent_one_turnover_register == "ПродажиПоБонуснымКартам"
    assert default_settings.agent_one_turnover_card_dim == "БонуснаяКарта"
    assert default_settings.agent_one_turnover_amount_res == "Сумма"

    enabled_settings = AgentSettings(
        agent_env="test",
        agent_key="test_agent_key_12345",
        cloud_base_url="https://cloud.example.com",
        agent_lifetime_turnover_enabled=True,
    )
    assert enabled_settings.agent_lifetime_turnover_enabled is True


def _mock_mapping():
    cfg = MagicMock()
    cfg.card_id_field = "Ссылка"
    cfg.card_barcode_field = "Код"
    cfg.card_phone_field = "Телефон"
    cfg.card_full_name_field = "Наименование"
    cfg.balance_amount_resource = "СуммаОстаток"
    cfg.card_catalog_name = "БонусныеКарты"
    cfg.balance_register_name = "ОстаткиБонусныхКарт"
    cfg.balance_card_dimension = "БонуснаяКарта"
    return cfg


def test_one_com_source_query_construction():
    """Verify query text contains turnover accumulation join only when enabled."""
    store = MagicMock(spec=StateStore)
    store.get_card_hashes.return_value = {}
    cfg = _mock_mapping()

    # 1. Disabled
    settings_off = AgentSettings(
        agent_env="test",
        agent_key="test_key",
        cloud_base_url="https://cloud.example.com",
        agent_lifetime_turnover_enabled=False,
    )
    src_off = OneComLoyaltySource(settings=settings_off, state_store=store, mapping_config=cfg)

    with patch.object(src_off, "_get_connection"), \
         patch.object(src_off, "_execute_query") as mock_exec:
        mock_sel = MagicMock()
        mock_sel.Следующий.return_value = False
        mock_exec.return_value = mock_sel

        src_off._fetch_all_changed_cards_worker()
        assert mock_exec.called
        query_text = mock_exec.call_args[0][1]
        assert "ПродажиПоБонуснымКартам" not in query_text
        assert "КАК Оборот" not in query_text

    # 2. Enabled
    settings_on = AgentSettings(
        agent_env="test",
        agent_key="test_key",
        cloud_base_url="https://cloud.example.com",
        agent_lifetime_turnover_enabled=True,
    )
    src_on = OneComLoyaltySource(settings=settings_on, state_store=store, mapping_config=cfg)

    with patch.object(src_on, "_get_connection"), \
         patch.object(src_on, "_execute_query") as mock_exec:
        mock_sel = MagicMock()
        mock_sel.Следующий.return_value = False
        mock_exec.return_value = mock_sel

        src_on._fetch_all_changed_cards_worker()
        assert mock_exec.called
        query_text = mock_exec.call_args[0][1]
        assert "РегистрНакопления.ПродажиПоБонуснымКартам.Обороты(, , , )" in query_text
        assert "СУММА(Об.СуммаОборот) КАК Оборот" in query_text
        assert "СГРУППИРОВАТЬ ПО" in query_text
        assert "Об.БонуснаяКарта" in query_text
        assert "ЕСТЬNULL(Об.Оборот, 0) КАК Оборот" in query_text
        assert "ПО К.Ссылка = Об.Карточка" in query_text
        # Must NOT query physical table rows directly
        assert "РегистрНакопления.ПродажиПоБонуснымКартам КАК Р" not in query_text


def test_one_com_source_query_amount_resource_derivation():
    """Verify that resource name derives <Res>Оборот or preserves existing suffix."""
    store = MagicMock(spec=StateStore)
    store.get_card_hashes.return_value = {}
    cfg = _mock_mapping()

    # Case A: Amount res is 'Сумма' -> derives 'СуммаОборот'
    settings_a = AgentSettings(
        agent_env="test",
        agent_key="test_key",
        cloud_base_url="https://cloud.example.com",
        agent_lifetime_turnover_enabled=True,
        agent_one_turnover_amount_res="Сумма",
    )
    src_a = OneComLoyaltySource(settings=settings_a, state_store=store, mapping_config=cfg)
    with patch.object(src_a, "_get_connection"), patch.object(src_a, "_execute_query") as mock_exec:
        mock_sel = MagicMock()
        mock_sel.Следующий.return_value = False
        mock_exec.return_value = mock_sel
        src_a._fetch_all_changed_cards_worker()
        q_a = mock_exec.call_args[0][1]
        assert "СУММА(Об.СуммаОборот) КАК Оборот" in q_a

    # Case B: Amount res already has 'Оборот' suffix -> does not duplicate ('СуммаОборотОборот')
    settings_b = AgentSettings(
        agent_env="test",
        agent_key="test_key",
        cloud_base_url="https://cloud.example.com",
        agent_lifetime_turnover_enabled=True,
        agent_one_turnover_amount_res="СуммаОборот",
    )
    src_b = OneComLoyaltySource(settings=settings_b, state_store=store, mapping_config=cfg)
    with patch.object(src_b, "_get_connection"), patch.object(src_b, "_execute_query") as mock_exec:
        mock_sel = MagicMock()
        mock_sel.Следующий.return_value = False
        mock_exec.return_value = mock_sel
        src_b._fetch_all_changed_cards_worker()
        q_b = mock_exec.call_args[0][1]
        assert "СУММА(Об.СуммаОборот) КАК Оборот" in q_b
        assert "СуммаОборотОборот" not in q_b


def test_one_com_source_query_aggregation_and_no_duplicate_cards():
    """Verify aggregated query results produce exactly one card item without duplicates.

    NOTE: This test verifies query structure, result extraction, and card deduplication
    using mocked 1C COM objects. Mocks do NOT prove query execution or performance in a
    real 1C:Enterprise (ONE) runtime environment. Physical execution must be verified
    against real 1C databases during pilot testing.
    """
    store = MagicMock(spec=StateStore)
    store.get_card_hashes.return_value = {}
    cfg = _mock_mapping()

    settings = AgentSettings(
        agent_env="test",
        agent_key="test_key",
        cloud_base_url="https://cloud.example.com",
        agent_lifetime_turnover_enabled=True,
    )
    src = OneComLoyaltySource(settings=settings, state_store=store, mapping_config=cfg)

    # Simulate 3 cards from 1C query (card-1 with positive turnover, card-2 with zero, card-3 with None)
    class MockRow:
        def __init__(self, ref, code, phone, name, balance, turnover):
            self.Ссылка = ref
            self.Код = code
            self.Телефон = phone
            self.Наименование = name
            self.Заблокирована = False
            self.ПометкаУдаления = False
            self.Баланс = balance
            self.Оборот = turnover

    rows = [
        MockRow("ref-1", "200000000001", "+77011112233", "Покупатель 1", 100, 150000.5),
        MockRow("ref-2", "200000000002", "+77011112234", "Покупатель 2", 50, 0),
        MockRow("ref-3", "200000000003", "+77011112235", "Покупатель 3", 0, None),
    ]
    row_iter = iter(rows)

    mock_sel = MagicMock()
    def next_row():
        try:
            curr = next(row_iter)
            for attr in ["Ссылка", "Код", "Телефон", "Наименование", "Заблокирована", "ПометкаУдаления", "Баланс", "Оборот"]:
                setattr(mock_sel, attr, getattr(curr, attr))
            return True
        except StopIteration:
            return False

    mock_sel.Следующий.side_effect = next_row

    with patch.object(src, "_get_connection"), \
         patch.object(src, "_execute_query", return_value=mock_sel), \
         patch.object(src, "_get_ref_uuid", side_effect=lambda conn, ref: str(ref)):

        items = src._fetch_all_changed_cards_worker()

        # Exactly 3 cards produced - no duplicate cards
        assert len(items) == 3
        uuids = [card_uuid for card_uuid, _ in items]
        assert len(uuids) == len(set(uuids)), "Card UUIDs must be unique, no duplicates allowed"

        card1 = items[0][1]
        assert card1.barcode == "200000000001"
        assert card1.spend_total == Decimal("150000.5000")

        card2 = items[1][1]
        assert card2.barcode == "200000000002"
        assert card2.spend_total == Decimal("0.0000")

        card3 = items[2][1]
        assert card3.barcode == "200000000003"
        assert card3.spend_total is None


def test_one_com_source_turnover_data_handling(tmp_path):
    """Verify extraction of turnover, negative turnover handling, zero vs confirmed, and monotonic updated_at."""
    db_path = tmp_path / "state.db"
    store = StateStore(db_path)

    # Pre-populate state store with an existing card
    old_time = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    old_hash = compute_card_hmac(b"test_key", "200000000001|||False|100.0000")
    store.record_pending_cards(
        session_id="test_sess_0",
        page=1,
        cards=[("ref-1", old_hash, old_time)],
    )
    store.commit_pending_cards("test_sess_0", 1)

    settings_on = AgentSettings(
        agent_env="test",
        agent_key="test_key",
        cloud_base_url="https://cloud.example.com",
        agent_lifetime_turnover_enabled=True,
    )
    cfg = _mock_mapping()
    src = OneComLoyaltySource(settings=settings_on, state_store=store, mapping_config=cfg)
    src._hmac_key = b"test_key"

    class Mock1CRow:
        def __init__(self, ref, code, balance, turnover):
            self.Ссылка = ref
            self.Код = code
            self.Телефон = ""
            self.Наименование = ""
            self.Заблокирована = False
            self.ПометкаУдаления = False
            self.Баланс = balance
            self.Оборот = turnover

    class Mock1CSelection:
        def __init__(self, rows):
            self.rows = rows
            self.idx = -1

        def Следующий(self):
            self.idx += 1
            if self.idx < len(self.rows):
                for k, v in self.rows[self.idx].__dict__.items():
                    setattr(self, k, v)
                return True
            return False

    class Mock1CRowNoTurnover:
        def __init__(self, ref, code, balance):
            self.Ссылка = ref
            self.Код = code
            self.Телефон = ""
            self.Наименование = ""
            self.Заблокирована = False
            self.ПометкаУдаления = False
            self.Баланс = balance

    rows = [
        # Card 1: Existing card, now has turnover 5000.00. Must detect change and increment updated_at
        Mock1CRow("ref-1", "200000000001", 100, 5000),
        # Card 2: New card with confirmed zero turnover from ЕСТЬNULL
        Mock1CRow("ref-2", "200000000002", 50, 0),
        # Card 3: Card with negative turnover in 1C -> spend_total must be None (not clamped to 0)
        Mock1CRow("ref-3", "200000000003", 20, -150),
        # Card 4: Card with None turnover (COM result None / NULL) -> spend_total must be None (not 0!)
        Mock1CRow("ref-4", "200000000004", 10, None),
        # Card 5: Card with missing Оборот attribute -> spend_total must be None (not 0!)
        Mock1CRowNoTurnover("ref-5", "200000000005", 30),
    ]

    with patch.object(src, "_get_connection"), \
         patch.object(src, "_execute_query", return_value=Mock1CSelection(rows)), \
         patch.object(src, "_get_ref_uuid", side_effect=lambda conn, ref: ref):

        changed = src._fetch_all_changed_cards_worker()

        # All 5 cards should be detected as changed
        assert len(changed) == 5

        # Card 1
        uuid1, item1 = changed[0]
        assert uuid1 == "ref-1"
        assert item1.spend_total == Decimal("5000.0000")
        assert item1.updated_at > datetime.fromisoformat(old_time)

        # Card 2: 0 turnover -> Decimal("0.0000")
        uuid2, item2 = changed[1]
        assert uuid2 == "ref-2"
        assert item2.spend_total == Decimal("0.0000")

        # Card 3: Negative turnover -> None per contract §2
        uuid3, item3 = changed[2]
        assert uuid3 == "ref-3"
        assert item3.spend_total is None

        # Card 4: None turnover -> None (unknown, NOT converted to zero!)
        uuid4, item4 = changed[3]
        assert uuid4 == "ref-4"
        assert item4.spend_total is None, f"Expected None for unknown turnover, got {item4.spend_total}"

        # Card 5: Missing attribute -> None (unknown, NOT converted to zero!)
        uuid5, item5 = changed[4]
        assert uuid5 == "ref-5"
        assert item5.spend_total is None, f"Expected None for missing turnover attribute, got {item5.spend_total}"
