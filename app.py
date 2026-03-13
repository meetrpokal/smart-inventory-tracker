from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import json
import time
import os
import re
from pymongo import MongoClient
from datetime import datetime
import heapq

app = Flask(__name__)
app.secret_key = 'super_secret_inventory_key_123'

import traceback

# Setup MongoDB Connection
MONGO_URI = os.getenv("MONGO_URI")
client = None
collection = None

if MONGO_URI:
    try:
        # Some servers need standard configurations to bypass tricky TLS requirements
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000, connectTimeoutMS=10000, socketTimeoutMS=10000)
        # Attempt a ping to confirm connection
        client.admin.command('ping')
        db = client.inventory_db
        collection = db.inventory_data
        print("MongoDB Connected Successfully!")
    except Exception as e:
        print(f"Failed to connect to MongoDB: {e}")
        traceback.print_exc()
        client = None
        collection = None

# Temporary storage for inventory data (Local Fallback)
INVENTORY_FILE = 'inventory_data.json'
USERS_FILE = 'users.json'

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            if request.path.startswith('/api/') or request.path in ['/get_inventory', '/check_expiry', '/export_csv'] or request.path.startswith('/check_low_stock'):
                return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def load_users():
    if collection is not None:
        try:
            doc = collection.find_one({"_id": "users_list"})
            if doc:
                return doc.get("users", {})
        except Exception as e:
            pass
    try:
        import os
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        pass
    return {}

def save_users(users_data):
    if collection is not None:
        try:
            collection.update_one({"_id": "users_list"}, {"$set": {"users": users_data}}, upsert=True)
            return
        except Exception as e:
            pass
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump(users_data, f)
    except Exception as e:
        pass

def load_inventory(username):
    if collection is not None:
        try:
            doc = collection.find_one({"_id": f"inventory_{username}"})
            if doc:
                doc.pop('_id', None)
                return doc
        except Exception as e:
            print(f"Error reading from MongoDB: {e}")
            
    try:
        import os
        if os.path.exists(INVENTORY_FILE):
            with open(INVENTORY_FILE, 'r') as f:
                all_data = json.load(f)
                
                if 'stock' in all_data:
                    old_data = all_data.copy()
                    all_data = {'default_admin': old_data}
                    with open(INVENTORY_FILE, 'w') as fw:
                        json.dump(all_data, fw)
                        
                return all_data.get(username, {"stock": {}, "expiry": []})
    except Exception as e:
        print(f"Error reading local JSON: {e}")
        
    return {"stock": {}, "expiry": []}

def save_inventory(username, data):
    if collection is not None:
        try:
            collection.update_one({"_id": f"inventory_{username}"}, {"$set": data}, upsert=True)
            return
        except Exception as e:
            print(f"Error writing to MongoDB: {e}")
    
    try:
        all_data = {}
        import os
        if os.path.exists(INVENTORY_FILE):
            try:
                with open(INVENTORY_FILE, 'r') as f:
                    all_data = json.load(f)
                    if 'stock' in all_data:
                        old_data = all_data.copy()
                        all_data = {'default_admin': old_data}
            except:
                pass
                
        all_data[username] = data
        with open(INVENTORY_FILE, 'w') as f:
            json.dump(all_data, f)
    except Exception as e:
        print(f"Error writing local JSON: {e}")

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
@login_required
def index():
    return render_template('index.html', username=session['username'])

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.json
        username = data.get('username')
        password = data.get('password')
        
        users = load_users()
        if username in users and check_password_hash(users[username]['password'], password):
            session['username'] = username
            return jsonify({'status': 'success'})
        return jsonify({'status': 'error', 'message': 'Invalid credentials'})
    return render_template('login.html')

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    users = load_users()
    if username in users:
        return jsonify({'status': 'error', 'message': 'Organization ID already exists'})
        
    users[username] = {
        'password': generate_password_hash(password)
    }
    save_users(users)
    session['username'] = username
    return jsonify({'status': 'success'})

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/add_stock', methods=['POST'])
@login_required
def add_stock():
    username = session['username']
    product = request.form['product']
    quantity = int(request.form['quantity'])
    expiry = request.form.get('expiry', '')
    
    data = load_inventory(username)
    
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
    
    save_inventory(username, data)
    
    return jsonify({
        'status': 'success',
        'message': f'Added {quantity} of {product}',
        'inventory': data['stock']
    })

@app.route('/remove_stock', methods=['POST'])
@login_required
def remove_stock():
    username = session['username']
    product = request.form['product']
    quantity = int(request.form['quantity'])
    
    data = load_inventory(username)
    
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
    
    save_inventory(username, data)
    
    return jsonify({
        'status': 'success',
        'message': f'Removed {quantity} of {product}',
        'inventory': data['stock']
    })

@app.route('/get_inventory')
@login_required
def get_inventory():
    username = session['username']
    data = load_inventory(username)
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
@login_required
def check_expiry():
    username = session['username']
    data = load_inventory(username)
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
@login_required
def check_low_stock(threshold):
    username = session['username']
    data = load_inventory(username)
    
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
@login_required
def export_csv():
    username = session['username']
    data = load_inventory(username)
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