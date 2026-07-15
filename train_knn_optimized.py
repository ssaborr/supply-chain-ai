import pandas as pd
import numpy as np
import pickle
import os
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix
from pymongo import MongoClient

def optimize_and_train_knn():
    raw_path = r"c:\Users\Sabor\Desktop\project\processed_data\anomaly_features_raw.csv"
    anomaly_cols = ['delay_delta', 'Order Item Quantity', 'Sales', 'profit_margin', 'discount_ratio']
    loaded_data = False
    
    print("Attempting to load actual dataset from MongoDB...")
    try:
        client = MongoClient('mongodb://localhost:27017', serverSelectionTimeoutMS=2000)
        db = client['smart_supply_chain']
        products = list(db["products"].find())
        orders = list(db["sales_orders"].find())
        client.close()
        
        if products and orders:
            products_map = {int(p["sku"]): p for p in products}
            anomaly_records = []
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
            df_db = pd.DataFrame(anomaly_records)
            X = df_db[anomaly_cols]
            y = df_db['is_fraud']
            loaded_data = True
            print(f"Successfully loaded {len(X)} records from MongoDB.")
    except Exception as e:
        print(f"Could not connect to MongoDB ({e}). Checking CSV datasets...")

    if not loaded_data:
        # Generate features if raw file is not present
        if not os.path.exists(raw_path):
            print("Raw features csv not found. Running seed script generator logic...")
            from train_knn import train_and_save_knn
            train_and_save_knn()
            
        print(f"Loading raw features from {raw_path}...")
        df = pd.read_csv(raw_path)
        X = df[anomaly_cols]
        y = df['is_fraud']
    
    # 2. Balance the entire dataset using Random Oversampling of the minority class
    df_full = pd.DataFrame(X, columns=anomaly_cols)
    df_full['is_fraud'] = y.values
    
    df_majority = df_full[df_full['is_fraud'] == 0]
    df_minority = df_full[df_full['is_fraud'] == 1]
    
    df_minority_oversampled = df_minority.sample(len(df_majority), replace=True, random_state=42)
    df_balanced = pd.concat([df_majority, df_minority_oversampled])
    
    X_balanced = df_balanced.drop(columns=['is_fraud'])
    y_balanced = df_balanced['is_fraud']
    
    # 3. Train-Test Split (80% Train, 20% Test) with stratification on the balanced labels
    X_train, X_test, y_train, y_test = train_test_split(X_balanced, y_balanced, test_size=0.2, random_state=42, stratify=y_balanced)
    
    # 4. Fit scaler on training data
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # 5. Cross-Validation Grid Search Hyperparameter Optimization
    param_grid = {
        'n_neighbors': [3, 5, 7, 9, 11, 13, 15],
        'weights': ['uniform', 'distance'],
        'metric': ['euclidean', 'manhattan']
    }
    
    print("Running Cross-Validation Grid Search (K-fold = 5)...")
    grid_search = GridSearchCV(
        KNeighborsClassifier(),
        param_grid,
        cv=5,
        scoring='f1',
        n_jobs=-1
    )
    grid_search.fit(X_train_scaled, y_train)
    
    print("\n--- GRID SEARCH RESULT ---")
    print(f"Best Hyperparameters found: {grid_search.best_params_}")
    print(f"Best CV F1-Score: {grid_search.best_score_:.4f}")
    
    best_knn = grid_search.best_estimator_
    
    # 5. Evaluate on Test Dataset
    y_pred = best_knn.predict(X_test_scaled)
    acc = accuracy_score(y_test, y_pred)
    cm = confusion_matrix(y_test, y_pred)
    
    print("\n--- MODEL PERFORMANCE ON TEST SET ---")
    print(f"Accuracy: {acc * 100:.2f}%")
    print("\nConfusion Matrix:")
    print(cm)
    print("\nDetailed Classification Report:")
    print(classification_report(y_test, y_pred))
    
    # 6. Save optimized model and scaler (using full dataset for final training)
    print("Re-fitting best model on complete dataset for production...")
    # Balance the full dataset before final fitting
    df_full = pd.DataFrame(X, columns=anomaly_cols)
    df_full['is_fraud'] = y.values
    
    df_maj_full = df_full[df_full['is_fraud'] == 0]
    df_min_full = df_full[df_full['is_fraud'] == 1]
    
    df_min_full_oversampled = df_min_full.sample(len(df_maj_full), replace=True, random_state=42)
    df_full_balanced = pd.concat([df_maj_full, df_min_full_oversampled])
    
    X_balanced_full = df_full_balanced.drop(columns=['is_fraud'])
    y_balanced_full = df_full_balanced['is_fraud']
    
    scaler_full = StandardScaler()
    X_scaled_full = scaler_full.fit_transform(X_balanced_full)
    
    # Instantiate best KNN parameters
    knn_optimized = KNeighborsClassifier(**grid_search.best_params_)
    knn_optimized.fit(X_scaled_full, y_balanced_full)
    
    model_data = {
        "scaler": scaler_full,
        "knn": knn_optimized,
        "features": anomaly_cols,
        "cv_score": grid_search.best_score_,
        "test_accuracy": acc,
        "best_params": grid_search.best_params_
    }
    
    model_path = r"c:\Users\Sabor\Desktop\project\processed_data\knn_anomaly_model.pkl"
    tmp_path = model_path + ".tmp"
    with open(tmp_path, 'wb') as f:
        pickle.dump(model_data, f)
    os.replace(tmp_path, model_path)
    print(f"\nSuccessfully saved optimized KNN model configuration to {model_path}")

if __name__ == "__main__":
    optimize_and_train_knn()
