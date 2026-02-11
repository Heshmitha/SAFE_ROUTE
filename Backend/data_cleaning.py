import pandas as pd
import os 

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_FILE = os.path.join(BASE_DIR, 'dataset', 'chicago_crime_data.csv')
OUTPUT_FILE = os.path.join(BASE_DIR, 'dataset', 'clean_crime_data.csv')

def clean_data():
    print(f"⏳ Loading data from: {INPUT_FILE}")
    
    try:
        # 1. Load the CSV
        df = pd.read_csv(INPUT_FILE)
        print(f"✅ Loaded {len(df)} records.")

        # 2. Keep only what we need
        # 'Primary Type' = What crime? (Theft, Assault)
        # 'Latitude', 'Longitude' = Where?
        useful_cols = ['Date', 'Primary Type', 'Latitude', 'Longitude', 'Location Description']
        df = df[useful_cols]

        # 3. Remove rows with missing location (can't map them)
        df = df.dropna(subset=['Latitude', 'Longitude'])

        # 4. Filter out non-dangerous stuff (Optional but recommended)
        # Removes "Non-Criminal" or "Lost Property" reports
        df = df[~df['Primary Type'].isin(['NON-CRIMINAL', 'LOST PROPERTY'])]

        # 5. Save the clean file
        df.to_csv(OUTPUT_FILE, index=False)
        print(f"🎉 Success! Cleaned data saved to: {OUTPUT_FILE}")
        print(f"📊 Final Record Count: {len(df)}")
        print(df.head())

    except FileNotFoundError:
        print("❌ Error: Could not find the input file.")
        print(f"Please check if '{INPUT_FILE}' exists.")

if __name__ == "__main__":
    clean_data()