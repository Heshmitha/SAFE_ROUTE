import pandas as pd
from sklearn.cluster import KMeans
import pickle
import os

# --- PATH CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_FILE = os.path.join(BASE_DIR, 'dataset', 'clean_crime_data.csv')
MODEL_FILE = os.path.join(BASE_DIR, 'Backend', 'models', 'kmeans_model.pkl')

def train_model():
    print("🧠 Starting AI Training...")
    
    # 1. Load the Clean Data
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Error: {INPUT_FILE} not found. Did you run data_cleaning.py?")
        return

    df = pd.read_csv(INPUT_FILE)
    
    # 2. Prepare Data for AI
    # K-Means only understands numbers (Lat, Long). It doesn't care about the Date.
    X = df[['Latitude', 'Longitude']]
    
    print(f"📊 Training on {len(X)} crime locations...")

    # 3. Initialize K-Means
    # n_clusters=50 means we want to find the 50 most dangerous "Hotspots" in Chicago.
    # You can change this number later if you want more/less detail.
    kmeans = KMeans(n_clusters=50, random_state=42, n_init=10)
    
    # 4. Train! (This is where the learning happens)
    kmeans.fit(X)
    
    # 5. Save the Trained Brain
    # We use 'pickle' to save the math logic to a file so we don't have to retrain every time.
    with open(MODEL_FILE, 'wb') as f:
        pickle.dump(kmeans, f)
        
    print(f"✅ Success! AI Model saved to: {MODEL_FILE}")
    print("🚀 You are now ready to build the Backend API!")

if __name__ == "__main__":
    train_model()