import pytest
from fastapi import HTTPException

from app.routers.products import _get_product_query_for_user
from app.services.product_service import _build_cluster_summary_prompt


class AsyncCursor:
    def __init__(self, items):
        self.items = items

    def __aiter__(self):
        self._iter = iter(self.items)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


class FakeCollection:
    def __init__(self, items):
        self.items = items

    def find(self, query=None):
        query = query or {}
        if not query:
            return AsyncCursor(self.items)
        return AsyncCursor([
            item for item in self.items
            if all(item.get(key) == value for key, value in query.items())
        ])


class FakeDb(dict):
    pass


@pytest.mark.asyncio
async def test_supplier_product_query_uses_purchase_line_skus():
    db = FakeDb({
        "purchases": FakeCollection([
            {
                "Supplier": "Nike Manufacturing EU",
                "purchase_lines": [
                    {"product_sku": 191},
                    {"product_sku": "403"},
                ],
            },
            {
                "Supplier": "Other Supplier",
                "purchase_lines": [{"product_sku": 777}],
            },
        ])
    })

    query = await _get_product_query_for_user(
        db,
        {"role": "supplier", "supplier_name": "Nike Manufacturing EU"}
    )

    assert sorted(query["sku"]["$in"]) == [191, 403]


@pytest.mark.asyncio
async def test_admin_product_query_is_unscoped():
    query = await _get_product_query_for_user(FakeDb({}), {"role": "admin"})

    assert query == {}


@pytest.mark.asyncio
async def test_supplier_without_company_is_forbidden():
    with pytest.raises(HTTPException) as exc:
        await _get_product_query_for_user(FakeDb({}), {"role": "supplier"})

    assert exc.value.status_code == 403


def test_supplier_cluster_summary_prompt_is_supplier_scoped():
    prompt = _build_cluster_summary_prompt(
        {"count": 1, "avg_price": 100.0, "avg_volume": 10.0},
        {"count": 2, "avg_price": 50.0, "avg_volume": 40.0},
        {"count": 3, "avg_price": 20.0, "avg_volume": 5.0},
        "Nike Manufacturing EU",
    )

    assert "Nike Manufacturing EU" in prompt
    assert "Supplier-filtered catalog size: 6 products" in prompt
    assert "global or company-wide" in prompt
    assert "Total catalog size" not in prompt
