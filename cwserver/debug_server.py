# debug_server.py - Simple Flask server for testing WebSocket connection
from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'test_secret'
socketio = SocketIO(app, cors_allowed_origins="*")

# Simple HTML template for testing
TEST_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>WebSocket Test</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
</head>
<body>
    <h1>WebSocket Connection Test</h1>
    <div id="status">Connecting...</div>
    <div id="messages"></div>
    
    <script>
        const socket = io();
        const statusDiv = document.getElementById('status');
        const messagesDiv = document.getElementById('messages');
        
        function addMessage(msg) {
            messagesDiv.innerHTML += '<div>' + new Date().toLocaleTimeString() + ': ' + msg + '</div>';
        }
        
        socket.on('connect', function() {
            statusDiv.textContent = 'Connected!';
            statusDiv.style.color = 'green';
            addMessage('Connected to server');
        });
        
        socket.on('disconnect', function() {
            statusDiv.textContent = 'Disconnected!';
            statusDiv.style.color = 'red';
            addMessage('Disconnected from server');
        });
        
        socket.on('test_message', function(data) {
            addMessage('Received: ' + data.message);
        });
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(TEST_TEMPLATE)

@socketio.on('connect')
def handle_connect():
    print('Client connected')
    emit('test_message', {'message': 'Hello from server!'})

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

if __name__ == '__main__':
    print("Starting simple WebSocket test server...")
    print("Open browser to: http://localhost:5000")
    print("If you see 'Connected!' then WebSocket is working")
    print("Press Ctrl+C to stop")
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)