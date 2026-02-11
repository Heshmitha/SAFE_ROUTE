from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import networkx as nx
import osmnx as ox
import os

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRAPH_FILE = os.path.join(BASE_DIR, 'Backend', 'models', 'chicago_graph.graphml')

app = Flask(__name__, template_folder='../Frontend', static_folder='../Frontend/static')
CORS(app)

G = None

def load_graph():
    global G
    print("⏳ Loading Street Network...")
    if os.path.exists(GRAPH_FILE):
        G = ox.load_graphml(GRAPH_FILE)
        # Convert attributes to numbers
        for u, v, data in G.edges(data=True):
            data['length'] = float(data.get('length', 10.0))
            data['safety_weight'] = float(data.get('safety_weight', 10.0))
        print(f"✅ Graph Ready! Nodes: {len(G.nodes)}")
    else:
        print("❌ Graph file not found!")

load_graph()

def get_path_stats(G, path, weight_col='safety_weight'):
    """Calculates Total Distance and Total Risk for a given path."""
    total_dist = 0
    total_risk = 0
    for i in range(len(path) - 1):
        u, v = path[i], path[i+1]
        # Get edge data (handle multi-edges)
        edge_data = G.get_edge_data(u, v)[0] 
        total_dist += edge_data.get('length', 0)
        # Risk is the 'safety_weight' minus the 'length' (pure crime penalty)
        risk = edge_data.get('safety_weight', 0) - edge_data.get('length', 0)
        total_risk += max(0, risk) # Ensure non-negative
        
    return int(total_dist), int(total_risk)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/get_safe_path', methods=['POST'])
def get_safe_path():
    data = request.json
    start_lat, start_lon = data.get('start_lat'), data.get('start_lon')
    end_lat, end_lon = data.get('end_lat'), data.get('end_lon')

    if not G: return jsonify({"error": "Graph not loaded"}), 500

    try:
        orig_node = ox.nearest_nodes(G, start_lon, start_lat)
        dest_node = ox.nearest_nodes(G, end_lon, end_lat)

        # 1. Calculate Risky Path (Shortest Distance)
        risky_path = nx.shortest_path(G, orig_node, dest_node, weight='length')
        risky_dist, risky_score = get_path_stats(G, risky_path)

        # 2. Calculate Safe Path (Lowest Safety Weight)
        safe_path = nx.shortest_path(G, orig_node, dest_node, weight='safety_weight')
        safe_dist, safe_score = get_path_stats(G, safe_path)

        return jsonify({
            "risky_path": [[G.nodes[n]['y'], G.nodes[n]['x']] for n in risky_path],
            "risky_dist": risky_dist,
            "risky_score": risky_score,
            
            "safe_path": [[G.nodes[n]['y'], G.nodes[n]['x']] for n in safe_path],
            "safe_dist": safe_dist,
            "safe_score": safe_score
        })

    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)