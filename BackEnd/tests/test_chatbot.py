import asyncio
import pytest
from app.routers.chatbot import query_chatbot, ChatRequest

class FakeChatbotCollection:
    def __init__(self, items=None):
        self.items = items or []

    async def count_documents(self, filter_dict):
        return len(self.items)

    async def distinct(self, key):
        return list(set(item.get(key) for item in self.items if item.get(key) is not None))

    def find(self, query=None):
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
        return AsyncCursor(self.items)

    async def find_one(self, query, sort=None):
        if not self.items:
            return None
        items = list(self.items)
        if sort:
            for field, direction in sort:
                items.sort(key=lambda x: x.get(field, 0), reverse=(direction == -1))
        return items[0]

class FakeDb(dict):
    pass

def test_chatbot_date_of_last_sales_order_admin():
    db = FakeDb({
        "sales_orders": FakeChatbotCollection([
            {"id": 100, "order_date": "01/01/2024", "status": "CLOSED"},
            {"id": 200, "order_date": "12/26/2024 19:38", "status": "CLOSED"},
            {"id": 150, "order_date": "06/06/2024", "status": "CLOSED"},
        ]),
        "anomalies": FakeChatbotCollection(),
        "products": FakeChatbotCollection(),
        "client": FakeChatbotCollection(),
        "insights": FakeChatbotCollection(),
        "purchases": FakeChatbotCollection(),
        "kpis": FakeChatbotCollection(),
    })

    request = ChatRequest(message="tell me the date of our last sales order")
    result = asyncio.run(query_chatbot(request, language="en", db=db, current_admin={"role": "admin"}))

    assert "12/26/2024" in result["response"]
    assert "19:38" in result["response"]
    assert "[SO #200](http://localhost:4200/sales-order?orderId=200)" in result["response"]


def test_chatbot_date_of_last_sales_order_french():
    db = FakeDb({
        "sales_orders": FakeChatbotCollection([
            {"id": 300, "order_date": "11/11/2024", "status": "CLOSED"},
        ]),
        "anomalies": FakeChatbotCollection(),
        "products": FakeChatbotCollection(),
        "client": FakeChatbotCollection(),
        "insights": FakeChatbotCollection(),
        "purchases": FakeChatbotCollection(),
        "kpis": FakeChatbotCollection(),
    })

    request = ChatRequest(message="la date de la dernière commande")
    result = asyncio.run(query_chatbot(request, language="fr", db=db, current_admin={"role": "admin"}))

    assert "11/11/2024" in result["response"]
    assert "[SO #300](http://localhost:4200/sales-order?orderId=300)" in result["response"]


def test_chatbot_linked_supplier_for_sales_order():
    db = FakeDb({
        "sales_orders": FakeChatbotCollection([
            {
                "id": 24650,
                "order_date": "12/26/2024 19:38",
                "status": "SUSPECTED_FRAUD",
                "total_sales": 13198.08,
                "order_profit": 67.84,
                "order_lines": [{"product_sku": 858, "quantity": 12}]
            }
        ]),
        "anomalies": FakeChatbotCollection(),
        "products": FakeChatbotCollection([{"sku": 858, "name": "Running Shoes", "category": "Footwear", "price": 199.99}]),
        "client": FakeChatbotCollection(),
        "insights": FakeChatbotCollection(),
        "purchases": FakeChatbotCollection([
            {
                "id": "PURCH-01",
                "Supplier": "Nike Manufacturing EU",
                "purchase_lines": [{"product_sku": 858, "quantity": 100}]
            }
        ]),
        "kpis": FakeChatbotCollection(),
    })

    request = ChatRequest(message="The sales order SO #24650 which supplier is linked to it")
    result = asyncio.run(query_chatbot(request, language="en", db=db, current_admin={"role": "admin"}))

    assert "Nike Manufacturing EU" in result["response"]
    assert "24650" in result["response"]
    assert "http://localhost:4200/sales-order?orderId=24650" in result["response"]
