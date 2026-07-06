import asyncio
import numpy as np
import pandas as pd
from prophet import Prophet
from motor.motor_asyncio import AsyncIOMotorClient

async def train_global():
    print("Connecting to MongoDB...")
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client['smart_supply_chain']
    
    # 1. Fetch all historical forecasts (where sales is not null and it's not a pre-existing overall record)
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
    
    # Filter dates before October 2017 to align with historical window limits if any
    df = df[df['ds'] < '2017-10-01'].reset_index(drop=True)
    
    print(f"Aggregated {len(df)} daily historical demand points.")
    
    # Apply Log transform
    df['y_original'] = df['y'].copy()
    df['y'] = np.log1p(df['y'])
    
    # 3. Fit Prophet model on total demand
    print("Fitting Prophet model on total demand...")
    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=True,
        daily_seasonality=False,
        changepoint_prior_scale=0.05,
        seasonality_prior_scale=10.0,
        uncertainty_samples=0
    )
    model.fit(df[['ds', 'y']])
    
    # 4. Predict next 90 days
    print("Generating predictions...")
    future = model.make_future_dataframe(periods=90, include_history=True)
    forecast = model.predict(future)
    forecast['yhat'] = np.expm1(forecast['yhat']).clip(lower=0.0)
    
    # 5. Insert aggregated history and predictions into forecasts collection under product_id = 0
    print("Cleaning old global forecasts...")
    await db["forecasts"].delete_many({"product_id": 0})
    
    docs = []
    # Historical points
    for _, row in df.iterrows():
        # Find matching forecast value for history
        fc_val = forecast[forecast['ds'] == row['ds']]['yhat'].iloc[0]
        docs.append({
            "date": row['ds'].strftime('%Y-%m-%d'),
            "product_id": 0,
            "sales": float(row['y_original']),
            "forecast": float(fc_val)
        })
        
    # Future points
    future_forecast = forecast[forecast['ds'] > df['ds'].max()]
    for _, row in future_forecast.iterrows():
        docs.append({
            "date": row['ds'].strftime('%Y-%m-%d'),
            "product_id": 0,
            "sales": None,
            "forecast": float(row['yhat'])
        })
        
    print(f"Inserting {len(docs)} overall demand forecast records...")
    await db["forecasts"].insert_many(docs)
    print("Global demand forecast trained and seeded successfully!")
    client.close()

if __name__ == '__main__':
    asyncio.run(train_global())
