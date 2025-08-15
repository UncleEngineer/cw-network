# gui_server.py - Tkinter GUI Server for CW Paddle Morse Code
import socket
import threading
import datetime
import time
import tkinter as tk
from tkinter import ttk
import pygame
import numpy as np

class GUIMorseServer:
    def __init__(self, root):
        self.root = root
        self.root.title("CW Paddle Morse Code Server - GUI")
        self.root.geometry("1000x700")
        self.root.configure(bg='#2c3e50')
        
        # Server settings
        self.host = '0.0.0.0'
        self.port = 12345
        self.server_socket = None
        self.running = False
        
        # Text display settings
        self.current_line = ""
        self.line_length = 100  # 100 characters per line
        self.last_char_time = time.time()
        
        # Smart spacing based on Morse timing (adjusted for 15 WPM default)
        self.letter_gap_time = 0.24   # 3 dit units at 15 WPM = 0.24s (between letters in a word)
        self.word_gap_time = 1.5      # Longer pause indicates word boundary  
        self.newline_timeout = 8.0    # seconds before adding newline
        
        # Multiple device tracking
        self.connected_devices = {}  # Track connected devices
        self.device_colors = ['#e74c3c', '#2ecc71', '#3498db', '#f39c12', '#9b59b6', '#1abc9c']  # Red first, then green
        self.next_color_index = 0
        
        # Character tracking for mixed colors
        self.current_line_chars = []  # List of (char, color) tuples
        
        # Timing-based spacing
        self.auto_space_added = False  # Track if we already added auto-space
        
        # Audio setup
        self.setup_audio()
        
        # Morse timing (15 WPM default to match Pico)
        self.wpm = 15
        self.update_timing_from_wpm()
        
        # Setup GUI
        self.setup_gui()
        
        # Start timeout checker
        self.check_timeout_timer()
        
    def setup_audio(self):
        """Setup audio system for morse code tones"""
        try:
            pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
            self.tone_frequency = 600  # Hz (standard CW tone)
            sample_rate = 22050
            
            # Generate tone sounds for dit and dah
            self.dit_sound = self.generate_tone(self.tone_frequency, 0.08, sample_rate)
            self.dah_sound = self.generate_tone(self.tone_frequency, 0.24, sample_rate)
            
            self.audio_enabled = True
            
        except Exception as e:
            print(f"Audio initialization failed: {e}")
            self.audio_enabled = False
    
    def generate_tone(self, frequency, duration, sample_rate):
        """Generate a sine wave tone"""
        frames = int(duration * sample_rate)
        arr = np.zeros((frames, 2))
        for i in range(frames):
            wave = np.sin(2 * np.pi * frequency * i / sample_rate)
            arr[i][0] = wave * 0.3  # Left channel
            arr[i][1] = wave * 0.3  # Right channel
        
        arr = (arr * 32767).astype(np.int16)
        return pygame.sndarray.make_sound(arr)
    
    def update_timing_from_wpm(self):
        """Calculate timing values based on WPM setting"""
        self.dot_duration = 60.0 / (self.wpm * 50)
        self.dash_duration = self.dot_duration * 3
        
    def play_morse_audio(self, morse_code):
        """Play audio for received morse code"""
        if not self.audio_enabled:
            return
            
        def play_sequence():
            try:
                for symbol in morse_code:
                    if symbol == '.':
                        self.dit_sound.play()
                        time.sleep(self.dot_duration + 0.05)
                    elif symbol == '-':
                        self.dah_sound.play()
                        time.sleep(self.dash_duration + 0.05)
                    elif symbol == ' ':
                        time.sleep(self.dot_duration * 2)
                    elif symbol == '/':
                        time.sleep(self.dot_duration * 4)
            except Exception as e:
                print(f"Audio playback error: {e}")
        
        audio_thread = threading.Thread(target=play_sequence)
        audio_thread.daemon = True
        audio_thread.start()
    
    def setup_gui(self):
        """Setup the GUI interface"""
        # Title
        title_frame = tk.Frame(self.root, bg='#2c3e50')
        title_frame.pack(fill='x', padx=10, pady=10)
        
        title_label = tk.Label(title_frame, text="CW PADDLE MORSE CODE SERVER", 
                              font=('Courier', 20, 'bold'), fg='#ecf0f1', bg='#2c3e50')
        title_label.pack()
        
        # Status frame
        status_frame = tk.Frame(self.root, bg='#34495e', relief='raised', bd=2)
        status_frame.pack(fill='x', padx=10, pady=5)
        
        # Server status
        self.status_label = tk.Label(status_frame, text="Server: Stopped", 
                                    font=('Courier', 12, 'bold'), fg='#e74c3c', bg='#34495e')
        self.status_label.pack(side='left', padx=10, pady=5)
        
        # Connection info and device counter
        connection_info_frame = tk.Frame(status_frame, bg='#34495e')
        connection_info_frame.pack(side='left', padx=20, pady=5)
        
        self.connection_label = tk.Label(connection_info_frame, text="", 
                                        font=('Courier', 10), fg='#95a5a6', bg='#34495e')
        self.connection_label.pack()
        
        self.device_count_label = tk.Label(connection_info_frame, text="Devices: 0", 
                                          font=('Courier', 10, 'bold'), fg='#3498db', bg='#34495e')
        self.device_count_label.pack()
        
        # Audio status
        audio_status = "Audio: ✓ Enabled" if self.audio_enabled else "Audio: ✗ Disabled"
        self.audio_label = tk.Label(status_frame, text=audio_status, 
                                   font=('Courier', 10), fg='#3498db', bg='#34495e')
        self.audio_label.pack(side='right', padx=10, pady=5)
        
        # Control frame
        control_frame = tk.Frame(self.root, bg='#2c3e50')
        control_frame.pack(fill='x', padx=10, pady=5)
        
        # Start/Stop button
        self.start_button = tk.Button(control_frame, text="Start Server", 
                                     command=self.toggle_server,
                                     font=('Courier', 12, 'bold'), 
                                     bg='#27ae60', fg='white', padx=20)
        self.start_button.pack(side='left', padx=5)
        
        # Clear button
        self.clear_button = tk.Button(control_frame, text="Clear Text", 
                                     command=self.clear_text,
                                     font=('Courier', 12, 'bold'), 
                                     bg='#e74c3c', fg='white', padx=20)
        self.clear_button.pack(side='left', padx=5)
        
        # Character counter
        self.char_counter = tk.Label(control_frame, text="Characters: 0 | Line: 0/100", 
                                    font=('Courier', 10), fg='#95a5a6', bg='#2c3e50')
        self.char_counter.pack(side='right', padx=10)
        
        # Text display frame
        text_frame = tk.Frame(self.root, bg='#34495e', relief='raised', bd=2)
        text_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Text display label
        display_label = tk.Label(text_frame, text="RECEIVED TEXT (100 characters per line):", 
                                font=('Courier', 12, 'bold'), fg='#ecf0f1', bg='#34495e')
        display_label.pack(anchor='w', padx=10, pady=(10,5))
        
        # Create scrollable text display using Canvas and Frame
        self.canvas = tk.Canvas(text_frame, bg='#2c3e50', highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(text_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg='#2c3e50')
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        self.scrollbar.pack(side="right", fill="y", pady=10)
        
        # Text lines storage
        self.text_lines = []
        self.current_line_label = None
        self.total_chars = 0
        
        # Add first line
        self.add_new_line()
        
        # Reset timing flags
        self.last_char_time = time.time()
        self.auto_space_added = False
        
        # Info frame
        info_frame = tk.Frame(self.root, bg='#34495e', relief='raised', bd=2)
        info_frame.pack(fill='x', padx=10, pady=5)
        
        info_text = ("Instructions: Start server, then connect multiple Pico W or Arduino Nano ESP32 devices. " +
                    "Each device gets a unique color when multiple are connected. " +
                    "Text appears in real-time, 100 chars per line. AUTO-SPACES added after 1.5s pause (prevents splitting words like CQ), NEWLINES after 8s pause.")
        
        info_label = tk.Label(info_frame, text=info_text, 
                             font=('Courier', 9), fg='#95a5a6', bg='#34495e',
                             wraplength=950, justify='left')
        info_label.pack(padx=10, pady=8)
    
    def add_new_line(self):
        """Add a new line to the text display"""
        line_num = len(self.text_lines) + 1
        
        # Create frame for the line to hold multiple colored labels
        line_frame = tk.Frame(self.scrollable_frame, bg='#2c3e50')
        line_frame.pack(fill='x', padx=5, pady=1)
        
        # Line number label (always neutral color)
        line_num_label = tk.Label(line_frame, 
                                 text=f"{line_num:3d}: ", 
                                 font=('Courier', 12), 
                                 fg='#95a5a6', bg='#2c3e50',
                                 anchor='w')
        line_num_label.pack(side='left')
        
        # Text container frame for colored characters
        text_container = tk.Frame(line_frame, bg='#2c3e50')
        text_container.pack(side='left', fill='x', expand=True)
        
        self.text_lines.append({
            'frame': line_frame,
            'container': text_container,
            'chars': []
        })
        self.current_line = ""
        self.current_line_chars = []
        
        # Auto-scroll to bottom
        self.root.after(10, lambda: self.canvas.yview_moveto(1.0))
    
    def update_current_line(self, device_color="#2ecc71"):
        """Update the current line display by adding character with its color"""
        if len(self.text_lines) > 0:
            current_line_info = self.text_lines[-1]
            
            # Get the last character and its color
            if self.current_line_chars:
                last_char, char_color = self.current_line_chars[-1]
                
                # Create a label for this character
                char_label = tk.Label(current_line_info['container'],
                                     text=last_char,
                                     font=('Courier', 12),
                                     fg=char_color,
                                     bg='#2c3e50')
                char_label.pack(side='left')
                
                # Store the label reference
                current_line_info['chars'].append(char_label)
            
            # Update character counter
            line_chars = len(self.current_line)
            device_count = len(self.connected_devices)
            self.char_counter.config(text=f"Characters: {self.total_chars} | Line: {line_chars}/100 | Devices: {device_count}")
    
    def add_character(self, char, client_ip="", device_color="#e74c3c"):
        """Add a character to the current line with device color coding"""
        # Reset auto-space flag when new character arrives
        self.auto_space_added = False
        
        # Skip explicit space characters from devices
        if char == "[SPACE]":
            return
        
        # Check if we need a new line
        if len(self.current_line) >= self.line_length:
            self.add_new_line()
        
        # Add character to current line with its color
        self.current_line += char
        self.current_line_chars.append((char, device_color))
        self.total_chars += 1
        self.last_char_time = time.time()
        
        # Update display
        self.update_current_line(device_color)
    
    def add_space_and_newline(self):
        """Add space and newline when timeout occurs"""
        if self.current_line and not self.current_line.endswith(" "):
            # Add space if line doesn't end with space (use neutral color)
            if len(self.current_line) < self.line_length:
                self.current_line += " "
                self.current_line_chars.append((" ", "#95a5a6"))  # Neutral color for auto-spaces
                self.total_chars += 1
                self.update_current_line("#95a5a6")
        
        # Start new line if current line has content
        if self.current_line.strip():
            self.add_new_line()
    
    def check_timeout_timer(self):
        """Check for timeout and add space/newline based on Morse timing"""
        current_time = time.time()
        time_since_last_char = current_time - self.last_char_time
        
        # Only add auto-spacing if we have content and haven't already added space
        if self.current_line and not self.auto_space_added:
            # Add space only after a pause longer than normal letter spacing
            # This prevents spaces within words like "CQ" but adds them between words
            if time_since_last_char > self.word_gap_time:
                self.add_auto_space()
                self.auto_space_added = True
            
            # Add newline after much longer pause
            elif time_since_last_char > self.newline_timeout:
                self.add_auto_newline()
                self.auto_space_added = True  # Prevent adding space after newline
        
        # Schedule next check
        self.root.after(100, self.check_timeout_timer)  # Check every 0.1 seconds for faster response
    
    def add_auto_space(self):
        """Add an automatic space based on timing"""
        if (self.current_line and 
            not self.current_line.endswith(" ") and 
            len(self.current_line) < self.line_length):
            
            # Add space with neutral color to indicate it's automatic
            self.current_line += " "
            self.current_line_chars.append((" ", "#95a5a6"))  # Gray for auto-space
            self.total_chars += 1
            self.update_current_line("#95a5a6")
            
            print(f"[AUTO] Added space after {self.word_gap_time}s pause")
    
    def add_auto_newline(self):
        """Add an automatic newline based on timing"""
        if self.current_line.strip():  # Only if line has content
            print(f"[AUTO] Added newline after {self.newline_timeout}s pause")
            self.add_new_line()
    
    def clear_text(self):
        """Clear all text"""
        # Clear all line frames
        for line_info in self.text_lines:
            if isinstance(line_info, dict):
                line_info['frame'].destroy()
            else:
                # Handle old format for compatibility
                line_info.destroy()
        
        # Reset variables
        self.text_lines = []
        self.current_line = ""
        self.current_line_chars = []
        self.total_chars = 0
        self.auto_space_added = False
        
        # Add first line
        self.add_new_line()
    
    def toggle_server(self):
        """Start or stop the server"""
        if not self.running:
            self.start_server()
        else:
            self.stop_server()
    
    def start_server(self):
        """Start the server"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(10)
            self.running = True
            
            # Update GUI
            self.status_label.config(text="Server: Running", fg='#2ecc71')
            self.start_button.config(text="Stop Server", bg='#e74c3c')
            
            # Get local IP
            local_ip = self.get_local_ip()
            self.connection_label.config(text=f"Listening on {local_ip}:{self.port}")
            
            # Start server thread
            server_thread = threading.Thread(target=self.server_loop)
            server_thread.daemon = True
            server_thread.start()
            
            print(f"GUI Server started on {self.host}:{self.port}")
            
        except Exception as e:
            print(f"Failed to start server: {e}")
            self.status_label.config(text=f"Server: Error - {e}", fg='#e74c3c')
    
    def server_loop(self):
        """Main server loop"""
        while self.running:
            try:
                client_socket, client_address = self.server_socket.accept()
                
                # Handle client in separate thread
                client_thread = threading.Thread(
                    target=self.handle_client, 
                    args=(client_socket, client_address)
                )
                client_thread.daemon = True
                client_thread.start()
                
            except socket.error as e:
                if self.running:
                    print(f"Socket error: {e}")
    
    def handle_client(self, client_socket, client_address):
        """Handle individual client connections"""
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
            
            # Update device count in GUI
            self.root.after(0, self.update_device_count)
            print(f"New device connected: {client_ip}")
        
        # Update last seen time
        self.connected_devices[client_ip]['last_seen'] = time.time()
        
        try:
            data = client_socket.recv(1024).decode('utf-8')
            
            if data:
                self.process_morse_data(data, client_ip)
                
        except Exception as e:
            print(f"Error handling client {client_address}: {e}")
        finally:
            client_socket.close()
    
    def update_device_count(self):
        """Update the device count display"""
        # Clean up old devices (not seen for 30 seconds)
        current_time = time.time()
        devices_to_remove = []
        
        for ip, info in self.connected_devices.items():
            if current_time - info['last_seen'] > 30:
                devices_to_remove.append(ip)
        
        for ip in devices_to_remove:
            del self.connected_devices[ip]
            print(f"Device disconnected: {ip}")
        
        # Update display
        device_count = len(self.connected_devices)
        self.device_count_label.config(text=f"Devices: {device_count}")
        
        # Show device list if multiple devices
        if device_count > 1:
            device_list = ", ".join(self.connected_devices.keys())
            self.connection_label.config(text=f"Connected: {device_list}")
        elif device_count == 1:
            device_ip = list(self.connected_devices.keys())[0]
            self.connection_label.config(text=f"Connected: {device_ip}")
        else:
            local_ip = self.get_local_ip()
            self.connection_label.config(text=f"Listening on {local_ip}:{self.port}")
    
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
                # Skip explicit space characters - we'll handle spacing by timing
                if char == "[SPACE]":
                    return
                
                # Update device character count
                self.connected_devices[client_ip]['char_count'] += 1
                
                # Add character to GUI (must be done in main thread)
                device_color = self.connected_devices[client_ip]['color']
                self.root.after(0, lambda: self.add_character(char, client_ip, device_color))
                
                # Play audio
                self.play_morse_audio(morse)
                
                # Print to console for debugging
                timestamp = datetime.datetime.now().strftime("%H:%M:%S")
                device_count = len(self.connected_devices)
                print(f"[{timestamp}] {client_ip} -> {char} ({morse}) [Devices: {device_count}]")
                
        except Exception as e:
            print(f"Error processing data: {e}")
    
    def stop_server(self):
        """Stop the server"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()
        
        # Update GUI
        self.status_label.config(text="Server: Stopped", fg='#e74c3c')
        self.start_button.config(text="Start Server", bg='#27ae60')
        self.connection_label.config(text="")
        
        print("GUI Server stopped")
    
    def get_local_ip(self):
        """Get the local IP address"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            return local_ip
        except:
            return "127.0.0.1"
    
    def on_closing(self):
        """Handle window closing"""
        if self.running:
            self.stop_server()
        
        if self.audio_enabled:
            try:
                pygame.mixer.quit()
            except:
                pass
        
        self.root.destroy()

def main():
    """Main function"""
    root = tk.Tk()
    app = GUIMorseServer(root)
    
    # Handle window closing
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        app.on_closing()

if __name__ == "__main__":
    main()