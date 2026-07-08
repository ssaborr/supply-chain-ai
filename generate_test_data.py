import pandas as pd
import os

def generate_test_csv():
    project_root = os.path.dirname(os.path.abspath(__file__))
    source_path = os.path.join(project_root, "DataCoSupplyChainDataset.csv")
    dest_path = os.path.join(project_root, "test_orders_new.csv")
    
    if not os.path.exists(source_path):
        print(f"Error: Source dataset not found at {source_path}")
        return
        
    print(f"Loading first 50 rows from {source_path}...")
    # Read the first 50 rows (including header, nrows reads 50 data rows)
    df = pd.read_csv(source_path, nrows=50, encoding='latin-1')
    
    # Offset Order Id to make them brand new unique orders
    if 'Order Id' in df.columns:
        df['Order Id'] = df['Order Id'] + 10000000
        
    df.to_csv(dest_path, index=False)
    print(f"Successfully generated test file at {dest_path}")

if __name__ == "__main__":
    generate_test_csv()
