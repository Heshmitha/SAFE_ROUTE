import osmnx as ox
import pandas as pd
import networkx as nx
from scipy.spatial import cKDTree
import numpy as np
import os

# --- PATH CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE = os.path.join(BASE_DIR, 'dataset', 'clean_crime_data.csv')
GRAPH_FILE = os.path.join(BASE_DIR, 'Backend', 'models', 'chicago_graph.graphml')

def build_graph():
    print("🏗️  Step 1: Downloading Chicago Street Network... (This takes 2-5 mins)")
    print("    (Please be patient, do not close the window!)")
    
    # Download the driving network for Chicago
    # This creates a graph where Nodes = Intersections, Edges = Roads
    G = ox.graph_from_place("Chicago, Illinois, USA", network_type='drive')
    print(f"✅ Graph Downloaded! Nodes: {len(G.nodes)}, Edges: {len(G.edges)}")

    print("📊 Step 2: Loading Crime Data...")
    if not os.path.exists(DATA_FILE):
        print(f"❌ Error: Could not find {DATA_FILE}")
        return

    df = pd.read_csv(DATA_FILE)
    crime_coords = df[['Latitude', 'Longitude']].dropna().values

    print("🔗 Step 3: Mapping Crimes to Nearest Streets...")
    # Get all intersection coordinates from the map
    nodes = ox.graph_to_gdfs(G, nodes=True, edges=False)
    node_coords = np.array(list(zip(nodes.y, nodes.x))) # Lat, Lon

    # Use a KDTree (Fast Search) to find the nearest intersection for every crime
    tree = cKDTree(node_coords)
    distances, indices = tree.query(crime_coords, k=1)

    # Count crimes at each node
    node_crime_counts = pd.Series(indices).value_counts().sort_index()
    
    # Create a dictionary {Node_ID: Crime_Count}
    node_ids = nodes.index.tolist()
    crime_map = {}
    for i, count in node_crime_counts.items():
        crime_map[node_ids[i]] = count

    print("⚖️  Step 4: Calculating Safety Weights...")
    # Iterate through every road (edge) and assign a weight
    for u, v, data in G.edges(data=True):
        # 1. Get the physical length (meters)
        length = data.get('length', 10)
        
        # 2. Get crime count at both ends of the road
        u_crimes = crime_map.get(u, 0)
        v_crimes = crime_map.get(v, 0)
        total_crimes = u_crimes + v_crimes
        
        # 3. Calculate "Safety Cost"
        # If a road has crimes, we pretend it is 10x longer than it really is.
        # This forces the algorithm to find a "shorter" (safer) way around.
        safety_penalty = total_crimes * 20 
        
        # 'weight' is what the algorithm minimizes. 
        # Low Weight = Short + Safe. High Weight = Long OR Dangerous.
        data['safety_weight'] = length + safety_penalty

    print("💾 Step 5: Saving the Smart Map...")
    # Save the processed graph so we don't have to download it again
    ox.save_graphml(G, GRAPH_FILE)
    print(f"🎉 Success! Graph saved to: {GRAPH_FILE}")

if __name__ == "__main__":
    build_graph()