import pytest
from fastapi import HTTPException, BackgroundTasks

from app.routers.products import _get_product_query_for_user, create_product
from app.services.product_service import _build_cluster_summary_prompt
from app.models.product import ProductCreate


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

    async def find_one(self, query):
        for item in self.items:
            # handle _id matches or basic matches
            if all(item.get(key) == value for key, value in query.items() if key != "_id"):
                return item
        return None

    async def insert_one(self, document):
        import bson
        document["_id"] = bson.ObjectId() if hasattr(bson, "ObjectId") else "fake_id"
        self.items.append(document)
        class InsertResult:
            inserted_id = document["_id"]
        return InsertResult()


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


@pytest.mark.asyncio
async def test_create_product_success():
    db = FakeDb({
        "products": FakeCollection([])
    })
    payload = ProductCreate(
        sku=1500,
        name="Test Shoe",
        price=99.99,
        discount=0.05,
        category="Apparel",
        current_stock=100,
        department_id="3",
        image="data:image/png;base64,abcdef",
        monthly_volume=0.0,
        cluster="LOW PERFORMERS",
        prep_delay=4,
        internal_delay=0,
        transport_delay=0
    )
    result = await create_product(payload, background_tasks=BackgroundTasks(), db=db, current_admin={"role": "admin"})
    assert result["sku"] == 1500
    assert result["name"] == "Test Shoe"
    assert result["price"] == 99.99
    assert result["image"] == "data:image/png;base64,abcdef"
    assert result["id"] == 1500


@pytest.mark.asyncio
async def test_create_product_duplicate_sku():
    db = FakeDb({
        "products": FakeCollection([{"sku": 1500, "name": "Existing Product"}])
    })
    payload = ProductCreate(
        sku=1500,
        name="Test Shoe",
        price=99.99,
        discount=0.05,
        category="Apparel",
        current_stock=100,
        department_id="3"
    )
    with pytest.raises(HTTPException) as exc:
        await create_product(payload, background_tasks=BackgroundTasks(), db=db, current_admin={"role": "admin"})
    assert exc.value.status_code == 400
    assert "already exists" in exc.value.detail
