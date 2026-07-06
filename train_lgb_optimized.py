import pandas as pd
import numpy as np
import pickle
import os
from sklearn.model_selection import train_test_split, GridSearchCV
from lightgbm import LGBMClassifier
from sklearn.metrics import classification_report, accuracy_score, confusion_matrix

def optimize_and_train_lgb():
    raw_path = r"c:\Users\Sabor\Desktop\project\processed_data\anomaly_features_raw.csv"
    
    # 1. Generate features if raw file is not present
    if not os.path.exists(raw_path):
        print("Raw features csv not found. Please run preprocessing first.")
        return
        
    print(f"Loading raw features from {raw_path}...")
    df = pd.read_csv(raw_path)
    
    anomaly_cols = ['delay_delta', 'Order Item Quantity', 'Sales', 'profit_margin', 'discount_ratio']
    X = df[anomaly_cols]
    y = df['is_fraud']
    
    # 2. Train-Test Split (80% Train, 20% Test)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    
    # 3. Cross-Validation Grid Search Hyperparameter Optimization
    param_grid = {
        'n_estimators': [50, 100, 200],
        'max_depth': [3, 5, 7, -1],
        'learning_rate': [0.01, 0.05, 0.1],
        'num_leaves': [15, 31, 63]
    }
    
    print("Running Cross-Validation Grid Search (K-fold = 5) for LightGBM...")
    grid_search = GridSearchCV(
        LGBMClassifier(random_state=42, verbose=-1),
        param_grid,
        cv=5,
        scoring='f1',
        n_jobs=-1
    )
    grid_search.fit(X_train, y_train)
    
    print("\n--- GRID SEARCH RESULT ---")
    print(f"Best Hyperparameters found: {grid_search.best_params_}")
    print(f"Best CV F1-Score: {grid_search.best_score_:.4f}")
    
    best_lgb = grid_search.best_estimator_
    
    # 4. Evaluate on Test Dataset
    y_pred = best_lgb.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    cm = confusion_matrix(y_test, y_pred)
    
    print("\n--- MODEL PERFORMANCE ON TEST SET ---")
    print(f"Accuracy: {acc * 100:.2f}%")
    print("\nConfusion Matrix:")
    print(cm)
    print("\nDetailed Classification Report:")
    print(classification_report(y_test, y_pred))
    
    # 5. Save optimized model (using full dataset for final training)
    print("Re-fitting best model on complete dataset for production...")
    lgb_optimized = LGBMClassifier(**grid_search.best_params_, random_state=42, verbose=-1)
    lgb_optimized.fit(X, y)
    
    model_data = {
        "model": lgb_optimized,
        "features": anomaly_cols,
        "cv_score": grid_search.best_score_,
        "test_accuracy": acc,
        "best_params": grid_search.best_params_
    }
    
    model_path = r"c:\Users\Sabor\Desktop\project\processed_data\lgb_anomaly_model.pkl"
    with open(model_path, 'wb') as f:
        pickle.dump(model_data, f)
    print(f"\nSuccessfully saved optimized LightGBM model configuration to {model_path}")

if __name__ == "__main__":
    optimize_and_train_lgb()
