// #include <iostream>
// #include <unordered_map>
// #include <queue>
// #include <deque>
// #include <string>
// #include <ctime>
// #include <fstream>
// #include <sstream>
// #include <vector>
// #include <functional>
// #include <algorithm>
// #include <climits>
// #include <iomanip>
#include <bits/stdc++.h>

using namespace std;

// -- Struct for expiry tracking --
struct Batch {
    string product;
    int quantity;
    time_t expiry;
    bool operator>(const Batch& other) const {
        return expiry > other.expiry;
    }
};

//WarehouseGraph with Dijkstra for picking path 
class WarehouseGraph {
private:
    unordered_map<string, vector<pair<string, int>>> adj;

public:
    void addEdge(const string& from, const string& to, int weight) {
        adj[from].push_back({to, weight});
        adj[to].push_back({from, weight});
    }

    void shortestPath(const string& start, const string& end) {
        // Add early return if start == end
        if (start == end) {
        cout << "PATH_START\n";
        cout << "Shortest path from " << start << " to " << end << ":\n";
        cout << start << " (0)\n";
        cout << "PATH_END\n";
        cout << "Total cost: 0\n";
        return;
        }

        unordered_map<string, int> dist;
        unordered_map<string, string> parent;
        priority_queue<pair<int, string>, vector<pair<int, string>>, greater<>> pq;

        // Initialize distances
        for (const auto& node : adj) {
            dist[node.first] = INT_MAX;
        }
        dist[start] = 0;
        pq.push({0, start});

        // Dijkstra's algorithm
        while (!pq.empty()) {
            auto [curDist, node] = pq.top(); 
            pq.pop();

            if (curDist > dist[node]) continue;

            for (auto& [nei, weight] : adj[node]) {
                if (dist[node] + weight < dist[nei]) {
                    dist[nei] = dist[node] + weight;
                    parent[nei] = node;
                    pq.push({dist[nei], nei});
                }
            }
        }

        // Output the path in parseable format
        if (dist[end] == INT_MAX) {
            cout << "No path from " << start << " to " << end << "\n";
            return;
        }

        // Reconstruct path
        vector<string> path;
        string at = end;
        while (at != start) {
            if (parent.find(at) == parent.end()) {
                cout << "Path broken. Could not trace back from " << end << " to " << start << "\n";
                return;
            }
            path.push_back(at);
            at = parent[at];
        }
        path.push_back(start);
        reverse(path.begin(), path.end());

        // Calculate cumulative distances for each step
        vector<int> cumulative_dists;
        int current_dist = 0;
        cumulative_dists.push_back(current_dist);
        
        for (size_t i = 1; i < path.size(); i++) {
            // Find the edge weight between path[i-1] and path[i]
            for (const auto& [nei, weight] : adj[path[i-1]]) {
                if (nei == path[i]) {
                    current_dist += weight;
                    break;
                }
            }
            cumulative_dists.push_back(current_dist);
        }

        // Print in parseable format for Flask
        cout << "PATH_START\n";
        cout << "Shortest path from " << start << " to " << end << ":\n";
        for (size_t i = 0; i < path.size(); i++) {
            cout << path[i] << " (" << cumulative_dists[i] << ")\n";
        }
        cout << "PATH_END\n";
        cout << "Total cost: " << dist[end] << "\n";
    }
};


class InventoryManager {
private:
    unordered_map<string, int> stock;
    priority_queue<pair<int, string>,
                  vector<pair<int, string>>,
                  greater<>> lowStockHeap;

    deque<pair<time_t, string>> recentSales;
    priority_queue<Batch, vector<Batch>, greater<>> expiryHeap;

    WarehouseGraph graph;

public:
    void addStock(const string& product, int qty, time_t expiry = 0) {
        if (product.empty()) {
            cout << "[!] Product name cannot be empty\n";
            return;
        }
        if (qty <= 0) {
            cout << "[!] Quantity must be positive\n";
            return;
        }

        stock[product] += qty;
        if (expiry != 0) {
            expiryHeap.push({product, qty, expiry});
        }
        lowStockHeap.push({stock[product], product});
        cout << "[+] Added " << qty << " of '" << product << "'\n";
    }

    void removeStock(const string& product, int qty) {
        if (stock.find(product) == stock.end()) {
            cout << "[!] Product not found\n";
            return;
        }
        if (stock[product] < qty) {
            cout << "[!] Not enough stock\n";
            return;
        }
        stock[product] -= qty;
        time_t now = time(0);
        for (int i = 0; i < qty; i++) {
            recentSales.push_back({now, product});
        }
        cout << "[-] Removed " << qty << " of '" << product << "'\n";
    }

    unordered_map<string, int> getStock() {
        return stock;
    }

    void checkLowStock(int threshold) {
        auto temp = lowStockHeap;
        cout << "\nLow Stock:\n";
        bool found = false;
        while (!temp.empty()) {
            auto [qty, prod] = temp.top(); 
            temp.pop();
            if (qty <= threshold) {
                cout << prod << ": " << qty << "\n";
                found = true;
            }
        }
        if (!found) {
            cout << "No low stock items found\n";
        }
    }

    void detectDemandSpike(int windowSec, int spikeThreshold) {
        time_t now = time(0);
        while (!recentSales.empty() && now - recentSales.front().first > windowSec) {
            recentSales.pop_front();
        }

        unordered_map<string, int> freq;
        for (auto& [t, p] : recentSales) {
            freq[p]++;
        }
        
        cout << "\nDemand Spikes:\n";
        bool found = false;
        for (auto& [prod, count] : freq) {
            if (count >= spikeThreshold) {
                cout << prod << ": " << count << "\n";
                found = true;
            }
        }
        if (!found) {
            cout << "No demand spikes detected\n";
        }
    }

    void checkExpiry(time_t today) {
        cout << "\nExpired Batches:\n";
        bool found = false;
        while (!expiryHeap.empty() && expiryHeap.top().expiry <= today) {
            auto b = expiryHeap.top(); 
            expiryHeap.pop();
            cout << "[EXPIRED] " << b.product << " Qty: " << b.quantity << "\n";
            found = true;
        }
        if (!found) {
            cout << "No expired items found\n";
        }
    }

    void exportToCSV(const string& filename) {
        ofstream file(filename);
        if (!file.is_open()) {
            cout << "[!] Could not open file " << filename << " for writing\n";
            return;
        }

        file << "Product,Quantity,Expiry,Status\n";
        time_t today = time(0);

        // Export non-expiry stock
        // for (auto& [prod, qty] : stock) {
        //     file << prod << "," << qty << "," << "N/A,Valid\n";
        // }

        // Export expiry batches
        priority_queue<Batch, vector<Batch>, greater<>> temp = expiryHeap;
        while (!temp.empty()) {
            Batch b = temp.top(); 
            temp.pop();
            char buf[50];
            strftime(buf, sizeof(buf), "%Y-%m-%d", localtime(&b.expiry));
            string status = (b.expiry <= today) ? "Expired" : "Valid";
            file << b.product << "," << b.quantity << "," << buf << "," << status << "\n";
        }

        file.close();
        cout << "\nDetailed inventory exported to " << filename << "\n";
    }

    WarehouseGraph& getGraph() {
        return graph;
    }
};

//Gujarat city map 
void preloadGujaratCityMap(WarehouseGraph& g) {
    g.addEdge("Ahmedabad", "Gandhinagar", 30);
    g.addEdge("Ahmedabad", "Surat", 270);
    g.addEdge("Surat", "Vadodara", 150);
    g.addEdge("Vadodara", "Ahmedabad", 110);
    g.addEdge("Rajkot", "Jamnagar", 90);
    g.addEdge("Rajkot", "Ahmedabad", 215);
    g.addEdge("Bhuj", "Rajkot", 240);
    g.addEdge("Bhuj", "Jamnagar", 135);
    g.addEdge("Surat", "Valsad", 70);
    g.addEdge("Valsad", "Vapi", 20);
    g.addEdge("Vapi", "Navsari", 35);
    g.addEdge("Navsari", "Surat", 30);
    g.addEdge("Mehsana", "Palanpur", 85);
    g.addEdge("Palanpur", "Deesa", 55);
    g.addEdge("Deesa", "Bhuj", 290);
    g.addEdge("Surendranagar", "Ahmedabad", 120);
    g.addEdge("Botad", "Bhavnagar", 70);
    g.addEdge("Bhavnagar", "Surendranagar", 100);
    g.addEdge("Anand", "Vadodara", 45);
    g.addEdge("Nadiad", "Anand", 20);
    g.addEdge("Nadiad", "Ahmedabad", 55);
    g.addEdge("Dahod", "Godhra", 80);
    g.addEdge("Godhra", "Vadodara", 65);
    g.addEdge("Amreli", "Bhavnagar", 90);
    g.addEdge("Junagadh", "Amreli", 110);
    g.addEdge("Junagadh", "Porbandar", 85);
    g.addEdge("Porbandar", "Dwarka", 105);
    g.addEdge("Dwarka", "Jamnagar", 130);
    g.addEdge("Morbi", "Rajkot", 65);
    g.addEdge("Morbi", "Surendranagar", 90);
    g.addEdge("Modasa", "Himmatnagar", 40);
    g.addEdge("Himmatnagar", "Ahmedabad", 85);
    g.addEdge("Kalol", "Gandhinagar", 15);
    g.addEdge("Kalol", "Mehsana", 40);
    g.addEdge("Jetpur", "Rajkot", 65);
    g.addEdge("Jetpur", "Junagadh", 45);
    g.addEdge("Mangrol", "Porbandar", 40);
    g.addEdge("Veraval", "Mangrol", 60);
    g.addEdge("Veraval", "Junagadh", 75);
    g.addEdge("Bharuch", "Vadodara", 75);
    g.addEdge("Bharuch", "Surat", 60);
    g.addEdge("Ankleshwar", "Bharuch", 12);
}

void normalizeInput(string& input) {
    // Remove leading/trailing whitespace
    input.erase(0, input.find_first_not_of(" \t\r\n"));
    input.erase(input.find_last_not_of(" \t\r\n") + 1);
    
    // Convert to proper case (first letter uppercase, rest lowercase)
    if (!input.empty()) {
        input[0] = toupper(input[0]);
        for (size_t i = 1; i < input.length(); i++) {
            input[i] = tolower(input[i]);
        }
    }
}

// Also add this function to validate city names
bool isValidCity(const string& city, const vector<string>& validCities) {
    for (const string& validCity : validCities) {
        if (city == validCity) {
            return true;
        }
    }
    return false;
}

int main() {
    InventoryManager manager;
    WarehouseGraph& g = manager.getGraph();
    preloadGujaratCityMap(g);

    int choice;
    string product;
    int quantity;
    string expiryStr;
    time_t expiry = 0;

    do {
        cout << "\n===== Inventory Menu =====\n";
        cout << "1. Add Stock\n2. Remove Stock\n3. Show Inventory\n4. Check Low Stock\n";
        cout << "5. Detect Demand Spike\n6. Check Expiry\n7. Export to CSV\n";
        cout << "8. Find Shortest Picking Path\n9. Add Path Between Locations\n0. Exit\n";
        cout << "Enter choice: ";
        cin >> choice;
        cin.ignore();

        switch (choice) {
            case 1: {
                cout << "Enter product name: ";
                getline(cin, product);
                if (product.empty()) {
                    cout << "[!] Product name cannot be empty\n";
                    break;
                }
                cout << "Enter quantity: ";
                cin >> quantity;
                if (quantity <= 0) {
                    cout << "[!] Quantity must be positive\n";
                    cin.ignore();
                    break;
                }
                cin.ignore();
                cout << "Enter expiry date (YYYY-MM-DD) or leave blank: ";
                getline(cin, expiryStr);
                if (!expiryStr.empty()) {
                    tm tm = {};
                    istringstream ss(expiryStr);
                    if (!(ss >> get_time(&tm, "%Y-%m-%d"))) {
                        cout << "[!] Invalid date format. Use YYYY-MM-DD\n";
                        break;
                    }
                    expiry = mktime(&tm);
                }
                manager.addStock(product, quantity, expiry);
                break;
            }
            case 2: {
                cout << "Enter product name: ";
                getline(cin, product);
                if (product.empty()) {
                    cout << "Product name cannot be empty\n";
                    break;
                }
                cout << "Enter quantity: ";
                cin >> quantity;
                if (quantity <= 0) {
                    cout << "Quantity must be positive\n";
                    cin.ignore();
                    break;
                }
                cin.ignore();
                manager.removeStock(product, quantity);
                break;
            }
            case 3: {
                auto stock = manager.getStock();
                cout << "\nCurrent Inventory:\n";
                if (stock.empty()) {
                    cout << "No items in inventory\n";
                } else {
                    for (auto& [prod, qty] : stock) {
                        cout << prod << ": " << qty << "\n";
                    }
                }
                break;
            }
            case 4: {
                cout << "Enter low stock threshold: ";
                cin >> quantity;
                if (quantity <= 0) {
                    cout << "Threshold must be positive\n";
                    cin.ignore();
                    break;
                }
                cin.ignore();
                manager.checkLowStock(quantity);
                break;
            }
            case 5: {
                manager.detectDemandSpike(60, 3);
                break;
            }
            case 6: {
                manager.checkExpiry(time(0));
                break;
            }
            case 7: {
                manager.exportToCSV("inventory_report.csv");
                break;
            }
           case 8: {
                string from, to;
                vector<string> validCities = {
                    "Ahmedabad", "Gandhinagar", "Surat", "Vadodara", "Rajkot", "Jamnagar", 
                    "Bhuj", "Valsad", "Vapi", "Navsari", "Mehsana", "Palanpur", 
                    "Deesa", "Surendranagar", "Botad", "Bhavnagar", "Anand", "Nadiad", 
                    "Dahod", "Godhra", "Amreli", "Junagadh", "Porbandar", "Dwarka", 
                    "Morbi", "Modasa", "Himmatnagar", "Kalol", "Jetpur", "Mangrol", 
                    "Veraval", "Bharuch", "Ankleshwar"
                };
                
                cout << "Enter start location: ";
                getline(cin, from);
                normalizeInput(from);
                
                cout << "Enter end location: ";
                getline(cin, to);
                normalizeInput(to);
                
                // Validate input cities
                if (!isValidCity(from, validCities)) {
                    cout << "Invalid start city: " << from << "\n";
                    break;
                }
                
                if (!isValidCity(to, validCities)) {
                    cout << "Invalid destination city: " << to << "\n";
                    break;
                }
                
                // Call shortestPath on the graph object
                g.shortestPath(from, to);
                break;
            }
            case 9: {
                string from, to;
                int weight;
                cout << "Available Cities:\n";
                cout << "Ahmedabad, Gandhinagar, Surat, Vadodara, Rajkot, Jamnagar, Bhuj, Valsad, Vapi, Navsari, "
                     << "Mehsana, Palanpur, Deesa, Surendranagar, Botad, Bhavnagar, Anand, Nadiad, Dahod, Godhra, "
                     << "Amreli, Junagadh, Porbandar, Dwarka, Morbi, Modasa, Himmatnagar, Kalol, Jetpur, Mangrol, "
                     << "Veraval, Bharuch, Ankleshwar\n";
                
                cout << "Enter location 1: ";
                getline(cin, from);
                cout << "Enter location 2: ";
                getline(cin, to);
                cout << "Enter distance: ";
                cin >> weight;
                cin.ignore();
                
                // Add edge to the graph
                g.addEdge(from, to, weight);
                cout << "Path added between '" << from << "' and '" << to << "' with distance " << weight << "\n";
                break;
            }

            case 0: {
                cout << "Exiting...\n";
                break;
            }
            default: {
                cout << "Invalid choice. Try again.\n";
                break;
            }
        }
    } while (choice != 0);

    return 0;
}
