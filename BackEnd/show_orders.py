from pymongo import MongoClient
from app.core.config import settings

client = MongoClient(settings.MONGODB_URI)
db = client[settings.DATABASE_NAME]

print("=== Sample Sales Orders with Line Items ===\n")

orders = db["sales_orders"].find().limit(5)

for order in orders:
    print(f"Order ID: {order['id']}")
    print(f"  Client: {order['client_id']}")
    print(f"  Order Date: {order['order_date']}")
    print(f"  Status: {order['status']}")
    print(f"  Profit: ${order['order_profit']:.2f}")
    print(f"  Total Line Items: {len(order['order_lines'])}")
    
    for idx, line in enumerate(order['order_lines'], 1):
        total = line['quantity'] * line['unitPrice']
        print(f"    Line {idx}: SKU {line['product_sku']} | Qty: {line['quantity']} x ${line['unitPrice']:.2f} = ${total:.2f}")
    print()

print(f"\nTotal Sales Orders in DB: {db['sales_orders'].count_documents({})}")
print("\nRun 'python seed_db.py' to refresh and populate all collections with this updated order_lines logic.")