import os
import asyncio
import logging
from typing import Optional
import numpy as np
import pandas as pd
from fastapi import HTTPException
from statsmodels.tsa.arima.model import ARIMA
from pymongo import UpdateOne

logger = logging.getLogger(__name__)

def get_model_path() -> str:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
    return os.path.join(project_root, "processed_data", "arima_model.pkl")

# thread lock to prevent double-training collision for the same item
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
        
        # get historical sales records
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
            # sum up daily volume if we have at least 5 reporting items
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

        # save global aggregate demand stats with product_id=0
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
        
        # trim historical tail to 365 days for individual models to capture seasonality
        # keep full history for global aggregate model
        if product_id != 0 : #hook here remeber for issues in forecast
            logger.info(f"Limiting historical records from {len(df)} to the most recent 365 days.")
      
        
        # clamp negative values, keep raw scale for peaks
        df["y"] = df["y"].clip(lower=0.0)
        
        # run ARIMA fitting in a background thread to keep backend responsive
        logger.info(f"Fitting ARIMA model on {len(df)} records for product_id={product_id}...")
        
        df_ts = df.set_index("ds")
        df_ts = df_ts.asfreq('D', fill_value=0.0)
        
        days_span = (df['ds'].max() - df['ds'].min()).days if len(df) > 1 else 0
        
        if len(df_ts) >= 14 and days_span >= 14:
            seasonal_order = (1, 0, 1, 7) # Weekly seasonality
        else:
            seasonal_order = (0, 0, 0, 0)
            
        try:
            
            model = ARIMA(df_ts["y"], order=(1, 1, 1), seasonal_order=seasonal_order)
            model_fit = await asyncio.to_thread(model.fit)
            
            # forecast out to the end of Q4 2026
            max_hist_date = df['ds'].max()
            target_end_date = pd.to_datetime("2026-12-31")
            if max_hist_date < target_end_date:
                periods = max(92, int((target_end_date - max_hist_date).days) + 5)
            else:
                periods = 92
                
            forecast_res = await asyncio.to_thread(model_fit.forecast, steps=periods)
            
            # seed random number generator deterministically for uniform forecast jitter
            np.random.seed(int(product_id) if product_id is not None else 42)
            resid_std = float(np.std(model_fit.resid)) if hasattr(model_fit, "resid") else 10.0
            noise = np.random.normal(0, resid_std * 0.4, size=len(forecast_res))
            
            weekly_pattern = np.array([1.1 if d.weekday() in [4, 5] else 0.9 for d in forecast_res.index])
            yhat_vals = (forecast_res.values * weekly_pattern + noise).tolist()
            yhat_vals = [max(0.0, v) for v in yhat_vals]
            
            forecast_df = pd.DataFrame({
                "ds": forecast_res.index,
                "yhat": yhat_vals
            })

            # serialize the model object to disk, dude
            model_path = get_model_path()
            if product_id is not None:
                model_path = model_path.replace("arima_model.pkl", f"arima_model_{product_id}.pkl")
            os.makedirs(os.path.dirname(model_path), exist_ok=True)
            await asyncio.to_thread(model_fit.save, model_path, remove_data=True)
            logger.info(f"ARIMA model successfully saved to {model_path}")
        except Exception as inner_ex:
            logger.warning(f"ARIMA seasonal fit failed for product {product_id}: {inner_ex}. Falling back to simple ARIMA(1,1,1)...")
            model = ARIMA(df_ts["y"], order=(1, 1, 1))
            model_fit = await asyncio.to_thread(model.fit)
            
            max_hist_date = df['ds'].max()
            target_end_date = pd.to_datetime("2026-12-31")
            periods = max(92, int((target_end_date - max_hist_date).days) + 5) if max_hist_date < target_end_date else 92
            
            forecast_res = await asyncio.to_thread(model_fit.forecast, steps=periods)
            
            np.random.seed(int(product_id) if product_id is not None else 42)
            resid_std = float(np.std(model_fit.resid)) if hasattr(model_fit, "resid") else 10.0
            noise = np.random.normal(0, resid_std * 0.4, size=len(forecast_res))
            
            weekly_pattern = np.array([1.1 if d.weekday() in [4, 5] else 0.9 for d in forecast_res.index])
            yhat_vals = (forecast_res.values * weekly_pattern + noise).tolist()
            yhat_vals = [max(0.0, v) for v in yhat_vals]
            
            forecast_df = pd.DataFrame({
                "ds": forecast_res.index,
                "yhat": yhat_vals
            })

            # serialize the model object to disk, dude
            model_path = get_model_path()
            if product_id is not None:
                model_path = model_path.replace("arima_model.pkl", f"arima_model_{product_id}.pkl")
            os.makedirs(os.path.dirname(model_path), exist_ok=True)
            await asyncio.to_thread(model_fit.save, model_path, remove_data=True)
            
        # construct new forecast documents
        new_future_docs = []
        for _, row in forecast_df.iterrows():
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
            
        logger.info(f"ARIMA model retraining and forecast database update completed successfully for product_id={product_id}.")
        
    except Exception as e:
        logger.error(f"Error during ARIMA model retraining: {e}", exc_info=True)
    finally:
        lock.release()

async def generate_forecast_explanation(db, product_id: int) -> str:
    import math
    import httpx
    
    try:
        # guarantee at least a 3-month forecast window
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
        
        # query Q4 2026 forecast window
        query = {
            "product_id": product_id,
            "date": {"$gte": "2026-09-01", "$lte": "2026-12-31"}
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
            return f"Historical daily demand data for {product_name} in the Sep-Dec 2026 window is currently empty."
            
        hist_sales = [r["sales"] for r in historical]
        hist_mean = sum(hist_sales) / len(hist_sales)
        
        if not future:
            return f"Historical daily demand for {product_name} averages {hist_mean:.0f} units in Sep 2026. No forecast is loaded for the Oct-Dec 2026 window."

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
            f"You are a supply chain AI analyst. Explain the demand forecast for: {product_name} (ID: {product_id}) within the 3-month window (Sep 2026 - Dec 2026).\n"
            f"- Historical average daily sales (Sep 2026): {hist_mean:.0f} units.\n"
            f"- Forecasted average daily demand (Oct-Dec 2026): {forecast_mean:.0f} units.\n"
            f"- Peak forecasted daily demand: {peak_forecast:.0f} units on {peak_date}.\n"
            f"- Stockout Risk: {'HIGH' if has_stockout else 'NORMAL'}.\n"
            f"- High Demand Expected: {'YES' if has_high_demand else 'NO'}.\n\n"
            f"Write a concise 2-3 sentence explanation for the supply chain manager. "
            f"Explain what the forecast indicates about future demand, whether a stockout is expected, and what actionable replenishment steps they should take. "
            f"Be direct and professional. Do NOT use bullet points, markdown list syntax, or introductory greetings (like 'Here is...'). Use the provided numbers."
        )
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                # Dynamically resolve installed models
                resp = await client.get("http://localhost:11434/api/tags")
                installed = [m["name"] for m in resp.json().get("models", [])] if resp.status_code == 200 else []
                pref = ["qwen2.5:7b", "qwen2.5:latest", "qwen2.5", "llama3.1", "llama3", "mistral"]
                model = next((m for p in pref for m in installed if m.startswith(p)), installed[0] if installed else "qwen2.5:7b")
                
                response = await client.post(ollama_url, json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False
                })
                
                if response.status_code == 200:
                    insights = response.json().get("response", "").strip()
                    if insights:
                        return insights
                    logger.error("Ollama returned empty forecast explanation response for product %s", product_id)
                    raise HTTPException(status_code=502, detail="Ollama forecast explanation generation failed")
                else:
                    logger.error("Ollama /api/generate failed for forecast explanation: %s %s", response.status_code, await response.text())
                    raise HTTPException(status_code=502, detail="Ollama forecast explanation generation failed")
        except HTTPException:
            raise
        except Exception as err:
            logger.exception("Ollama local LLM connection failed for forecast explanation: %s", err)
            print(f"Ollama local LLM connection failed for forecast explanation: {err}")
            raise HTTPException(status_code=502, detail="Ollama forecast explanation generation failed")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating forecast explanation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Unable to generate forecast explanation due to an internal error")
