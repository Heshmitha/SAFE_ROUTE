from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import networkx as nx
import osmnx as ox
import os
import gdown
import sys
import traceback

# --- CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GRAPH_FILE = os.path.join(BASE_DIR, 'Backend', 'models', 'chicago_graph.graphml')

# Google Drive file ID for your graph (UPDATED)
GOOGLE_DRIVE_GRAPH_ID = "10bayxYtw_hP6jw86dnL-SZXuD45DbGKo"

app = Flask(__name__, 
            template_folder='../Frontend', 
            static_folder='../Frontend',
            static_url_path='')
CORS(app)

G = None

def download_graph_from_drive():
    """Download graph file from Google Drive if not exists"""
    try:
        if not os.path.exists(GRAPH_FILE):
            os.makedirs(os.path.dirname(GRAPH_FILE), exist_ok=True)
            print("⏳ Downloading graph file from Google Drive...")
            
            url = f"https://drive.google.com/uc?id={GOOGLE_DRIVE_GRAPH_ID}"
            gdown.download(url, GRAPH_FILE, quiet=False)
            
            if os.path.exists(GRAPH_FILE):
                print(f"✅ Graph downloaded successfully: {os.path.getsize(GRAPH_FILE) / (1024*1024):.2f} MB")
                return True
            else:
                print("❌ Download failed - file not found")
                return False
        else:
            print(f"✅ Graph file already exists: {os.path.getsize(GRAPH_FILE) / (1024*1024):.2f} MB")
            return True
    except Exception as e:
        print(f"❌ Error downloading graph: {e}")
        traceback.print_exc()
        return False

def load_graph():
    """Load the street network graph"""
    global G
    print("⏳ Loading Street Network...")
    
    # Try to download if not exists
    if not os.path.exists(GRAPH_FILE):
        print("📥 Graph file not found locally, attempting download...")
        if not download_graph_from_drive():
            print("⚠️  Could not download graph. Using OSMnx to download Chicago network...")
            try:
                # Fallback: Download Chicago network on the fly
                print("⏳ Downloading Chicago network from OSMnx (this may take a minute)...")
                G = ox.graph_from_place('Chicago, Illinois, USA', network_type='drive')
                print(f"✅ Downloaded Chicago network from OSMnx: {len(G.nodes):,} nodes, {len(G.edges):,} edges")
                return
            except Exception as e:
                print(f"❌ Could not download Chicago network: {e}")
                traceback.print_exc()
                return
    
    try:
        if os.path.exists(GRAPH_FILE):
            print(f"⏳ Loading graph from: {GRAPH_FILE}")
            G = ox.load_graphml(GRAPH_FILE)
            
            # Convert attributes to numbers
            edge_count = 0
            for u, v, data in G.edges(data=True):
                # Handle length
                if 'length' in data:
                    try:
                        data['length'] = float(data['length'])
                    except:
                        data['length'] = 10.0
                else:
                    data['length'] = 10.0
                
                # Handle safety_weight
                if 'safety_weight' in data:
                    try:
                        data['safety_weight'] = float(data['safety_weight'])
                    except:
                        data['safety_weight'] = data['length'] * 1.5
                else:
                    # Fallback: create safety_weight from length if not present
                    data['safety_weight'] = data['length'] * 1.5
                    
                # Handle highway type
                if 'highway' not in data:
                    data['highway'] = 'unclassified'
                
                edge_count += 1
            
            print(f"✅ Graph Ready! Nodes: {len(G.nodes):,}, Edges: {edge_count:,}")
            
            # Test the graph with a sample route
            try:
                # Get a random node pair for testing
                nodes = list(G.nodes())
                if len(nodes) > 1:
                    test_path = nx.shortest_path(G, nodes[0], nodes[1], weight='length')
                    print(f"✅ Graph test successful: Path found between test nodes")
            except:
                print("⚠️ Graph test warning: Could not find test path, but graph may still work")
            
        else:
            print("❌ Graph file not found!")
            
    except Exception as e:
        print(f"❌ Error loading graph: {e}")
        traceback.print_exc()

def get_path_stats(G, path, weight_col='safety_weight'):
    """Calculates Total Distance and Total Risk for a given path."""
    total_dist = 0
    total_risk = 0
    
    if not path or len(path) < 2:
        return 0, 0
    
    for i in range(len(path) - 1):
        u, v = path[i], path[i+1]
        
        try:
            # Get edge data (handle multi-edges)
            if G.has_edge(u, v):
                edge_data = G.get_edge_data(u, v)
                
                # Get the first edge if multiple exist
                if isinstance(edge_data, dict) and len(edge_data) > 0:
                    first_key = next(iter(edge_data))
                    edge = edge_data[first_key]
                else:
                    edge = edge_data
                
                # Get length
                length = edge.get('length', 10.0)
                if isinstance(length, (list, tuple)):
                    length = length[0] if length else 10.0
                
                total_dist += float(length)
                
                # Calculate risk (safety_weight - length)
                safety_weight = edge.get('safety_weight', length * 1.5)
                if isinstance(safety_weight, (list, tuple)):
                    safety_weight = safety_weight[0] if safety_weight else length * 1.5
                
                risk = float(safety_weight) - float(length)
                total_risk += max(0, risk)  # Ensure non-negative
                
        except Exception as e:
            print(f"⚠️ Error processing edge ({u}, {v}): {e}")
            continue
    
    return int(total_dist), int(total_risk)

@app.route('/')
def home():
    """Serve the frontend"""
    return render_template('index.html')

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'graph_loaded': G is not None,
        'nodes': len(G.nodes) if G else 0,
        'edges': len(G.edges) if G else 0,
        'graph_file_exists': os.path.exists(GRAPH_FILE),
        'graph_file_size': f"{os.path.getsize(GRAPH_FILE) / (1024*1024):.2f} MB" if os.path.exists(GRAPH_FILE) else "0 MB"
    })

@app.route('/api/get_safe_path', methods=['POST'])
def get_safe_path():
    """Find safe and risky paths between two points"""
    if G is None:
        return jsonify({"error": "Graph not loaded. Please try again later."}), 503
    
    try:
        data = request.json
        start_lat = float(data.get('start_lat'))
        start_lon = float(data.get('start_lon'))
        end_lat = float(data.get('end_lat'))
        end_lon = float(data.get('end_lon'))

        print(f"📍 Finding path from ({start_lat}, {start_lon}) to ({end_lat}, {end_lon})")

        # Find nearest nodes
        try:
            orig_node = ox.nearest_nodes(G, start_lon, start_lat)
            dest_node = ox.nearest_nodes(G, end_lon, end_lat)
            print(f"📍 Origin node: {orig_node}, Destination node: {dest_node}")
        except Exception as e:
            return jsonify({"error": f"Could not find locations on map: {str(e)}"}), 400

        # 1. Calculate Risky Path (Shortest Distance)
        risky_path = None
        risky_dist = 0
        risky_score = 0
        
        try:
            risky_path = nx.shortest_path(G, orig_node, dest_node, weight='length')
            risky_dist, risky_score = get_path_stats(G, risky_path, 'length')
            print(f"✅ Risky path found: {len(risky_path)} nodes, {risky_dist}m")
        except nx.NetworkXNoPath:
            print("❌ No risky path found")
            return jsonify({"error": "No route found between these locations"}), 404
        except Exception as e:
            print(f"⚠️ Error calculating risky path: {e}")

        # 2. Calculate Safe Path (Lowest Safety Weight)
        safe_path = None
        safe_dist = 0
        safe_score = 0
        
        try:
            safe_path = nx.shortest_path(G, orig_node, dest_node, weight='safety_weight')
            safe_dist, safe_score = get_path_stats(G, safe_path, 'safety_weight')
            print(f"✅ Safe path found: {len(safe_path)} nodes, {safe_dist}m, risk score: {safe_score}")
        except nx.NetworkXNoPath:
            print("❌ No safe path found")
            return jsonify({"error": "No safe route found between these locations"}), 404
        except Exception as e:
            print(f"⚠️ Error calculating safe path: {e}")
            return jsonify({"error": f"Could not calculate safe path: {str(e)}"}), 500

        # Prepare response
        response = {
            "success": True,
            
            # Risky path (shortest)
            "risky_path": [[G.nodes[n]['y'], G.nodes[n]['x']] for n in risky_path] if risky_path else [],
            "risky_dist": risky_dist,
            "risky_score": risky_score,
            
            # Safe path (safest)
            "safe_path": [[G.nodes[n]['y'], G.nodes[n]['x']] for n in safe_path] if safe_path else [],
            "safe_dist": safe_dist,
            "safe_score": safe_score,
            
            # Comparison
            "distance_saved": max(0, risky_dist - safe_dist) if risky_dist and safe_dist else 0,
            "safety_improved": max(0, safe_score - risky_score) if risky_score and safe_score else 0,
            "safety_percentage": round((1 - (safe_score / risky_score if risky_score > 0 else 0)) * 100, 1) if risky_score > 0 else 0
        }

        return jsonify(response)

    except Exception as e:
        print(f"❌ Error: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/graph_stats')
def graph_stats():
    """Get statistics about the loaded graph"""
    if G is None:
        return jsonify({"error": "Graph not loaded"}), 503
    
    try:
        # Calculate average safety weight
        safety_weights = []
        for u, v, data in G.edges(data=True):
            if 'safety_weight' in data:
                try:
                    safety_weights.append(float(data['safety_weight']))
                except:
                    pass
        
        avg_safety = sum(safety_weights) / len(safety_weights) if safety_weights else 0
        
        stats = {
            "nodes": len(G.nodes),
            "edges": len(G.edges),
            "avg_degree": round(sum(dict(G.degree()).values()) / len(G.nodes), 2) if len(G.nodes) > 0 else 0,
            "is_directed": G.is_directed(),
            "avg_safety_weight": round(avg_safety, 2),
            "graph_file_size": f"{os.path.getsize(GRAPH_FILE) / (1024*1024):.2f} MB" if os.path.exists(GRAPH_FILE) else "0 MB"
        }
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Load graph on startup
print("=" * 60)
print("🚀 Starting Safe Route API Server")
print("=" * 60)
print(f"📁 Base directory: {BASE_DIR}")
print(f"📁 Graph file path: {GRAPH_FILE}")
print(f"🔗 Google Drive ID: {GOOGLE_DRIVE_GRAPH_ID}")
print("=" * 60)

load_graph()

if G is not None:
    print("✅ Server ready to accept requests!")
else:
    print("⚠️  Server started but graph failed to load!")
print("=" * 60)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)