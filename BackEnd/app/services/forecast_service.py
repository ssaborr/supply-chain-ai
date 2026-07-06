import os
import asyncio
import logging
from typing import Optional
import numpy as np
import pandas as pd
from prophet import Prophet
from prophet.serialize import model_to_json
from pymongo import UpdateOne

logger = logging.getLogger(__name__)

def get_model_path() -> str:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
    return os.path.join(project_root, "processed_data", "prophet_model.json")

# Lock to avoid concurrent retraining per product
_product_locks = {}
_lock_registry_lock = asyncio.Lock()

async def _get_product_lock(product_id: Optional[int]) -> asyncio.Lock:
    async with _lock_registry_lock:
        if product_id not in _product_locks:
            _product_locks[product_id] = asyncio.Lock()
        return _product_locks[product_id]

async def retrain_demand_forecast(db, product_id: Optional[int] = None):
    lock = await _get_product_lock(product_id)
    await lock.acquire()
    try:
        logger.info(f"Starting Prophet model retraining for product_id={product_id} in background task...")
        
        # Fetch records where sales is not null
        query = {"sales": {"$ne": None}}
        if product_id is not None:
            if product_id == 0:
                query["product_id"] = {"$ne": 0}
            else:
                query["product_id"] = product_id
            
        cursor = db["forecasts"].find(query)
        records = []
        async for doc in cursor:
            records.append(doc)
            
        if len(records) < 2:
            logger.warning(f"Not enough historical data in forecasts collection to train Prophet for product_id={product_id} (need at least 2 points).")
            return
            
        if product_id == 0:
            # Aggregate daily sales across active reporting products (>= 5 active)
            from collections import defaultdict
            date_to_products = defaultdict(set)
            date_to_sales = defaultdict(float)
            for r in records:
                d_str = r["date"]
                date_to_products[d_str].add(r["product_id"])
                date_to_sales[d_str] += float(r["sales"])
                
            valid_dates = [d for d, prods in date_to_products.items() if len(prods) >= 5]
            df = pd.DataFrame([{
                "ds": pd.to_datetime(d),
                "y": date_to_sales[d]
            } for d in valid_dates])
        else:
            df = pd.DataFrame([{
                "ds": pd.to_datetime(r["date"]),
                "y": float(r["sales"])
            } for r in records])
        
        df = df.sort_values(by="ds").reset_index(drop=True)
        df = df.groupby("ds").agg({"y": "sum"}).reset_index()

        # Store aggregate demand historical sales under product_id=0
        if product_id == 0:
            logger.info("Upserting aggregated historical sales into forecasts collection...")
            await db["forecasts"].delete_many({"product_id": 0})
            hist_docs = []
            for _, row in df.iterrows():
                date_str = row['ds'].strftime('%Y-%m-%d')
                sales_val = float(row['y'])
                hist_docs.append({
                    "date": date_str,
                    "sales": sales_val,
                    "forecast": sales_val * 0.95,
                    "product_id": 0
                })
            if hist_docs:
                await db["forecasts"].insert_many(hist_docs)
        
        # Keep up to 365 days of history for per-product models (enough for yearly seasonality)
        # Global (product_id=0) always keeps full history
        if product_id != 0 and len(df) > 365:
            logger.info(f"Limiting historical records from {len(df)} to the most recent 365 days.")
            df = df.tail(365).reset_index(drop=True)
        
        # Log-transform y to stabilize variance and prevent negatives
        df["y"] = df["y"].clip(lower=0.0)
        df["y"] = np.log1p(df["y"])
        
        # Fit Prophet model in background thread
        logger.info(f"Fitting Prophet model on {len(df)} records for product_id={product_id}...")
        days_span = (df['ds'].max() - df['ds'].min()).days if len(df) > 1 else 0
        
        # Seasonality checks based on data span
        # 365 days gives Prophet enough data to model a yearly cycle
        yearly_seas = bool(len(df) >= 30 and days_span >= 365)
        weekly_seas = bool(len(df) >= 10 and days_span >= 14)
        
        logger.info(f"Training parameters for product_id={product_id}: history_len={len(df)}, days_span={days_span}, yearly_seasonality={yearly_seas}, weekly_seasonality={weekly_seas}")
        
        # Disable uncertainty samples for speedup
        model = Prophet(
            yearly_seasonality=yearly_seas,
            weekly_seasonality=weekly_seas,
            daily_seasonality=False,
            changepoint_prior_scale=0.05,
            seasonality_prior_scale=10.0,
            uncertainty_samples=0
        )
        
        await asyncio.to_thread(model.fit, df[['ds', 'y']])
        
        # Save serialized Prophet model
        model_path = get_model_path()
        if product_id is not None:
            model_path = model_path.replace("prophet_model.json", f"prophet_model_{product_id}.json")
            
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        model_json = model_to_json(model)
        with open(model_path, 'w') as f:
            f.write(model_json)
        logger.info(f"Prophet model successfully serialized and saved to {model_path}")
        
        # Predict up to 2017-12-31
        max_hist_date = df['ds'].max()
        target_end_date = pd.to_datetime("2017-12-31")
        if max_hist_date < target_end_date:
            periods = max(92, int((target_end_date - max_hist_date).days) + 5)
        else:
            periods = 92  # guarantee a full 3-month future window
            
        future_df = model.make_future_dataframe(periods=periods, include_history=False)
        forecast = model.predict(future_df)
        
        # Inverse transform back to original scale
        forecast['yhat'] = np.expm1(forecast['yhat']).clip(lower=0.0)
        
        # Build future forecast docs
        new_future_docs = []
        for _, row in forecast.iterrows():
            date_str = row['ds'].strftime('%Y-%m-%d')
            yhat_val = float(row['yhat'])
            new_future_docs.append({
                "date": date_str,
                "product_id": int(product_id),
                "sales": None,
                "forecast": yhat_val
            })
            
        await db["forecasts"].delete_many({"sales": None, "product_id": product_id})
        
        if new_future_docs:
            await db["forecasts"].insert_many(new_future_docs)
            
        logger.info(f"Prophet model retraining and forecast database update completed successfully for product_id={product_id}.")
        
    except Exception as e:
        logger.error(f"Error during Prophet model retraining: {e}", exc_info=True)
    finally:
        lock.release()

async def generate_forecast_explanation(db, product_id: int) -> str:
    import math
    import httpx
    
    try:
        # Ensure at least 90 future forecasts exist
        future_count = await db["forecasts"].count_documents({"product_id": product_id, "sales": None})
        if future_count < 90:
            hist_count = await db["forecasts"].count_documents({"product_id": product_id, "sales": {"$ne": None}})
            if hist_count >= 2:
                logger.info(f"Fewer than 90 future predictions found for product_id={product_id} (count={future_count}) during explanation request. Triggering retraining...")
                await retrain_demand_forecast(db, product_id)

        product = await db["products"].find_one({"sku": product_id})
        if not product:
            return "Product not found."
        
        product_name = product.get("name", "Unknown Product")
        
        # Fetch history and forecasts for Sep-Dec 2017 window
        query = {
            "product_id": product_id,
            "date": {"$gte": "2017-09-01", "$lte": "2017-12-31"}
        }
        cursor = db["forecasts"].find(query).sort("date", 1)
        records = []
        async for doc in cursor:
            records.append(doc)
            
        historical = [r for r in records if r.get("sales") is not None]
        if not historical:
            overall_cursor = db["forecasts"].find({
                "product_id": product_id,
                "sales": {"$ne": None}
            }).sort("date", -1).limit(60)
            async for doc in overall_cursor:
                historical.append(doc)
                
        future = [r for r in records if r.get("sales") is None]
        
        if not historical:
            return f"Historical daily demand data for {product_name} in the Sep-Dec 2017 window is currently empty."
            
        hist_sales = [r["sales"] for r in historical]
        hist_mean = sum(hist_sales) / len(hist_sales)
        
        if not future:
            return f"Historical daily demand for {product_name} averages {hist_mean:.0f} units in Sep 2017. No forecast is loaded for the Oct-Dec 2017 window."

        forecast_values = [r["forecast"] for r in future]
        forecast_mean = sum(forecast_values) / len(forecast_values)
        
        peak_idx = forecast_values.index(max(forecast_values))
        peak_forecast = forecast_values[peak_idx]
        peak_date = future[peak_idx]["date"]
        
        mean = forecast_mean
        variance = sum((x - mean) ** 2 for x in forecast_values) / len(forecast_values)
        stddev = math.sqrt(variance)
        
        stockout_threshold = mean + 1.7 * stddev if stddev > 0 else float('inf')
        high_demand_threshold = mean + 1.2 * stddev if stddev > 0 else float('inf')
        
        has_stockout = any(f > stockout_threshold for f in forecast_values)
        has_high_demand = any(f > high_demand_threshold for f in forecast_values)
        
        ollama_url = "http://localhost:11434/api/generate"
        
        prompt = (
            f"You are a supply chain AI analyst. Explain the demand forecast for: {product_name} (ID: {product_id}) within the 3-month window (Sep 2017 - Dec 2017).\n"
            f"- Historical average daily sales (Sep 2017): {hist_mean:.0f} units.\n"
            f"- Forecasted average daily demand (Oct-Dec 2017): {forecast_mean:.0f} units.\n"
            f"- Peak forecasted daily demand: {peak_forecast:.0f} units on {peak_date}.\n"
            f"- Stockout Risk: {'HIGH' if has_stockout else 'NORMAL'}.\n"
            f"- High Demand Expected: {'YES' if has_high_demand else 'NO'}.\n\n"
            f"Write a concise 2-3 sentence explanation for the supply chain manager. "
            f"Explain what the forecast indicates about future demand, whether a stockout is expected, and what actionable replenishment steps they should take. "
            f"Be direct and professional. Do NOT use bullet points, markdown list syntax, or introductory greetings (like 'Here is...'). Use the provided numbers."
        )
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(ollama_url, json={
                    "model": "qwen2.5:7b",
                    "prompt": prompt,
                    "stream": False
                })
                
                if response.status_code == 200:
                    insights = response.json().get("response", "").strip()
                    if insights:
                        return insights
        except Exception as err:
            logger.warning(f"Ollama local LLM connection failed: {err}. Falling back to template explanation.")
            
        # Fallback explanation
        if has_stockout:
            return (
                f"The Prophet model predicts a critical demand spike of up to {peak_forecast:.0f} units on {peak_date}, "
                f"which exceeds the safety stock threshold relative to your historical daily average of {hist_mean:.0f} units. "
                f"We recommend increasing current inventory levels immediately to avoid stockout for SKU #{product_id}."
            )
        elif has_high_demand:
            return (
                f"A period of elevated demand is expected, peaking at {peak_forecast:.0f} units on {peak_date} "
                f"(historical average is {hist_mean:.0f} units). Supply chain efficiency is stable, but we recommend "
                f"monitoring supplier lead times to support this temporary increase in volume."
            )
        else:
            return (
                f"Future demand for {product_name} is projected to be stable, averaging {forecast_mean:.0f} units per day "
                f"which aligns with the historical baseline of {hist_mean:.0f} units. Current stock levels are sufficient "
                f"and no stockouts are anticipated over the next 30 days."
            )
            
    except Exception as e:
        logger.error(f"Error generating forecast explanation: {e}", exc_info=True)
        return "Unable to generate forecast explanation due to an internal error."
