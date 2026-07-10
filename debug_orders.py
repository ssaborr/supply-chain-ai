from pymongo import MongoClient
from datetime import datetime

# Direct MongoDB connection
client = MongoClient("mongodb://localhost:27017")
db = client["smart_supply_chain"]

# Get some sample orders
orders = list(db["sales_orders"].find().limit(5))

print("=== Sample Order Dates ===\n")
for order in orders:
    print(f"Order ID: {order['id']}")
    print(f"Order Date (raw): {order.get('order_date')} (type: {type(order.get('order_date'))})")
    
    # Try parsing
    order_date = order.get('order_date', '')
    try:
        dt = datetime.strptime(str(order_date), "%m/%d/%Y %H:%M")
        print(f"Parsed as: {dt}")
    except Exception as e:
        try:
            dt = datetime.strptime(str(order_date), "%m/%d/%Y")
            print(f"Parsed as: {dt}")
        except Exception as e2:
            print(f"Failed to parse: {e2}")
    print()

# Check how many orders would pass the month filtering
print("\n=== Checking Month Filtering ===\n")

all_orders = list(db["sales_orders"].find())
print(f"Total orders: {len(all_orders)}")

def parse_date(date_str):
    try:
        return datetime.strptime(date_str, "%m/%d/%Y %H:%M")
    except Exception:
        try:
            return datetime.strptime(date_str, "%m/%d/%Y")
        except Exception:
            return None

parsed_orders = []
for doc in all_orders:
    dt = parse_date(doc.get("order_date", ""))
    if dt:
        parsed_orders.append((doc, dt))

print(f"Successfully parsed: {len(parsed_orders)} orders")

if parsed_orders:
    parsed_orders.sort(key=lambda x: x[1])
    max_dt = parsed_orders[-1][1]
    min_dt = parsed_orders[0][1]
    
    print(f"Date range: {min_dt} to {max_dt}")
    print(f"Max date month: {max_dt.month}, year: {max_dt.year}")
    
    cur_month = max_dt.month
    cur_year = max_dt.year
    
    if cur_month == 1:
        last_month = 12
        last_year = cur_year - 1
    else:
        last_month = cur_month - 1
        last_year = cur_year
    
    orders_cur = [item[0] for item in parsed_orders if item[1].month == cur_month and item[1].year == cur_year]
    orders_last = [item[0] for item in parsed_orders if item[1].month == last_month and item[1].year == last_year]
    
    print(f"\nCurrent month ({cur_month}/{cur_year}): {len(orders_cur)} orders")
    print(f"Last month ({last_month}/{last_year}): {len(orders_last)} orders")
