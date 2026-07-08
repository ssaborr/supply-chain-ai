import pandas as pd
import numpy as np
import pickle
import os
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import KNeighborsClassifier
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix

def optimize_and_train_knn():
    raw_path = r"c:\Users\Sabor\Desktop\project\processed_data\anomaly_features_raw.csv"
    
    # 1. Generate features if raw file is not present
    if not os.path.exists(raw_path):
        print("Raw features csv not found. Running seed script generator logic...")
        from train_knn import train_and_save_knn
        train_and_save_knn()
        
    print(f"Loading raw features from {raw_path}...")
    df = pd.read_csv(raw_path)
    
    anomaly_cols = ['delay_delta', 'Order Item Quantity', 'Sales', 'profit_margin', 'discount_ratio']
    X = df[anomaly_cols]
    y = df['is_fraud']
    
    # 2. Train-Test Split (80% Train, 20% Test)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    
    # 3. Fit scaler on training data
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # 4. Cross-Validation Grid Search Hyperparameter Optimization
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
    scaler_full = StandardScaler()
    X_scaled_full = scaler_full.fit_transform(X)
    
    # Instantiate best KNN parameters
    knn_optimized = KNeighborsClassifier(**grid_search.best_params_)
    knn_optimized.fit(X_scaled_full, y)
    
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
