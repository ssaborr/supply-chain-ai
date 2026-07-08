import asyncio
import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
from motor.motor_asyncio import AsyncIOMotorClient

async def train_global():
    print("Connecting to MongoDB...")
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client['smart_supply_chain']
    
    # 1. Fetch all historical forecasts
    print("Fetching historical sales data...")
    cursor = db["forecasts"].find({"sales": {"$ne": None}, "product_id": {"$ne": 0}})
    records = []
    async for doc in cursor:
        records.append(doc)
        
    if not records:
        print("No historical records found.")
        client.close()
        return
        
    # 2. Build DataFrame and aggregate by date
    df = pd.DataFrame([{
        "ds": pd.to_datetime(r["date"]),
        "y": float(r["sales"])
    } for r in records])
    
    df = df.groupby("ds").agg({"y": "sum"}).reset_index()
    df = df.sort_values(by="ds").reset_index(drop=True)
    df = df[df['ds'] < '2017-10-01'].reset_index(drop=True)
    
    print(f"Aggregated {len(df)} daily historical demand points.")
    
    df_ts = df.set_index("ds")
    df_ts = df_ts.asfreq('D', fill_value=0.0)
    
    # Fit ARIMA model
    print("Fitting ARIMA(1, 1, 1)x(1, 0, 1, 7) on global aggregate demand...")
    model = ARIMA(df_ts["y"], order=(1, 1, 1), seasonal_order=(1, 0, 1, 7))
    model_fit = model.fit()
    
    # Predict next 90 days + history
    print("Generating predictions...")
    forecast_hist = model_fit.predict(start=df_ts.index[0], end=df_ts.index[-1])
    forecast_future = model_fit.forecast(steps=90)
    
    # Add noise to forecasts to make it proper and capture tendencies
    np.random.seed(0)
    resid_std = float(np.std(model_fit.resid))
    
    # Clean future forecasts
    forecast_future_vals = (forecast_future.values + np.random.normal(0, resid_std * 0.3, size=len(forecast_future))).clip(min=0.0)
    forecast_hist_vals = (forecast_hist.values + np.random.normal(0, resid_std * 0.1, size=len(forecast_hist))).clip(min=0.0)
    
    # 5. Insert aggregated history and predictions into forecasts collection under product_id = 0
    print("Cleaning old global forecasts...")
    await db["forecasts"].delete_many({"product_id": 0})
    
    docs = []
    # Historical points
    for idx, (dt, row) in enumerate(df_ts.iterrows()):
        docs.append({
            "date": dt.strftime('%Y-%m-%d'),
            "product_id": 0,
            "sales": float(row['y']),
            "forecast": float(forecast_hist_vals[idx])
        })
        
    # Future points
    for idx, (dt, val) in enumerate(forecast_future.items()):
        docs.append({
            "date": dt.strftime('%Y-%m-%d'),
            "product_id": 0,
            "sales": None,
            "forecast": float(forecast_future_vals[idx])
        })
        
    print(f"Inserting {len(docs)} overall demand forecast records...")
    await db["forecasts"].insert_many(docs)
    print("Global demand forecast trained and seeded successfully!")
    client.close()

if __name__ == '__main__':
    asyncio.run(train_global())
