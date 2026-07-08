import os
import pickle
import logging
import pandas as pd

logger = logging.getLogger("anomaly_sync")

LGB_MODEL_DATA = None
LGB_MODEL_MTIME = 0

def load_lgb_model():
    global LGB_MODEL_DATA, LGB_MODEL_MTIME
    model_path = r"c:\Users\Sabor\Desktop\project\processed_data\lgb_anomaly_model.pkl"
    if os.path.exists(model_path):
        try:
            mtime = os.path.getmtime(model_path)
            if LGB_MODEL_DATA is None or mtime > LGB_MODEL_MTIME:
                with open(model_path, "rb") as f:
                    LGB_MODEL_DATA = pickle.load(f)
                LGB_MODEL_MTIME = mtime
                logger.info("Successfully loaded/reloaded LightGBM anomaly model for background synchronization.")
        except Exception as e:
            logger.error(f"Failed to load LGB model: {e}")
    return LGB_MODEL_DATA

async def sync_anomalies_to_db(db):
    logger.info("Starting asynchronous anomaly database synchronization...")
    model_data = load_lgb_model()
    if not model_data:
        logger.warning("LightGBM anomaly model could not be loaded. Setting delay anomalies based on delay thresholds only.")
    
    try:
        # Load products for category and discounts
        products_map = {
            int(p["sku"]): {
                "category": p.get("category", "Unknown"),
                "discount": p.get("discount", 0.0)
            }
            async for p in db["products"].find()
        }
        
        cursor = db["sales_orders"].find({})
        count = 0
        async for doc in cursor:
            lines = doc.get("order_lines", [])
            total_quantity = sum(line.get("quantity", 0) for line in lines)
            total_sales = sum(line.get("quantity", 0) * line.get("unitPrice", 0.0) for line in lines) or (doc.get("order_profit", 0.0) / 0.15 if doc.get("order_profit", 0.0) != 0 else 100.0)
            profit_margin = doc.get("order_profit", 0.0) / total_sales if total_sales != 0 else 0.0
            
            discounts = [products_map[l["product_sku"]]["discount"] for l in lines if l.get("product_sku") in products_map]
            discount_ratio = sum(discounts) / len(discounts) if discounts else 0.0
            
            delay_delta = doc.get("real_shipment", 0) - doc.get("scheduled_shipment", 0)
            is_lgb_fraud = 0
            if model_data:
                try:
                    features = pd.DataFrame(
                        [[float(delay_delta), float(total_quantity), float(total_sales), float(profit_margin), float(discount_ratio)]],
                        columns=model_data["features"]
                    )
                    is_lgb_fraud = int(model_data["model"].predict(features)[0])
                except Exception:
                    pass
            
            anomaly_status = "unusual" if (is_lgb_fraud == 1 or doc.get("status") == "SUSPECTED_FRAUD") else ("delay anomaly" if delay_delta > 3 else "valid")
            
            await db["sales_orders"].update_one(
                {"_id": doc["_id"]},
                {"$set": {
                    "anomaly_status": anomaly_status,
                    "delay_delta": delay_delta,
                    "total_quantity": total_quantity,
                    "total_sales": round(total_sales, 2),
                    "profit_margin": round(profit_margin, 4),
                    "discount_ratio": round(discount_ratio, 4)
                }}
            )
            
            # Sync anomalies
            if anomaly_status != "valid":
                anomaly_type = "fraud" if anomaly_status == "unusual" else "delay"
                anomaly_name = "Suspected Transaction Fraud" if anomaly_type == "fraud" else "Critical Shipping Delay"
                anomaly_score = -0.88 if anomaly_type == "fraud" else float(-0.1 * delay_delta)
                anomaly_desc = f"Fraud warning triggered on payment status: {doc.get('status')}." if anomaly_type == "fraud" else f"Shipping took {doc.get('real_shipment')} days vs promised {doc.get('scheduled_shipment')} days."
                
                # Avoid duplicate anomalies
                exists = await db["anomalies"].find_one({"sales_order_id": doc["id"]})
                if not exists:
                    await db["anomalies"].insert_one({
                        "anomaly": anomaly_name,
                        "score": anomaly_score,
                        "type": anomaly_type,
                        "timestamp": doc.get("order_date"),
                        "description": anomaly_desc,
                        "sales_order_id": doc["id"]
                    })
            
            count += 1
            
        logger.info(f"Asynchronous anomaly sync successfully completed. Synced {count} orders.")
    except Exception as e:
        logger.error(f"Error during background anomaly database sync: {e}")
