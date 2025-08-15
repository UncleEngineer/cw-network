# flask_server.py - Flask Web Server for Broadcasting Morse Code
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, disconnect
import socket
import threading
import datetime
import time
import json
from collections import deque

app = Flask(__name__)
app.config['SECRET_KEY'] = 'morse_code_secret_2024'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

class MorseFlaskServer:
    def __init__(self):
        # Server settings
        self.morse_host = '0.0.0.0'
        self.morse_port = 12345
        self.server_socket = None
        self.running = False
        
        # Text display settings
        self.current_line = ""
        self.line_length = 100
        self.last_char_time = time.time()
        self.word_gap_time = 1.5
        self.newline_timeout = 8.0
        
        # Device tracking
        self.connected_devices = {}
        self.device_colors = ['#e74c3c', '#2ecc71', '#3498db', '#f39c12', '#9b59b6', '#1abc9c']
        self.next_color_index = 0
        
        # Web clients tracking
        self.web_clients = set()
        
        # Message history for new clients
        self.message_history = deque(maxlen=1000)  # Keep last 1000 characters
        self.line_history = deque(maxlen=50)      # Keep last 50 lines
        
        # Auto-spacing control
        self.auto_space_added = False
        
        # Start timeout checker
        self.start_timeout_checker()
        
    def start_morse_server(self):
        """Start the Morse code receiver server"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.morse_host, self.morse_port))
            self.server_socket.listen(10)
            self.running = True
            
            print(f"Morse receiver started on {self.morse_host}:{self.morse_port}")
            
            # Start server thread
            server_thread = threading.Thread(target=self.morse_server_loop)
            server_thread.daemon = True
            server_thread.start()
            
            return True
            
        except Exception as e:
            print(f"Failed to start Morse server: {e}")
            return False
    
    def morse_server_loop(self):
        """Main Morse server loop"""
        while self.running:
            try:
                client_socket, client_address = self.server_socket.accept()
                
                # Handle client in separate thread
                client_thread = threading.Thread(
                    target=self.handle_morse_client, 
                    args=(client_socket, client_address)
                )
                client_thread.daemon = True
                client_thread.start()
                
            except socket.error as e:
                if self.running:
                    print(f"Morse socket error: {e}")
    
    def handle_morse_client(self, client_socket, client_address):
        """Handle Morse code from devices"""
        client_ip = client_address[0]
        
        # Assign color to device if new
        if client_ip not in self.connected_devices:
            device_color = self.device_colors[self.next_color_index % len(self.device_colors)]
            self.connected_devices[client_ip] = {
                'color': device_color,
                'last_seen': time.time(),
                'char_count': 0
            }
            self.next_color_index += 1
            
            # Broadcast device connection to web clients
            self.broadcast_device_update()
            print(f"New device connected: {client_ip}")
        
        # Update last seen time
        self.connected_devices[client_ip]['last_seen'] = time.time()
        
        try:
            data = client_socket.recv(1024).decode('utf-8')
            
            if data:
                self.process_morse_data(data, client_ip)
                
        except Exception as e:
            print(f"Error handling Morse client {client_address}: {e}")
        finally:
            client_socket.close()
    
    def process_morse_data(self, data, client_ip):
        """Process received morse code data"""
        try:
            lines = data.strip().split('\n')
            char = None
            morse = None
            
            for line in lines:
                if line.startswith("CHAR:"):
                    char = line.replace("CHAR:", "").strip()
                elif line.startswith("MORSE:"):
                    morse = line.replace("MORSE:", "").strip()
            
            if char and morse:
                # Skip explicit space characters
                if char == "[SPACE]":
                    return
                
                # Update device stats
                self.connected_devices[client_ip]['char_count'] += 1
                self.connected_devices[client_ip]['last_seen'] = time.time()
                
                # Process character
                device_color = self.connected_devices[client_ip]['color']
                self.add_character(char, client_ip, device_color, morse)
                
                # Broadcast to web clients
                self.broadcast_character(char, client_ip, device_color, morse)
                
                # Console log
                timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                device_count = len(self.connected_devices)
                print(f"[{timestamp}] {client_ip} -> {char} ({morse}) [Devices: {device_count}]")
                
        except Exception as e:
            print(f"Error processing Morse data: {e}")
    
    def add_character(self, char, client_ip, device_color, morse):
        """Add character to internal text buffer"""
        self.auto_space_added = False
        
        # Check if we need a new line
        if len(self.current_line) >= self.line_length:
            self.add_new_line()
        
        # Add character to current line
        self.current_line += char
        self.last_char_time = time.time()
        
        # Store in history
        char_data = {
            'char': char,
            'color': device_color,
            'device': client_ip,
            'morse': morse,
            'timestamp': time.time()
        }
        self.message_history.append(char_data)
    
    def add_new_line(self):
        """Start a new line"""
        if self.current_line.strip():
            line_data = {
                'text': self.current_line,
                'line_num': len(self.line_history) + 1,
                'timestamp': time.time()
            }
            self.line_history.append(line_data)
            
            # Broadcast line completion to web clients
            socketio.emit('line_complete', line_data)
        
        self.current_line = ""
    
    def add_auto_space(self):
        """Add automatic space"""
        if (self.current_line and 
            not self.current_line.endswith(" ") and 
            len(self.current_line) < self.line_length):
            
            self.current_line += " "
            
            # Broadcast auto-space to web clients
            socketio.emit('auto_space', {
                'type': 'space',
                'timestamp': time.time()
            })
            
            print(f"[AUTO] Added space after {self.word_gap_time}s pause")
    
    def start_timeout_checker(self):
        """Start the timeout checker thread"""
        def timeout_checker():
            while True:
                try:
                    current_time = time.time()
                    time_since_last_char = current_time - self.last_char_time
                    
                    if self.current_line and not self.auto_space_added:
                        if time_since_last_char > self.word_gap_time:
                            self.add_auto_space()
                            self.auto_space_added = True
                        elif time_since_last_char > self.newline_timeout:
                            self.add_new_line()
                            self.auto_space_added = True
                    
                    # Clean up old devices
                    self.cleanup_old_devices()
                    
                    time.sleep(0.1)
                    
                except Exception as e:
                    print(f"Timeout checker error: {e}")
                    time.sleep(1)
        
        timeout_thread = threading.Thread(target=timeout_checker)
        timeout_thread.daemon = True
        timeout_thread.start()
    
    def cleanup_old_devices(self):
        """Remove devices not seen for 30 seconds"""
        current_time = time.time()
        devices_to_remove = []
        
        for ip, info in self.connected_devices.items():
            if current_time - info['last_seen'] > 30:
                devices_to_remove.append(ip)
        
        if devices_to_remove:
            for ip in devices_to_remove:
                del self.connected_devices[ip]
                print(f"Device disconnected: {ip}")
            
            self.broadcast_device_update()
    
    def broadcast_character(self, char, client_ip, device_color, morse):
        """Broadcast character to all web clients"""
        char_data = {
            'char': char,
            'color': device_color,
            'device': client_ip,
            'morse': morse,
            'timestamp': time.time()
        }
        socketio.emit('new_character', char_data)
    
    def broadcast_device_update(self):
        """Broadcast device list update to web clients"""
        device_list = []
        for ip, info in self.connected_devices.items():
            device_list.append({
                'ip': ip,
                'color': info['color'],
                'char_count': info['char_count'],
                'last_seen': info['last_seen']
            })
        
        socketio.emit('device_update', {
            'devices': device_list,
            'count': len(device_list)
        })
    
    def get_local_ip(self):
        """Get local IP address"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except:
            return "127.0.0.1"

# Initialize the Morse server
morse_server = MorseFlaskServer()

# Flask routes
@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/api/status')
def api_status():
    """API endpoint for server status"""
    return jsonify({
        'running': morse_server.running,
        'devices': len(morse_server.connected_devices),
        'local_ip': morse_server.get_local_ip(),
        'morse_port': morse_server.morse_port
    })

@app.route('/api/history')
def api_history():
    """API endpoint for message history"""
    return jsonify({
        'lines': list(morse_server.line_history),
        'current_line': morse_server.current_line,
        'devices': list(morse_server.connected_devices.keys())
    })

# WebSocket events
@socketio.on('connect')
def handle_connect():
    """Handle web client connection"""
    client_id = request.sid
    morse_server.web_clients.add(client_id)
    
    print(f"✓ Web client connected: {client_id}")
    
    # Send current status to new client
    emit('status_update', {
        'devices': len(morse_server.connected_devices),
        'running': morse_server.running,
        'local_ip': morse_server.get_local_ip()
    })
    
    # Send device list
    morse_server.broadcast_device_update()
    
    # Send recent history
    emit('history_update', {
        'lines': list(morse_server.line_history)[-10:],  # Last 10 lines
        'current_line': morse_server.current_line
    })

@socketio.on('disconnect')
def handle_disconnect():
    """Handle web client disconnection"""
    client_id = request.sid
    morse_server.web_clients.discard(client_id)
    print(f"✗ Web client disconnected: {client_id}")

@socketio.on('request_clear')
def handle_clear():
    """Handle clear request from web client"""
    morse_server.line_history.clear()
    morse_server.message_history.clear()
    morse_server.current_line = ""
    
    socketio.emit('clear_display')
    print("📝 Display cleared by web client request")

# Test connection endpoint
@socketio.on('ping')
def handle_ping():
    """Handle ping from client"""
    emit('pong', {'status': 'ok', 'timestamp': time.time()})

if __name__ == '__main__':
    print("Flask Morse Code Broadcaster")
    print("=" * 40)
    
    # Start the Morse receiver server
    if morse_server.start_morse_server():
        local_ip = morse_server.get_local_ip()
        print(f"✓ Morse devices should connect to: {local_ip}:{morse_server.morse_port}")
        print(f"✓ Web interface available at: http://localhost:5000")
        print(f"✓ Web interface available at: http://{local_ip}:5000")
        print("✓ Starting Flask web server...")
        print()
        print("Web clients can connect to view live Morse code!")
        print("Press Ctrl+C to stop the server")
        print("-" * 50)
        
        try:
            # Start Flask-SocketIO server with better configuration
            socketio.run(app, 
                        host='0.0.0.0', 
                        port=5000, 
                        debug=False,
                        allow_unsafe_werkzeug=True)
        except Exception as e:
            print(f"Error starting Flask server: {e}")
            print("Try running with: python flask_server.py")
    else:
        print("❌ Failed to start Morse receiver server!")
        print("Check if port 12345 is already in use")