import os
import numpy as np
import pandas as pd
from pymongo import MongoClient
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from dotenv import load_dotenv

def train_and_save_kmeans():
    print("=== Training KMeans Product Clustering Model (All Products) ===")
    
    # Load config from BackEnd/.env
    env_path = os.path.join(os.path.dirname(__file__), 'BackEnd', '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
    
    mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    database_name = os.getenv("DATABASE_NAME", "smart_supply_chain")
    
    print(f"Connecting to MongoDB at {mongodb_uri} (DB: {database_name})...")
    client = MongoClient(mongodb_uri)
    db = client[database_name]
    
    # Retrieve products and sales orders
    products = list(db["products"].find())
    orders = list(db["sales_orders"].find())
    
    print(f"Found {len(products)} products and {len(orders)} sales orders in DB.")
    
    if not products:
        print("Error: No products found in the database. Please run seed_db.py first.")
        return
        
    # Sum order line quantities per SKU
    sales_qty = {}
    for o in orders:
        for line in o.get("order_lines", []):
            sku = line.get("product_sku")
            qty = line.get("quantity", 0)
            if sku is not None:
                sales_qty[sku] = sales_qty.get(sku, 0) + qty
                
    # Format dataset for clustering
    prod_data = []
    for p in products:
        sku = p["sku"]
        price = p["price"]
        # Scale volume by 1.5 for dashboard visual realism
        qty = sales_qty.get(sku, 0)
        monthly_volume = float(qty * 1.5)
        
        prod_data.append({
            "sku": sku,
            "name": p["name"],
            "price": price,
            "monthly_volume": monthly_volume
        })
        
    df = pd.DataFrame(prod_data)
    
    # Run KMeans clustering
    X = df[['price', 'monthly_volume']].copy()
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
    df['cluster_id'] = kmeans.fit_predict(X_scaled)

    # Classify labels based on cluster centroids
    centroids = df.groupby('cluster_id')[['price', 'monthly_volume']].mean().reset_index()
    print("\nCluster Centroids (Original scale):")
    print(centroids)
    
    # Highest price cluster -> HIGH VALUE
    high_value_id = int(centroids.loc[centroids['price'].idxmax()]['cluster_id'])
    
    # Highest volume cluster among the remaining -> VOLUME DRIVERS
    remaining = centroids[centroids['cluster_id'] != high_value_id]
    volume_driver_id = int(remaining.loc[remaining['monthly_volume'].idxmax()]['cluster_id'])
    
    # Last remaining cluster -> LOW PERFORMERS
    low_performer_id = int(remaining.loc[remaining['monthly_volume'].idxmin()]['cluster_id'])
    
    print(f"\nLabel mapping:")
    print(f"  Cluster {high_value_id} -> HIGH VALUE")
    print(f"  Cluster {volume_driver_id} -> VOLUME DRIVERS")
    print(f"  Cluster {low_performer_id} -> LOW PERFORMERS")
    
    # Map labels to products
    df['cluster_label'] = 'LOW PERFORMERS'
    df.loc[df['cluster_id'] == high_value_id, 'cluster_label'] = 'HIGH VALUE'
    df.loc[df['cluster_id'] == volume_driver_id, 'cluster_label'] = 'VOLUME DRIVERS'
    
    print("\nCluster Assignment Summary:")
    print(df['cluster_label'].value_counts())
    
    # Update products in MongoDB
    print("\nUpdating products collection in MongoDB...")
    updated_count = 0
    for _, row in df.iterrows():
        sku = int(row['sku'])
        monthly_volume = float(row['monthly_volume'])
        cluster = str(row['cluster_label'])
        
        result = db["products"].update_one(
            {"sku": sku},
            {"$set": {
                "monthly_volume": monthly_volume,
                "cluster": cluster
            }}
        )
        if result.modified_count > 0 or result.matched_count > 0:
            updated_count += 1
            
    print(f"Successfully updated {updated_count} products with clustering information.")
    print("=== Training Completed successfully ===")

if __name__ == "__main__":
    train_and_save_kmeans()
