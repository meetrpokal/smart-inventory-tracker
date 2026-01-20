from flask import Flask, render_template, request, jsonify, send_file
import json
import time
import os
import re
from datetime import datetime
import subprocess
import tempfile

app = Flask(__name__)

# Temporary storage for inventory data
INVENTORY_FILE = 'inventory_data.json'

def load_inventory():
    if os.path.exists(INVENTORY_FILE):
        with open(INVENTORY_FILE, 'r') as f:
            return json.load(f)
    return {"stock": {}, "expiry": []}

def save_inventory(data):
    with open(INVENTORY_FILE, 'w') as f:
        json.dump(data, f)

def compile_cpp_if_needed():
    """Compile the C++ program if it doesn't exist or is older than source"""
    cpp_file = 'inventory.cpp'  # Your C++ source file name
    exe_file = 'inventory'      # Executable name
    
    # Check if we need to compile
    need_compile = True
    if os.path.exists(exe_file) and os.path.exists(cpp_file):
        exe_time = os.path.getmtime(exe_file)
        cpp_time = os.path.getmtime(cpp_file)
        need_compile = cpp_time > exe_time
    
    if need_compile:
        try:
            result = subprocess.run(['g++', '-o', exe_file, cpp_file], 
                                  capture_output=True, text=True, check=True)
            print("C++ program compiled successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Compilation error: {e.stderr}")
            return False
    return True

def run_cpp_pathfinding(from_city, to_city):
    """Run the C++ program to find shortest path"""
    if not compile_cpp_if_needed():
        return None
    
    try:
        input_commands = f"8\n{from_city}\n{to_city}\n0\n"
        
        # Run C++ program
        result = subprocess.run(['./inventory'], 
                              input=input_commands, 
                              capture_output=True, 
                              text=True, 
                              timeout=10)
        
        if result.returncode != 0:
            print(f"C++ program error: {result.stderr}")
            return None
            
        # Parse the output
        output = result.stdout
        return parse_path_output(output)
        
    except subprocess.TimeoutExpired:
        print("C++ program timed out")
        return None
    except Exception as e:
        print(f"Error running C++ program: {e}")
        return None

def parse_path_output(output):
    """Parse the C++ program output to extract path information"""
    try:
        lines = output.strip().split('\n')
        
        # Look for PATH_START and PATH_END markers
        path_start_idx = -1
        path_end_idx = -1
        total_cost = 0
        
        for i, line in enumerate(lines):
            if 'PATH_START' in line:
                path_start_idx = i
            elif 'PATH_END' in line:
                path_end_idx = i
            elif 'Total cost:' in line:
                # Extract total cost
                cost_match = re.search(r'Total cost:\s*(\d+)', line)
                if cost_match:
                    total_cost = int(cost_match.group(1))
        
        if path_start_idx == -1 or path_end_idx == -1:
            # Check for "No path" message
            if any('No path' in line for line in lines):
                return {
                    'status': 'error',
                    'message': 'No path found between the cities'
                }
            return None
        
        # Extract path information
        path_lines = lines[path_start_idx + 2:path_end_idx]  # Skip PATH_START and header
        path = []
        distances = []
        
        for line in path_lines:
            if line.strip():
                # Parse format: "CityName (distance)"
                match = re.match(r'(.+?)\s*\((\d+)\)', line.strip())
                if match:
                    city = match.group(1).strip()
                    distance = int(match.group(2))
                    path.append(city)
                    distances.append(distance)
        
        if not path:
            return None
            
        return {
            'status': 'success',
            'path': path,
            'distances': distances,
            'total_distance': total_cost
        }
        
    except Exception as e:
        print(f"Error parsing path output: {e}")
        return None

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
    return jsonify({'cities': cities})

@app.route('/find_path', methods=['POST'])
def find_path():
    from_city = request.form['from']
    to_city = request.form['to']
    
    # Use the actual C++ pathfinding
    result = run_cpp_pathfinding(from_city, to_city)
    
    if result is None:
        return jsonify({
            'status': 'error',
            'message': 'Error running pathfinding algorithm'
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