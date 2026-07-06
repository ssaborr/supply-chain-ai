from pymongo import MongoClient
from app.core.config import settings

client = MongoClient(settings.MONGODB_URI)
db = client[settings.DATABASE_NAME]

collections = ['admin', 'client', 'departments', 'products', 'sales_orders', 'anomalies', 'kpis', 'insights', 'purchases', 'forecasts']

print("=== Database Collections Summary ===\n")
for col in collections:
    count = db[col].count_documents({})
    print(f"{col}: {count} documents")
    if count > 0:
        sample = db[col].find_one({})
        if col == 'sales_orders':
            print(f"  Sample: id={sample.get('id')}, client={sample.get('client_id')}, order_lines={len(sample.get('order_lines', []))}")
        elif col == 'purchases':
            print(f"  Sample: id={sample.get('id')}, supplier={sample.get('Supplier')}, purchase_lines={len(sample.get('purchase_lines', []))}")
        elif col == 'insights':
            print(f"  Sample: name={sample.get('name')}, verdict={sample.get('verdict')}, category={sample.get('category')}")
        elif col == 'anomalies':
            print(f"  Sample: type={sample.get('type')}, anomaly={sample.get('anomaly')}")
        else:
            print(f"  Sample fields: {list(sample.keys())[:5]}")
    print()
