import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
import os

def clean_and_prepare_ml_datasets(file_path):
    print("Starting ML Preprocessing Pipeline...")
    
    print(f"Loading raw dataset from {file_path}...")
    df = pd.read_csv(file_path, encoding='latin-1')
    total_raw_rows = len(df)
    
    output_dir = "processed_data"
    os.makedirs(output_dir, exist_ok=True)
    
    # Filter basic invalid rows
    cleaned_df = df[
        (df["Product Price"] > 0) & 
        (df["Sales"] >= 0) & 
        (df["Order Item Quantity"] > 0)
    ].copy()
    
    # Flag bulk quantities for consumers
    consumer_outliers = cleaned_df[
        (cleaned_df["Customer Segment"] == "Consumer") & 
        (cleaned_df["Order Item Quantity"] > 50)
    ]
    print(f"-> Flagged {len(consumer_outliers)} extreme quantity outliers.")
    
    # Flag extreme shipping delays (> 30 days deviation)
    delay_outliers = cleaned_df[
        (cleaned_df["Days for shipping (real)"] - cleaned_df["Days for shipment (scheduled)"]).abs() > 30
    ]
    print(f"-> Flagged {len(delay_outliers)} extreme shipping delay anomalies.")
    
    # Drop anomalies
    outliers_indices = pd.concat([consumer_outliers, delay_outliers]).index.unique()
    cleaned_df = cleaned_df.drop(outliers_indices)
    
    rows_removed = total_raw_rows - len(cleaned_df)
    print(f"Removed {rows_removed:,} outlier rows ({rows_removed/total_raw_rows:.2%}).")
    
    # Feature engineering for anomaly/fraud detection
    cleaned_df['delay_delta'] = cleaned_df['Days for shipping (real)'] - cleaned_df['Days for shipment (scheduled)']
    cleaned_df['profit_margin'] = cleaned_df['Order Profit Per Order'] / cleaned_df['Sales'].replace(0, np.nan)
    cleaned_df['profit_margin'] = cleaned_df['profit_margin'].fillna(0)
    cleaned_df['discount_ratio'] = cleaned_df['Order Item Discount Rate']
    
    # Target label for fraud
    cleaned_df['is_fraud'] = (cleaned_df['Order Status'] == 'SUSPECTED_FRAUD').astype(int)
    print(f"-> Found {cleaned_df['is_fraud'].sum():,} labeled fraud records ('SUSPECTED_FRAUD').")
    
    cleaned_df['order_date_parsed'] = pd.to_datetime(cleaned_df['order date (DateOrders)'])
    
    # --- Dataset 1: Anomaly Detection features ---
    print("Preparing anomaly detection datasets...")
    anomaly_cols = ['delay_delta', 'Order Item Quantity', 'Sales', 'profit_margin', 'discount_ratio']
    X_anomaly = cleaned_df[anomaly_cols].fillna(0).copy()
    
    anomaly_raw_export = X_anomaly.copy()
    anomaly_raw_export['is_fraud'] = cleaned_df['is_fraud'].values
    anomaly_raw_export.to_csv(os.path.join(output_dir, "anomaly_features_raw.csv"), index=False)
    
    scaler_anomaly = StandardScaler()
    X_anomaly_scaled = pd.DataFrame(
        scaler_anomaly.fit_transform(X_anomaly), 
        columns=anomaly_cols
    )
    
    anomaly_scaled_export = X_anomaly_scaled.copy()
    anomaly_scaled_export['is_fraud'] = cleaned_df['is_fraud'].values
    anomaly_scaled_export.to_csv(os.path.join(output_dir, "anomaly_features_scaled.csv"), index=False)
    
    # --- Dataset 2: Customer RFM Segmentation ---
    print("Preparing customer segmentation dataset...")
    snapshot_date = cleaned_df['order_date_parsed'].max()
    
    rfm_df = cleaned_df.groupby('Customer Id').agg(
        Recency=('order_date_parsed', lambda x: (snapshot_date - x.max()).days),
        Frequency=('Order Id', 'nunique'),
        Monetary=('Sales', 'sum')
    ).reset_index()
    rfm_df.to_csv(os.path.join(output_dir, "rfm_features_raw.csv"), index=False)
    
    scaler_rfm = StandardScaler()
    rfm_scaled = pd.DataFrame(
        scaler_rfm.fit_transform(rfm_df[['Recency', 'Frequency', 'Monetary']]),
        columns=['Recency_scaled', 'Frequency_scaled', 'Monetary_scaled']
    )
    rfm_scaled['Customer Id'] = rfm_df['Customer Id']
    rfm_scaled.to_csv(os.path.join(output_dir, "rfm_features_scaled.csv"), index=False)
    
    # --- Dataset 3: Product-level daily demand (forecasting) ---
    print("Preparing product-level demand forecasting dataset...")
    product_daily_demand = cleaned_df.groupby(
        ['Product Card Id', 'Product Name', cleaned_df['order_date_parsed'].dt.date]
    ).agg(
        y=('Order Item Quantity', 'sum'),
        sales_volume=('Sales', 'sum')
    ).reset_index()
    
    product_daily_demand.rename(columns={'order_date_parsed': 'ds', 'Product Card Id': 'product_id', 'Product Name': 'product_name'}, inplace=True)
    product_daily_demand.to_csv(os.path.join(output_dir, "product_daily_demand.csv"), index=False)
    
    # Global daily demand for overview charts
    global_daily_demand = cleaned_df.groupby(cleaned_df['order_date_parsed'].dt.date).agg(
        y=('Order Item Quantity', 'sum'),
        sales_volume=('Sales', 'sum')
    ).reset_index()
    global_daily_demand.rename(columns={'order_date_parsed': 'ds'}, inplace=True)
    global_daily_demand.to_csv(os.path.join(output_dir, "global_daily_demand.csv"), index=False)
    
    # --- Dataset 4: Stockout Risk features ---
    print("Preparing product features for stockout risk...")
    product_stats = cleaned_df.groupby('Product Card Id').agg(
        demand_mean=('Order Item Quantity', 'mean'),
        demand_std=('Order Item Quantity', 'std'),
        avg_lead_time=('delay_delta', 'mean'),
        price=('Product Price', 'first')
    ).reset_index()
    
    product_stats['demand_std'] = product_stats['demand_std'].fillna(0)
    product_stats['demand_cv'] = np.where(
        product_stats['demand_mean'] > 0, 
        product_stats['demand_std'] / product_stats['demand_mean'], 
        0
    )
    product_stats.to_csv(os.path.join(output_dir, "product_ml_features.csv"), index=False)
    
    print("\n=== ML PREPROCESSING PIPELINE COMPLETED ===")
    print(f"All outputs saved to: ./{output_dir}")

if __name__ == '__main__':
    csv_path = r"c:\Users\Sabor\Desktop\tinkering\DataCoSupplyChainDataset.csv"
    clean_and_prepare_ml_datasets(csv_path)
