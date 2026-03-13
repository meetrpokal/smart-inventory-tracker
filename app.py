from flask import Flask, render_template, request, jsonify, send_file
import json
import time
import os
import re
from pymongo import MongoClient
from datetime import datetime
import heapq

app = Flask(__name__)

# Setup MongoDB Connection
MONGO_URI = os.getenv("MONGO_URI")

if MONGO_URI:
    client = MongoClient(MONGO_URI)
    db = client.inventory_db
    collection = db.inventory_data
else:
    client = None
    collection = None

# Temporary storage for inventory data (Local Fallback)
INVENTORY_FILE = 'inventory_data.json'

def load_inventory():
    # If on Vercel with MongoDB connected
    if collection is not None:
        doc = collection.find_one({"_id": "main_inventory"})
        if doc:
            doc.pop('_id', None)
            return doc
        return {"stock": {}, "expiry": []}
        
    # If running locally without MongoDB
    if os.path.exists(INVENTORY_FILE):
        with open(INVENTORY_FILE, 'r') as f:
            return json.load(f)
    return {"stock": {}, "expiry": []}

def save_inventory(data):
    if collection is not None:
        collection.update_one({"_id": "main_inventory"}, {"$set": data}, upsert=True)
    else:
        with open(INVENTORY_FILE, 'w') as f:
            json.dump(data, f)

GUJARAT_GRAPH = {
    "Ahmedabad": {"Gandhinagar": 30, "Surat": 270, "Vadodara": 110, "Rajkot": 215, "Surendranagar": 120, "Nadiad": 55, "Himmatnagar": 85},
    "Gandhinagar": {"Ahmedabad": 30, "Kalol": 15},
    "Surat": {"Ahmedabad": 270, "Vadodara": 150, "Valsad": 70, "Navsari": 30, "Bharuch": 60},
    "Vadodara": {"Surat": 150, "Ahmedabad": 110, "Anand": 45, "Godhra": 65, "Bharuch": 75},
    "Rajkot": {"Jamnagar": 90, "Ahmedabad": 215, "Bhuj": 240, "Morbi": 65, "Jetpur": 65},
    "Jamnagar": {"Rajkot": 90, "Bhuj": 135, "Dwarka": 130},
    "Bhuj": {"Rajkot": 240, "Jamnagar": 135, "Deesa": 290},
    "Valsad": {"Surat": 70, "Vapi": 20},
    "Vapi": {"Valsad": 20, "Navsari": 35},
    "Navsari": {"Surat": 30, "Vapi": 35},
    "Mehsana": {"Palanpur": 85, "Kalol": 40},
    "Palanpur": {"Mehsana": 85, "Deesa": 55},
    "Deesa": {"Palanpur": 55, "Bhuj": 290},
    "Surendranagar": {"Ahmedabad": 120, "Bhavnagar": 100, "Morbi": 90},
    "Botad": {"Bhavnagar": 70},
    "Bhavnagar": {"Botad": 70, "Surendranagar": 100, "Amreli": 90},
    "Anand": {"Vadodara": 45, "Nadiad": 20},
    "Nadiad": {"Anand": 20, "Ahmedabad": 55},
    "Dahod": {"Godhra": 80},
    "Godhra": {"Dahod": 80, "Vadodara": 65},
    "Amreli": {"Bhavnagar": 90, "Junagadh": 110},
    "Junagadh": {"Amreli": 110, "Porbandar": 85, "Jetpur": 45, "Veraval": 75},
    "Porbandar": {"Junagadh": 85, "Dwarka": 105, "Mangrol": 40},
    "Dwarka": {"Porbandar": 105, "Jamnagar": 130},
    "Morbi": {"Rajkot": 65, "Surendranagar": 90},
    "Modasa": {"Himmatnagar": 40},
    "Himmatnagar": {"Modasa": 40, "Ahmedabad": 85},
    "Kalol": {"Gandhinagar": 15, "Mehsana": 40},
    "Jetpur": {"Rajkot": 65, "Junagadh": 45},
    "Mangrol": {"Porbandar": 40, "Veraval": 60},
    "Veraval": {"Mangrol": 60, "Junagadh": 75},
    "Bharuch": {"Vadodara": 75, "Surat": 60, "Ankleshwar": 12},
    "Ankleshwar": {"Bharuch": 12}
}

def find_shortest_path(start, end):
    if start not in GUJARAT_GRAPH or end not in GUJARAT_GRAPH:
        return {'status': 'error', 'message': 'Invalid city selection'}
        
    if start == end:
        return {
            'status': 'success',
            'path': [start],
            'distances': [0],
            'total_distance': 0
        }
    
    dist = {node: float('inf') for node in GUJARAT_GRAPH}
    parent = {}
    dist[start] = 0
    pq = [(0, start)]
    
    while pq:
        cur_dist, node = heapq.heappop(pq)
        
        if cur_dist > dist[node]:
            continue
            
        for nei, weight in GUJARAT_GRAPH[node].items():
            if dist[node] + weight < dist[nei]:
                dist[nei] = dist[node] + weight
                parent[nei] = node
                heapq.heappush(pq, (dist[nei], nei))
                
    if dist[end] == float('inf'):
        return {'status': 'error', 'message': f'No path found between {start} and {end}'}
        
    # Reconstruct path
    path = []
    at = end
    while at != start:
        path.append(at)
        at = parent[at]
    path.append(start)
    path.reverse()
    
    # Calculate cumulative distances
    cumulative_dists = [0]
    current_dist = 0
    for i in range(1, len(path)):
        weight = GUJARAT_GRAPH[path[i-1]][path[i]]
        current_dist += weight
        cumulative_dists.append(current_dist)
        
    return {
        'status': 'success',
        'path': path,
        'distances': cumulative_dists,
        'total_distance': dist[end]
    }

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/add_stock', methods=['POST'])
def add_stock():
    product = request.form['product']
    quantity = int(request.form['quantity'])
    expiry = request.form.get('expiry', '')
    
    data = load_inventory()
    
    # Add to stock
    if product in data['stock']:
        data['stock'][product] += quantity
    else:
        data['stock'][product] = quantity
    
    # Add to expiry if provided
    if expiry:
        expiry_timestamp = int(datetime.strptime(expiry, '%Y-%m-%d').timestamp())
        data['expiry'].append({
            'product': product,
            'quantity': quantity,
            'expiry': expiry_timestamp
        })
    
    save_inventory(data)
    
    return jsonify({
        'status': 'success',
        'message': f'Added {quantity} of {product}',
        'inventory': data['stock']
    })

@app.route('/remove_stock', methods=['POST'])
def remove_stock():
    product = request.form['product']
    quantity = int(request.form['quantity'])
    
    data = load_inventory()
    
    if product not in data['stock'] or data['stock'][product] < quantity:
        return jsonify({
            'status': 'error',
            'message': f'Not enough stock of {product}'
        })
    
    data['stock'][product] -= quantity
    if data['stock'][product] == 0:
        del data['stock'][product]
    
    # Record recent sale (simplified)
    sale = {
        'product': product,
        'timestamp': int(time.time()),
        'quantity': quantity
    }
    if 'sales' not in data:
        data['sales'] = []
    data['sales'].append(sale)
    
    save_inventory(data)
    
    return jsonify({
        'status': 'success',
        'message': f'Removed {quantity} of {product}',
        'inventory': data['stock']
    })

@app.route('/get_inventory')
def get_inventory():
    data = load_inventory()
    today = int(time.time())
    
    # Prepare inventory with expiry status
    inventory = []
    for product, quantity in data['stock'].items():
        inventory.append({
            'product': product,
            'quantity': quantity,
            'expiry': 'N/A',
            'status': 'Valid'
        })
    
    # Add expiry information
    for item in data.get('expiry', []):
        expiry_date = datetime.fromtimestamp(item['expiry']).strftime('%Y-%m-%d')
        status = 'Expired' if item['expiry'] <= today else 'Valid'
        
        # Find if product already in inventory
        found = False
        for inv_item in inventory:
            if inv_item['product'] == item['product']:
                inv_item['expiry'] = expiry_date
                inv_item['status'] = status
                found = True
                break
        
        if not found:
            inventory.append({
                'product': item['product'],
                'quantity': item['quantity'],
                'expiry': expiry_date,
                'status': status
            })
    
    return jsonify({
        'status': 'success',
        'inventory': inventory
    })

@app.route('/check_expiry')
def check_expiry():
    data = load_inventory()
    today = int(time.time())
    
    expired = []
    for item in data.get('expiry', []):
        if item['expiry'] <= today:
            expired.append({
                'product': item['product'],
                'quantity': item['quantity'],
                'expiry_date': datetime.fromtimestamp(item['expiry']).strftime('%Y-%m-%d')
            })
    
    return jsonify({
        'status': 'success',
        'expired_items': expired
    })

@app.route('/check_low_stock/<int:threshold>')
def check_low_stock(threshold):
    data = load_inventory()
    
    low_stock = []
    for product, quantity in data['stock'].items():
        if quantity <= threshold:
            low_stock.append({
                'product': product,
                'quantity': quantity
            })
    
    return jsonify({
        'status': 'success',
        'low_stock': low_stock
    })

@app.route('/export_csv')
def export_csv():
    data = load_inventory()
    today = int(time.time())
    
    csv_data = "Product,Quantity,Expiry,Status\n"
    
    # Add stock items
    for product, quantity in data['stock'].items():
        csv_data += f"{product},{quantity},N/A,Valid\n"
    
    # Add expiry items
    for item in data.get('expiry', []):
        expiry_date = datetime.fromtimestamp(item['expiry']).strftime('%Y-%m-%d')
        status = 'Expired' if item['expiry'] <= today else 'Valid'
        csv_data += f"{item['product']},{item['quantity']},{expiry_date},{status}\n"
    
    with open('inventory_report.csv', 'w') as f:
        f.write(csv_data)
    
    return send_file(
        'inventory_report.csv',
        as_attachment=True,
        download_name='inventory_report.csv'
    )

@app.route('/get_cities')
def get_cities():
    # List of cities 
    cities = [
        "Ahmedabad", "Gandhinagar", "Surat", "Vadodara", "Rajkot", "Jamnagar", 
        "Bhuj", "Valsad", "Vapi", "Navsari", "Mehsana", "Palanpur", 
        "Deesa", "Surendranagar", "Botad", "Bhavnagar", "Anand", "Nadiad", 
        "Dahod", "Godhra", "Amreli", "Junagadh", "Porbandar", "Dwarka", 
        "Morbi", "Modasa", "Himmatnagar", "Kalol", "Jetpur", "Mangrol", 
        "Veraval", "Bharuch", "Ankleshwar"
    ]
    cities.sort()
    return jsonify({'cities': cities})

@app.route('/find_path', methods=['POST'])
def find_path():
    from_city = request.form['from']
    to_city = request.form['to']
    
    # Use native Python pathfinding
    result = find_shortest_path(from_city, to_city)
    
    if result is None:
        return jsonify({
            'status': 'error',
            'message': 'Error finding path'
        })
    
    if result['status'] == 'error':
        return jsonify(result)
    
    # Return successful result
    return jsonify({
        'status': 'success',
        'from': from_city,
        'to': to_city,
        'path': result['path'],
        'distances': result['distances'],
        'total_distance': result['total_distance']
    })

if __name__ == '__main__':
    app.run(debug=True)