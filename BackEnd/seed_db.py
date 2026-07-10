import os
import csv
import logging
import random
import numpy as np
import pandas as pd
from prophet import Prophet
from prophet.serialize import model_to_json
from pymongo import MongoClient
from app.core.security import get_password_hash
from app.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed_db")

def seed_database():
    logger.info("Initializing database seeding with updated Class Diagram structure...")
    client = MongoClient(settings.MONGODB_URI)
    db = client[settings.DATABASE_NAME]

    # --- 1. Seed 'admin' Collection ---
    logger.info("Seeding admin collection...")
    db["admin"].delete_many({})
    admins = [
        {
            "email": "admin@supplychain.com",
            "first_name": "System",
            "last_name": "Admin",
            "role": "admin",
            "hashed_password": get_password_hash("admin123")
        },
        {
            "email": "manager@supplychain.com",
            "first_name": "Supply",
            "last_name": "Manager",
            "role": "admin",
            "hashed_password": get_password_hash("manager123")
        },
        {
            "email": "supplier@supplychain.com",
            "first_name": "Supplier",
            "last_name": "Partner",
            "role": "supplier",
            "supplier_name": "Nike Manufacturing EU",
            "hashed_password": get_password_hash("supplier123")
        }
    ]
    db["admin"].insert_many(admins)

    # --- 2. Seed 'client' Collection (rfm_score included) ---
    rfm_path = r"c:\Users\Sabor\Desktop\project\processed_data\rfm_features_raw.csv"
    client_ids = []
    if os.path.exists(rfm_path):
        logger.info(f"Loading client RFM data from {rfm_path}...")
        db["client"].delete_many({})
        client_docs = []
        first_names = ["Jean", "Pierre", "Michel", "Andre", "Philippe", "Rene", "Louis", "Jacques", "Alain", "Marie"]
        last_names = ["Martin", "Bernard", "Thomas", "Petit", "Robert", "Richard", "Durand", "Dubois", "Moreau", "Laurent"]
        countries = ["France", "Germany", "Spain", "Italy", "United Kingdom", "United States"]
        categories = ["Aviation", "Automotive", "Military", "Commercial"]

        with open(rfm_path, mode='r', encoding='latin-1') as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                if count >= 100:
                    break
                try:
                    c_id = int(float(row["Customer Id"]))
                    client_ids.append(c_id)
                    fn = random.choice(first_names)
                    ln = random.choice(last_names)
                    email = f"{fn.lower()}.{ln.lower()}{c_id}@supplychain-client.com"
                    
                    monetary = float(row["Monetary"])
                    rfm_score = min(100.0, float(monetary / 250.0))

                    client_docs.append({
                        "id": str(c_id),
                        "first_name": fn,
                        "last_name": ln,
                        "email": email,
                        "password": get_password_hash("client123"),
                        "address": f"{random.randint(1, 150)} Rue de Paris",
                        "number": f"+33 6 {random.randint(10, 99)} {random.randint(10, 99)} {random.randint(10, 99)}",
                        "category": random.choice(categories),
                        "country": random.choice(countries),
                        "rfm_score": rfm_score
                    })
                    count += 1
                except Exception as ex:
                    logger.warning(f"Error parsing client RFM row: {ex}")
        if client_docs:
            db["client"].insert_many(client_docs)
            logger.info(f"Seeded {len(client_docs)} client records.")

    # --- 3. Extract and Seed 'departments' and 'products' (SKU as key) from Raw Dataset ---
    raw_dataset_path = r"c:\Users\Sabor\Desktop\project\DataCoSupplyChainDataset.csv"
    if os.path.exists(raw_dataset_path):
        logger.info("Extracting departments and products from raw dataset...")
        db["departments"].delete_many({})
        db["products"].delete_many({})

        df_raw = pd.read_csv(raw_dataset_path, encoding='latin-1')

        # Seed Departments
        df_dept = df_raw[['Department Id', 'Department Name']].drop_duplicates().dropna()
        dept_docs = []
        for _, row in df_dept.iterrows():
            d_id = str(int(row["Department Id"]))
            dept_docs.append({
                "id": d_id,
                "name": str(row["Department Name"]),
                "address": f"Zone Logistique {row['Department Name']}, Bâtiment {random.randint(1, 12)}"
            })
        if dept_docs:
            db["departments"].insert_many(dept_docs)
            logger.info(f"Seeded {len(dept_docs)} departments.")

        # Seed Products (sku, price, discount, category, current_stock, department_id)
        df_prod = df_raw[['Product Card Id', 'Product Name', 'Product Price', 'Order Item Discount Rate', 'Category Name', 'Department Id']].drop_duplicates(subset=['Product Card Id']).dropna()
        product_docs = []
        for _, row in df_prod.iterrows():
            product_docs.append({
                "sku": int(row["Product Card Id"]),
                "name": str(row["Product Name"]),
                "price": float(row["Product Price"]),
                "discount": float(row["Order Item Discount Rate"]),
                "category": str(row["Category Name"]),
                "current_stock": random.randint(50, 500),
                "department_id": str(int(row["Department Id"]))
            })
        if product_docs:
            db["products"].insert_many(product_docs)
            logger.info(f"Seeded {len(product_docs)} products.")

        # --- 4. Seed 'sales_orders' and 'anomalies' ---
        logger.info("Extracting transactional sales orders and anomalies...")
        db["sales_orders"].delete_many({})
        db["anomalies"].delete_many({})

        # Take a subset of orders (first 1000 rows representing unique transactions)
        df_orders_subset = df_raw.head(2000).copy()
        
        # Group by Order Id
        order_groups = df_orders_subset.groupby('Order Id')
        order_docs = []
        anomaly_docs = []

        count_orders = 0
        for order_id, group in order_groups:
            if count_orders >= 500: # Limit to 500 orders
                break
            try:
                first_row = group.iloc[0]
                cust_id = str(int(first_row["Customer Id"]))
                order_date = str(first_row["order date (DateOrders)"])
                status = str(first_row["Order Status"])
                profit = float(group["Order Profit Per Order"].sum())
                
                scheduled = int(first_row["Days for shipment (scheduled)"])
                real = int(first_row["Days for shipping (real)"])
                delay = real - scheduled
                internal_delay = max(0, delay // 2)
                transport_delay = max(0, delay - internal_delay)

                # Lines - extract from group AND ensure at least 1-3 random additional products
                lines = []
                for _, row in group.iterrows():
                    lines.append({
                        "quantity": int(row["Order Item Quantity"]) * 12,
                        "unitPrice": float(row["Product Price"]),
                        "product_sku": int(row["Product Card Id"])
                    })
                
                # Add 1-3 random products to make orders more realistic
                if product_docs:
                    num_extra_items = random.randint(1, 3)
                    for _ in range(num_extra_items):
                        extra_product = random.choice(product_docs)
                        lines.append({
                            "quantity": random.randint(1, 10) * 12,
                            "unitPrice": extra_product.get("price", 50.0),
                            "product_sku": extra_product["sku"]
                        })

                order_docs.append({
                    "id": int(order_id),
                    "client_id": cust_id,
                    "order_date": order_date,
                    "status": status,
                    "order_profit": profit,
                    "scheduled_shipment": scheduled,
                    "real_shipment": real,
                    "internalDelay": internal_delay,
                    "transportDelay": transport_delay,
                    "order_lines": lines
                })

                # Check and Seed Anomalies for this order
                is_fraud = 1 if status == "SUSPECTED_FRAUD" else 0
                if is_fraud == 1:
                    anomaly_docs.append({
                        "anomaly": "Suspected Transaction Fraud",
                        "score": -0.88,
                        "type": "fraud",
                        "timestamp": order_date,
                        "description": f"Fraud warning triggered on payment status: {status}.",
                        "sales_order_id": int(order_id)
                    })
                elif delay > 3:
                    anomaly_docs.append({
                        "anomaly": "Critical Shipping Delay",
                        "score": float(-0.1 * delay),
                        "type": "delay",
                        "timestamp": order_date,
                        "description": f"Shipping took {real} days vs promised {scheduled} days.",
                        "sales_order_id": int(order_id)
                    })

                count_orders += 1
            except Exception as e:
                logger.warning(f"Error seeding order {order_id}: {e}")

        if order_docs:
            db["sales_orders"].insert_many(order_docs)
            logger.info(f"Seeded {len(order_docs)} sales orders.")
        if anomaly_docs:
            db["anomalies"].insert_many(anomaly_docs)
            logger.info(f"Seeded {len(anomaly_docs)} anomalies.")

    # --- 5. Seed 'kpis' Collection ---
    logger.info("Seeding kpis collection...")
    db["kpis"].delete_many({})
    kpis = [
        {
            "name": "OTIF (On-Time In-Full)",
            "description": "Percentage of orders shipped on time and in full quantities",
            "date": "2026-09-15",
            "value": 92.4
        },
        {
            "name": "Average Profit Margin",
            "description": "Average profit margin across active client categories",
            "date": "2026-09-15",
            "value": 15.6
        },
        {
            "name": "Inventory Turnover Rate",
            "description": "Yearly inventory turnover coefficient",
            "date": "2026-09-15",
            "value": 4.8
        }
    ]
    db["kpis"].insert_many(kpis)
    logger.info(f"Seeded {len(kpis)} general KPIs.")

    # --- 6. Seed 'insights' Collection ---
    logger.info("Seeding insights collection...")
    db["insights"].delete_many({})
    
    # Generate insights from actual sales order data
    insights = []
    
    if order_docs:
        # Sample from orders to create insights
        sample_orders = random.sample(order_docs, min(20, len(order_docs)))
        
        verdicts = ["Positive", "Negative", "Neutral", "High Risk", "Opportunity"]
        categories = ["Sales", "Forecasting", "Inventory", "Logistics", "Customer Behavior"]
        
        for idx, order in enumerate(sample_orders):
            profit = order.get("order_profit", 0)
            delay = order.get("real_shipment", 0) - order.get("scheduled_shipment", 0)
            
            # Determine verdict based on metrics
            if profit > 100:
                verdict = "Positive"
                category = "Sales"
                description = f"Order {order['id']} showed strong profitability with ${profit:.2f} profit. Product mix was optimal."
            elif delay > 3:
                verdict = "Negative"
                category = "Logistics"
                description = f"Order {order['id']} experienced {delay} days of shipping delay. Real: {order['real_shipment']} vs Scheduled: {order['scheduled_shipment']} days."
            elif profit < 0:
                verdict = "High Risk"
                category = "Sales"
                description = f"Order {order['id']} resulted in a loss of ${abs(profit):.2f}. Review pricing strategy."
            else:
                verdict = "Opportunity"
                category = "Inventory"
                description = f"Order {order['id']} represents cross-sell opportunity. Consider bundling related products."
            
            insights.append({
                "id": len(insights) + 1,
                "name": f"Order {order['id']} Analysis",
                "verdict": verdict,
                "category": category,
                "description": description,
                "timestamp": f"{order['order_date']}T{random.randint(8, 18):02d}:{random.randint(0, 59):02d}:00Z",
                "client_id": order["client_id"],
                "product_sku": order["order_lines"][0]["product_sku"] if order.get("order_lines") else None,
                "sales_order_id": order["id"]
            })
    
    if insights:
        db["insights"].insert_many(insights)
        logger.info(f"Seeded {len(insights)} insights.")

    # --- 7. Seed 'purchases' Collection ---
    logger.info("Seeding purchases collection...")
    db["purchases"].delete_many({})
    
    # Generate diverse purchase orders from various suppliers
    suppliers = [
        "Nike Manufacturing EU", "Adidas Global Supply", "Puma Distribution",
        "Zara Production Spain", "H&M Logistics", "Decathlon Sourcing",
        "Asian Manufacturing Co.", "European Textile Mills", "Premium Quality Suppliers",
        "Budget Components Ltd", "FastShip Distributors", "Eco-Friendly Suppliers"
    ]
    
    origins = [
        "Lyon Entrepôt East", "Paris Warehouse North", "Marseille Port", "Lille Hub",
        "Toulouse Distribution", "Bordeaux Logistics", "Amsterdam Port", "Rotterdam Hub",
        "Hamburg Warehouse", "Berlin Logistics Center"
    ]
    
    purchase_types = ["Standard", "Express", "Seasonal", "Emergency", "Regular", "Bulk"]
    
    purchases = []
    purchase_id = 1
    
    # Generate purchases based on product data
    if product_docs:
        for _ in range(min(50, len(product_docs))):
            purchase_date = f"2026-{random.randint(9, 12):02d}-{random.randint(1, 28):02d}"
            
            # Generate 2-5 line items per purchase
            purchase_lines = []
            num_lines = random.randint(2, 5)
            selected_products = random.sample(product_docs, min(num_lines, len(product_docs)))
            
            for selected_product in selected_products:
                sku = selected_product["sku"]
                current_stock = selected_product.get("current_stock", 100)
                
                quantity = random.randint(50, max(150, int(current_stock * 0.3)))
                unit_price = selected_product.get("price", 50.0) * random.uniform(0.55, 0.80)  # wholesale discount
                supply_delay = random.randint(3, 21)
                
                purchase_lines.append({
                    "quantity": quantity,
                    "unitPrice": unit_price,
                    "supplyDelay": supply_delay,
                    "product_sku": sku
                })
            
            purchases.append({
                "id": f"PURCH-2026-{purchase_id:03d}",
                "origin": random.choice(origins),
                "date": purchase_date,
                "type": random.choice(purchase_types),
                "lot": f"LOT-2026-{purchase_id:05d}",
                "Supplier": random.choice(suppliers),
                "purchase_lines": purchase_lines
            })
            purchase_id += 1
    
    if purchases:
        db["purchases"].insert_many(purchases)
        logger.info(f"Seeded {len(purchases)} purchase orders.")

    # --- 8. Seed 'forecasts' Collection (Daily Demand History + Prophet Pre-training) ---
    product_demand_path = r"c:\Users\Sabor\Desktop\project\processed_data\product_daily_demand.csv"
    if os.path.exists(product_demand_path):
        logger.info("Loading daily demand records for forecasting...")
        db["forecasts"].delete_many({})
        
        df_all = pd.read_csv(product_demand_path)
        df_all['ds'] = pd.to_datetime(df_all['ds'])
        
        # Apply structured demand tendencies (distinct product profiles)
        def apply_product_profile_tendencies(row):
            pid = int(row['product_id'])
            dt = row['ds']
            val = float(row['y'])
            
            rem = pid % 8
            
            if rem in [0, 4]:
                # Profile 1a: Low & Steady
                val *= 2.5
            elif rem in [2, 6]:
                # Profile 1b: High & Steady
                val *= 15.0
            elif rem in [1, 5]:
                # Profile 2: Strong weekend peaks, quiet weekdays (weekly peaks)
                wd = dt.weekday()
                if wd in [4, 5]: # Friday & Saturday
                    val *= 30.0
                else:
                    val *= 0.5
            elif rem == 3:
                # Profile 3: High demand in one specific month, low elsewhere (Sept to Dec peak)
                peak_month = 9 + (pid % 4)
                if dt.month == peak_month:
                    val *= 35.0
                else:
                    val *= 1.5
            else: # rem == 7
                # Profile 4: High baseline with high variance
                val *= 12.0
                
            return val

        df_all['y_base'] = df_all.apply(apply_product_profile_tendencies, axis=1)
        
        # Add profile-specific noise / variance
        np.random.seed(42)
        noises = []
        for idx, row in df_all.iterrows():
            pid = int(row['product_id'])
            rem = pid % 8
            if rem == 7:
                # Highly volatile random noise (high variance)
                noises.append(np.random.uniform(0.1, 2.8))
            elif rem in [0, 2, 4, 6]:
                # Steady - minimal noise (+/- 3%)
                noises.append(np.random.uniform(0.97, 1.03))
            else:
                # Normal noise
                noises.append(np.random.uniform(0.85, 1.15))
                
        df_all['y'] = (df_all['y_base'] * np.array(noises)).clip(lower=1.0).round()
        df_all.drop(columns=['y_base'], inplace=True)
        
        df_clean = df_all.groupby(['product_id', 'ds']).agg({'y': 'sum'}).reset_index()
        
        forecast_docs = []
        for _, row in df_clean.iterrows():
            forecast_docs.append({
                "date": row["ds"].strftime('%Y-%m-%d'),
                "product_id": int(row["product_id"]),
                "sales": float(row["y"]),
                "forecast": float(row["y"] * 0.95)
            })
                
        if forecast_docs:
            chunk_size = 50000
            for start_idx in range(0, len(forecast_docs), chunk_size):
                chunk = forecast_docs[start_idx:start_idx + chunk_size]
                db["forecasts"].insert_many(chunk)
            logger.info(f"Seeded {len(forecast_docs)} historical forecasting records.")
            
            # Pre-train top products
            logger.info("Pre-training Prophet models for top 5 products...")
            counts = df_all['product_name'].value_counts()
            top_products = counts.head(5).index.tolist()
            
            for name in top_products:
                df_prod = df_all[df_all['product_name'] == name].copy()
                product_id = int(df_prod['product_id'].iloc[0])
                
                df_prophet = df_prod[['ds', 'y']].sort_values(by='ds').reset_index(drop=True)
                df_prophet['y'] = np.log1p(df_prophet['y'])
                
                days_span = (df_prophet['ds'].max() - df_prophet['ds'].min()).days if len(df_prophet) > 1 else 0
                yearly_seas = True if (len(df_prophet) >= 30 and days_span >= 730) else False
                weekly_seas = True if (len(df_prophet) >= 10 and days_span >= 14) else False
                
                model = Prophet(
                    yearly_seasonality=yearly_seas,
                    weekly_seasonality=weekly_seas,
                    daily_seasonality=False,
                    uncertainty_samples=0
                )
                model.fit(df_prophet[['ds', 'y']])
                
                model_path = os.path.join(r"c:\Users\Sabor\Desktop\project\processed_data", f"prophet_model_{product_id}.json")
                with open(model_path, 'w') as f:
                    f.write(model_to_json(model))
                
                # Predict up to 2026-12-31
                max_hist_date = df_prophet['ds'].max()
                target_end_date = pd.to_datetime("2026-12-31")
                periods = max(90, int((target_end_date - max_hist_date).days) + 5)
                
                future = model.make_future_dataframe(periods=periods, include_history=False)
                forecast = model.predict(future)
                forecast['yhat'] = np.expm1(forecast['yhat']).clip(lower=0.0)
                
                future_docs = []
                for _, row_fc in forecast.iterrows():
                    future_docs.append({
                        "date": row_fc['ds'].strftime('%Y-%m-%d'),
                        "product_id": product_id,
                        "sales": None,
                        "forecast": float(row_fc['yhat'])
                    })
                
                if future_docs:
                    db["forecasts"].insert_many(future_docs)
                    logger.info(f"Pre-trained and generated forecast up to 2026-12-31 for product: {name} (ID: {product_id}).")
        logger.info("Product forecasting database seeding completed.")

    logger.info("Database seeding successfully completed.")
    
    # Run K-Means product clustering training automatically
    try:
        import sys
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
        from train_kmeans import train_and_save_kmeans
        train_and_save_kmeans()
    except Exception as e:
        logger.error(f"Failed to run K-Means product clustering post-seed: {e}")

if __name__ == "__main__":
    seed_database()
