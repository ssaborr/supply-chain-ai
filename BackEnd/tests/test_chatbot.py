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

@pytest.mark.asyncio
async def test_chatbot_date_of_last_sales_order_admin():
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
    result = await query_chatbot(request, language="en", db=db, current_admin={"role": "admin"})

    assert "12/26/2024" in result["response"]
    assert "19:38" in result["response"]
    assert "[SO #200](http://localhost:4200/sales-order?orderId=200)" in result["response"]


@pytest.mark.asyncio
async def test_chatbot_date_of_last_sales_order_french():
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
    result = await query_chatbot(request, language="fr", db=db, current_admin={"role": "admin"})

    assert "11/11/2024" in result["response"]
    assert "[SO #300](http://localhost:4200/sales-order?orderId=300)" in result["response"]
