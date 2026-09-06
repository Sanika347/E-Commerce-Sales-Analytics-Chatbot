import os
import zipfile
import sqlite3
import pandas as pd
import subprocess
from app.config import settings

def initialize_database():
    """Downloads dataset from Kaggle if needed and loads CSVs into SQLite."""
    data_dir = "data"
    db_path = settings.db_path
    
    os.makedirs(data_dir, exist_ok=True)
    
    if os.path.exists(db_path):
        print(f"Database {db_path} already exists. Skipping initialization.")
        return
    
    # 1. Download Dataset
    zip_path = os.path.join(data_dir, "brazilian-ecommerce.zip")
    if not os.path.exists(zip_path):
        print("Downloading dataset from Kaggle...")
        # Ensure Kaggle credentials are set
        os.environ["KAGGLE_USERNAME"] = settings.kaggle_username
        os.environ["KAGGLE_KEY"] = settings.kaggle_key
        
        try:
            subprocess.run(
                ["kaggle", "datasets", "download", "-d", "olistbr/brazilian-ecommerce", "-p", data_dir],
                check=True
            )
        except subprocess.CalledProcessError as e:
            print(f"Error downloading dataset: {e}")
            return
            
    # 2. Extract Dataset
    print("Extracting dataset...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(data_dir)
        
    # 3. Load CSVs to SQLite
    print("Loading CSVs to SQLite...")
    conn = sqlite3.connect(db_path)
    
    csv_files = [f for f in os.listdir(data_dir) if f.endswith(".csv")]
    for csv_file in csv_files:
        table_name = csv_file.replace(".csv", "")
        file_path = os.path.join(data_dir, csv_file)
        
        print(f"Loading {csv_file} into table {table_name}...")
        df = pd.read_csv(file_path)
        df.to_sql(table_name, conn, if_exists="replace", index=False)
        
    conn.close()
    print("Database initialization complete.")

if __name__ == "__main__":
    initialize_database()
