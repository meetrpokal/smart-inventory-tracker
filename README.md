# Smart Inventory Tracker

An inventory tracker system with web interface and pathfinding capabilities for Gujarat cities. Built with C++ backend and Flask web framework.

## Features

- **Inventory Management**
  - Add/Remove stock with expiry tracking
  - Low stock alerts
  - Expired items detection
  - CSV export functionality

- **Advanced Analytics**
  - Real-time inventory tracking
  - Demand spike detection
  - FIFO expiry management

- **Pathfinding System**
  - Shortest path calculation between Gujarat cities
  - Interactive web visualization
  - Dijkstra's algorithm implementation

## Tech Stack

- **Backend**: C++ (Core logic), Python Flask (Web API)
- **Frontend**: HTML, CSS, JavaScript, Bootstrap 5
- **Visualization**: Chart.js
- **Data**: JSON file storage

## Project Structure

```
inventory-tracker/
├── inventory.cpp         # C++ inventory system
├── app.py                # Flask web application
├── templates/
│   └── index.html        # Web interface
├── inventory_data.json   # Data storage (auto-generated)
└── README.md
```

## Prerequisites

- C++ compiler (g++)
- Python 3.x
- Flask

## Installation & Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/meetrpokal/smart-inventory-tracker.git
   cd smart-inventory-tracker
   ```

2. **Install Python dependencies**
   ```bash
   pip install flask
   ```

3. **Compile C++ program**
   ```bash
   g++ -o inventory inventory.cpp
   ```

4. **Create templates directory**
   ```bash
   mkdir templates
   # Move index.html to templates/ folder
   ```

## Usage

### Running the Web Application

1. **Start the Flask server**
   ```bash
   python app.py
   ```

2. **Open browser and navigate to**
   ```
   http://localhost:5000
   ```

