"""Loyalty tiers without a turnover period (lifetime turnover): compatible create/edit contract."""
import pytest

from tests._dual_engine import engine  # noqa: F401
from tests.test_loyalty_tier_persistence import Env, env, form_body  # noqa: F401


def body_without_period(**overrides: object) -> dict[str, object]:
    body = form_body(**overrides)
    del body["turnover_period_months"]
    return body


@pytest.mark.asyncio
async def test_status_is_created_without_period_and_old_value_is_a_neutral_placeholder(env: Env) -> None:  # noqa: F811
    res = await env.client.post(env.url(), headers=env.mgr, json=body_without_period())
    assert res.status_code == 201, res.text
    tier = res.json()
    assert tier["turnover_period_months"] == 1  # NOT NULL legacy column placeholder, ignored by every calculation
    assert (await env.stored(tier["id"])).turnover_period_months == 1
    assert [t["id"] for t in await env.list()] == [tier["id"]]


@pytest.mark.asyncio
async def test_old_client_with_period_is_still_accepted_and_kept(env: Env) -> None:  # noqa: F811
    res = await env.client.post(env.url(), headers=env.mgr, json=form_body(turnover_period_months=6))
    assert res.status_code == 201, res.text
    assert res.json()["turnover_period_months"] == 6


@pytest.mark.asyncio
async def test_edit_without_period_changes_other_fields_and_keeps_old_period(env: Env) -> None:  # noqa: F811
    tier = (await env.client.post(env.url(), headers=env.mgr, json=form_body(turnover_period_months=12))).json()
    res = await env.client.patch(env.url(tier["id"]), headers=env.mgr, json=body_without_period(percent=7))
    assert res.status_code == 200, res.text
    stored = await env.stored(tier["id"])
    assert stored.percent == 7 and stored.turnover_period_months == 12


@pytest.mark.asyncio
async def test_null_period_is_still_refused_on_edit(env: Env) -> None:  # noqa: F811
    tier = (await env.client.post(env.url(), headers=env.mgr, json=body_without_period())).json()
    res = await env.client.patch(env.url(tier["id"]), headers=env.mgr, json={"turnover_period_months": None})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_overlap_is_checked_across_all_tiers_whatever_their_old_period(env: Env) -> None:  # noqa: F811
    first = await env.client.post(env.url(), headers=env.mgr, json=form_body(
        level=1, name_ru="A", name_kk="A", min_turnover=0, max_turnover=100000, turnover_period_months=3))
    assert first.status_code == 201
    clash = await env.client.post(env.url(), headers=env.mgr, json=body_without_period(
        level=2, name_ru="B", name_kk="B", min_turnover=50000, max_turnover=150000))
    assert clash.status_code == 409  # a different (historical) period no longer separates the ranges
    adjacent = await env.client.post(env.url(), headers=env.mgr, json=body_without_period(
        level=2, name_ru="B", name_kk="B", min_turnover=100000, max_turnover=None))
    assert adjacent.status_code == 201  # min inclusive / max exclusive: touching ranges are fine


@pytest.mark.asyncio
async def test_other_business_can_reuse_the_same_range(env: Env) -> None:  # noqa: F811
    assert (await env.client.post(env.url(), headers=env.mgr, json=body_without_period())).status_code == 201
    res = await env.client.post(env.url(biz=env.other_biz_id), headers=env.other_mgr, json=body_without_period())
    assert res.status_code == 201
