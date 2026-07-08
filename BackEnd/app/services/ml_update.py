import os
import sys
import logging
import subprocess
import asyncio
import numpy as np
import pandas as pd
from datetime import datetime
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger("ml_update")

def get_paths():
    project_root = r"c:\Users\Sabor\Desktop\project"
    processed_dir = os.path.join(project_root, "processed_data")
    os.makedirs(processed_dir, exist_ok=True)
    return {
        "project_root": project_root,
        "processed_dir": processed_dir,
        "anomaly_raw": os.path.join(processed_dir, "anomaly_features_raw.csv"),
        "anomaly_scaled": os.path.join(processed_dir, "anomaly_features_scaled.csv"),
        "rfm_raw": os.path.join(processed_dir, "rfm_features_raw.csv"),
        "rfm_scaled": os.path.join(processed_dir, "rfm_features_scaled.csv"),
        "product_demand": os.path.join(processed_dir, "product_daily_demand.csv"),
        "global_demand": os.path.join(processed_dir, "global_daily_demand.csv"),
        "product_features": os.path.join(processed_dir, "product_ml_features.csv")
    }

async def rebuild_ml_datasets_from_db(db):
    logger.info("Rebuilding ML datasets from MongoDB...")
    paths = get_paths()
    
    # 1. Load products mapping
    products_map = {}
    async for p in db["products"].find():
        sku = int(p["sku"])
        products_map[sku] = {
            "name": p.get("name", f"SKU {sku}"),
            "price": float(p.get("price", 0.0)),
            "discount": float(p.get("discount", 0.0)),
            "category": p.get("category", "Unknown"),
            "department_id": p.get("department_id", "0")
        }
        
    # 2. Retrieve sales orders
    orders = []
    async for doc in db["sales_orders"].find():
        orders.append(doc)
        
    if not orders:
        logger.warning("No sales orders in database. Skipping dataset generation.")
        return
        
    # 3. Process Anomaly Features
    anomaly_records = []
    item_rows = []
    
    for doc in orders:
        lines = doc.get("order_lines", [])
        if not lines:
            continue
            
        total_quantity = sum(line.get("quantity", 0) for line in lines)
        total_sales = sum(line.get("quantity", 0) * line.get("unitPrice", 0.0) for line in lines) or (doc.get("order_profit", 0.0) / 0.15 if doc.get("order_profit", 0.0) != 0 else 100.0)
        profit_margin = doc.get("order_profit", 0.0) / total_sales if total_sales != 0 else 0.0
        
        delay_delta = doc.get("real_shipment", 0) - doc.get("scheduled_shipment", 0)
        
        discounts = [products_map[l["product_sku"]]["discount"] for l in lines if l.get("product_sku") in products_map]
        discount_ratio = sum(discounts) / len(discounts) if discounts else 0.0
        
        is_fraud = 1 if doc.get("status") == "SUSPECTED_FRAUD" else 0
        
        anomaly_records.append({
            'delay_delta': float(delay_delta),
            'Order Item Quantity': float(total_quantity),
            'Sales': float(total_sales),
            'profit_margin': float(profit_margin),
            'discount_ratio': float(discount_ratio),
            'is_fraud': int(is_fraud)
        })
        
        # We also unpack items for daily demand forecasting datasets
        order_date_parsed = pd.to_datetime(doc.get("order_date"), errors='coerce')
        if pd.isna(order_date_parsed):
            continue
            
        for line in lines:
            sku = int(line.get("product_sku"))
            qty = int(line.get("quantity", 0))
            price = float(line.get("unitPrice", 0.0))
            sku_info = products_map.get(sku, {})
            
            item_rows.append({
                "product_id": sku,
                "product_name": sku_info.get("name", f"SKU {sku}"),
                "order_date_parsed": order_date_parsed,
                "quantity": qty,
                "sales_value": qty * price,
                "delay_delta": delay_delta,
                "price": price
            })
            
    df_anomaly = pd.DataFrame(anomaly_records)
    df_anomaly.to_csv(paths["anomaly_raw"], index=False)
    
    # Scale anomaly features
    anomaly_cols = ['delay_delta', 'Order Item Quantity', 'Sales', 'profit_margin', 'discount_ratio']
    if len(df_anomaly) > 1:
        scaler = StandardScaler()
        X_scaled = pd.DataFrame(
            scaler.fit_transform(df_anomaly[anomaly_cols]),
            columns=anomaly_cols
        )
        X_scaled['is_fraud'] = df_anomaly['is_fraud'].values
        X_scaled.to_csv(paths["anomaly_scaled"], index=False)
    else:
        df_anomaly.to_csv(paths["anomaly_scaled"], index=False)
        
    # 4. Customer RFM Segmentation
    df_items = pd.DataFrame(item_rows)
    rfm_records = []
    
    # Group by customer id
    customers = {}
    for doc in orders:
        c_id = doc.get("client_id")
        if not c_id:
            continue
        order_date_parsed = pd.to_datetime(doc.get("order_date"), errors='coerce')
        if pd.isna(order_date_parsed):
            continue
        lines = doc.get("order_lines", [])
        total_sales = sum(line.get("quantity", 0) * line.get("unitPrice", 0.0) for line in lines)
        
        if c_id not in customers:
            customers[c_id] = {"dates": [], "sales": 0.0, "order_count": 0}
        
        customers[c_id]["dates"].append(order_date_parsed)
        customers[c_id]["sales"] += total_sales
        customers[c_id]["order_count"] += 1

    if customers:
        all_dates = []
        for c in customers.values():
            all_dates.extend(c["dates"])
        snapshot_date = max(all_dates) if all_dates else datetime.now()
        
        for c_id, data in customers.items():
            last_order = max(data["dates"])
            recency = (snapshot_date - last_order).days
            frequency = data["order_count"]
            monetary = data["sales"]
            
            rfm_records.append({
                "Customer Id": int(c_id),
                "Recency": float(recency),
                "Frequency": float(frequency),
                "Monetary": float(monetary)
            })
            
            # Update customer RFM score in MongoDB client collection
            rfm_score = min(100.0, float(monetary / 250.0))
            await db["client"].update_one(
                {"id": str(c_id)},
                {"$set": {"rfm_score": rfm_score}}
            )
            
        df_rfm = pd.DataFrame(rfm_records)
        df_rfm.to_csv(paths["rfm_raw"], index=False)
        
        if len(df_rfm) > 1:
            scaler_rfm = StandardScaler()
            rfm_scaled = pd.DataFrame(
                scaler_rfm.fit_transform(df_rfm[['Recency', 'Frequency', 'Monetary']]),
                columns=['Recency_scaled', 'Frequency_scaled', 'Monetary_scaled']
            )
            rfm_scaled['Customer Id'] = df_rfm['Customer Id']
            rfm_scaled.to_csv(paths["rfm_scaled"], index=False)
        else:
            df_rfm.to_csv(paths["rfm_scaled"], index=False)
            
    # 5. Product daily demand & Global daily demand
    if not df_items.empty:
        # Product daily demand
        df_items['ds'] = df_items['order_date_parsed'].dt.date
        prod_demand = df_items.groupby(['product_id', 'product_name', 'ds']).agg(
            y=('quantity', 'sum'),
            sales_volume=('sales_value', 'sum')
        ).reset_index()
        prod_demand.to_csv(paths["product_demand"], index=False)
        
        # Global daily demand
        global_demand = df_items.groupby('ds').agg(
            y=('quantity', 'sum'),
            sales_volume=('sales_value', 'sum')
        ).reset_index()
        global_demand.to_csv(paths["global_demand"], index=False)
        
        # 6. Product ML features (for safety stock)
        prod_stats = df_items.groupby('product_id').agg(
            demand_mean=('quantity', 'mean'),
            demand_std=('quantity', 'std'),
            avg_lead_time=('delay_delta', 'mean'),
            price=('price', 'first')
        ).reset_index()
        
        prod_stats['demand_std'] = prod_stats['demand_std'].fillna(0)
        prod_stats['demand_cv'] = np.where(
            prod_stats['demand_mean'] > 0,
            prod_stats['demand_std'] / prod_stats['demand_mean'],
            0
        )
        prod_stats.rename(columns={'product_id': 'Product Card Id'}, inplace=True)
        prod_stats.to_csv(paths["product_features"], index=False)
        
    logger.info("Successfully rebuilt all ML datasets from DB.")

async def run_subprocess_async(cmd_args):
    process = await asyncio.create_subprocess_exec(
        *cmd_args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        err_msg = stderr.decode()
        logger.error(f"Command {' '.join(cmd_args)} failed with exit code {process.returncode}: {err_msg}")
        raise RuntimeError(f"Subprocess failed: {err_msg}")
    logger.info(f"Command {' '.join(cmd_args)} completed successfully.")
    return stdout.decode()

async def retrain_all_models_task(db):
    logger.info("Starting background task: Rebuilding datasets & Retraining all ML models...")
    try:
        # Step 1: Rebuild datasets
        await rebuild_ml_datasets_from_db(db)
        
        # Step 2: Get python executable
        python_bin = sys.executable
        paths = get_paths()
        
        # Retrain KMeans
        kmeans_script = os.path.join(paths["project_root"], "train_kmeans.py")
        if os.path.exists(kmeans_script):
            logger.info("Retraining KMeans product clusters...")
            await run_subprocess_async([python_bin, kmeans_script])
        
        # Retrain KNN
        knn_script = os.path.join(paths["project_root"], "train_knn_optimized.py")
        if os.path.exists(knn_script):
            logger.info("Retraining KNN fraud detector...")
            await run_subprocess_async([python_bin, knn_script])
            
        # Retrain LightGBM
        lgb_script = os.path.join(paths["project_root"], "train_lgb_optimized.py")
        if os.path.exists(lgb_script):
            logger.info("Retraining LightGBM fraud detector...")
            await run_subprocess_async([python_bin, lgb_script])
            
        # Retrain ARIMA Global demand forecast
        global_forecast_script = os.path.join(paths["project_root"], "BackEnd", "train_global.py")
        if os.path.exists(global_forecast_script):
            logger.info("Retraining ARIMA global demand forecast...")
            await run_subprocess_async([python_bin, global_forecast_script])
            
        # Retrain ARIMA for Top 5 Products
        # Find top 5 product SKUs by sales volume from the database
        pipeline = [
            {"$unwind": "$order_lines"},
            {"$group": {"_id": "$order_lines.product_sku", "total_sales": {"$sum": "$order_lines.quantity"}}},
            {"$sort": {"total_sales": -1}},
            {"$limit": 5}
        ]
        
        top_skus = []
        async for doc in db["sales_orders"].aggregate(pipeline):
            top_skus.append(doc["_id"])
            
        from app.services.forecast_service import retrain_demand_forecast
        for sku in top_skus:
            logger.info(f"Retraining ARIMA forecast for product SKU {sku}...")
            await retrain_demand_forecast(db, int(sku))
            
        # Sync anomaly statuses to sales orders in DB using the newly trained LightGBM model
        from app.services.anomaly_sync import sync_anomalies_to_db
        logger.info("Syncing newly calculated anomaly statuses to DB...")
        await sync_anomalies_to_db(db)
        
        logger.info("ML and Forecasting retraining pipeline completed successfully.")
        
    except Exception as e:
        logger.error(f"Error during ML model retraining: {e}", exc_info=True)
        raise e
