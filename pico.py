# code.py - CircuitPython for Raspberry Pi Pico W
# CW Paddle Morse Code Sender to PC Server

import wifi
import socketpool
import time
import board
import digitalio

# WiFi Configuration
WIFI_SSID = "HD_2.4G"
WIFI_PASSWORD = "11115555"
# code.py - CircuitPython for Raspberry Pi Pico W
# CW Paddle Morse Code Sender to PC Server

# Server Configuration
SERVER_IP = "192.168.1.35"  # Replace with your PC's IP address
SERVER_PORT = 12345

# Pin Configuration
DIT_PIN = board.GP15    # Dit paddle (dot) 
DAH_PIN = board.GP10    # Dah paddle (dash) 
LED_PIN = board.LED     # Onboard LED (correct for Pico W)

# Morse Code Dictionary (reverse lookup)
MORSE_TO_CHAR = {
    '.-': 'A', '-...': 'B', '-.-.': 'C', '-..': 'D', '.': 'E', '..-.': 'F',
    '--.': 'G', '....': 'H', '..': 'I', '.---': 'J', '-.-': 'K', '.-..': 'L',
    '--': 'M', '-.': 'N', '---': 'O', '.--.': 'P', '--.-': 'Q', '.-.': 'R',
    '...': 'S', '-': 'T', '..-': 'U', '...-': 'V', '.--': 'W', '-..-': 'X',
    '-.--': 'Y', '--..': 'Z',
    '-----': '0', '.----': '1', '..---': '2', '...--': '3', '....-': '4',
    '.....': '5', '-....': '6', '--...': '7', '---..': '8', '----.': '9'
}

# CW Speed Configuration
WPM = 15                # Words per minute (adjust as needed: 5-40 typical range)

# Timing constants (in seconds) - calculated from WPM
# Standard: PARIS = 50 dit units, so dit_time = 1.2 / WPM
DIT_TIME = 1.2 / WPM    # Base timing unit
DAH_TIME = DIT_TIME * 3 # Dash is 3 times dit
ELEMENT_GAP = DIT_TIME  # Gap between dits and dahs
LETTER_GAP = DIT_TIME * 3  # Gap between letters
WORD_GAP = DIT_TIME * 7    # Gap between words

# Paddle timing (from your simulator)
DEBOUNCE_TIME = 0.005   # 5ms debounce (faster than before)
LOOP_DELAY = 0.001      # 1ms loop delay for responsiveness

class MorsePaddle:
    def __init__(self):
        # Setup paddle pins with pull-up resistors
        self.dit_paddle = digitalio.DigitalInOut(DIT_PIN)
        self.dit_paddle.direction = digitalio.Direction.INPUT
        self.dit_paddle.pull = digitalio.Pull.UP
        
        self.dah_paddle = digitalio.DigitalInOut(DAH_PIN)
        self.dah_paddle.direction = digitalio.Direction.INPUT
        self.dah_paddle.pull = digitalio.Pull.UP
        
        # Setup LED
        self.led = digitalio.DigitalInOut(LED_PIN)
        self.led.direction = digitalio.Direction.OUTPUT
        
        # State variables
        self.current_morse = ""
        self.last_activity = time.monotonic()
        self.socket_pool = None
        self.connected = False
        
        # Paddle state tracking (from your simulator)
        self.dit_pressed = False
        self.dah_pressed = False
        self.last_dit_state = True
        self.last_dah_state = True
        self.last_dit_time = 0
        self.last_dah_time = 0
        
    def connect_to_wifi(self):
        """Connect to WiFi network"""
        print(f"Connecting to WiFi: {WIFI_SSID}")
        try:
            wifi.radio.connect(WIFI_SSID, WIFI_PASSWORD)
            print(f"Connected to WiFi!")
            print(f"IP Address: {wifi.radio.ipv4_address}")
            self.socket_pool = socketpool.SocketPool(wifi.radio)
            return True
        except Exception as e:
            print(f"WiFi connection failed: {e}")
            return False
    
    def send_character(self, char, morse_code):
        """Send a single character and its morse code to server"""
        try:
            # Create socket
            sock = self.socket_pool.socket(self.socket_pool.AF_INET, self.socket_pool.SOCK_STREAM)
            sock.settimeout(2.0)  # 2 second timeout
            
            # Connect to server
            sock.connect((SERVER_IP, SERVER_PORT))
            
            # Prepare message
            message = f"CHAR: {char}\nMORSE: {morse_code}\nTIME: {time.monotonic()}\n"
            
            # Send the message
            sock.send(message.encode('utf-8'))
            sock.close()
            
            print(f"Sent: '{char}' ({morse_code})")
            
            # Flash LED to confirm transmission
            self.led.value = True
            time.sleep(0.05)
            self.led.value = False
            
        except Exception as e:
            print(f"Error sending character: {e}")
            # Error indication - 3 quick flashes
            for _ in range(3):
                self.led.value = True
                time.sleep(0.05)
                self.led.value = False
                time.sleep(0.05)
    
    def send_space(self):
        """Send a space character to server"""
        try:
            sock = self.socket_pool.socket(self.socket_pool.AF_INET, self.socket_pool.SOCK_STREAM)
            sock.settimeout(2.0)
            sock.connect((SERVER_IP, SERVER_PORT))
            
            message = f"CHAR: [SPACE]\nMORSE: /\nTIME: {time.monotonic()}\n"
            sock.send(message.encode('utf-8'))
            sock.close()
            
            print("Sent: [SPACE]")
            
        except Exception as e:
            print(f"Error sending space: {e}")
    
    def play_element(self, duration):
        """Play a morse code element (dit or dah) with LED"""
        self.led.value = True
        time.sleep(duration)
        self.led.value = False
        time.sleep(ELEMENT_GAP)
    
    def read_paddle_input(self):
        """Read paddle input with proper debouncing (from your simulator)"""
        current_time = time.monotonic()
        element_detected = None
        
        # === DIT PADDLE HANDLING ===
        current_dit_state = self.dit_paddle.value
        if (current_dit_state != self.last_dit_state and 
            current_time - self.last_dit_time > DEBOUNCE_TIME):
            
            if not current_dit_state:  # Pressed (LOW)
                if not self.dit_pressed:
                    self.dit_pressed = True
                    element_detected = 'dit_start'
            else:  # Released (HIGH)
                if self.dit_pressed:
                    self.dit_pressed = False
                    element_detected = 'dit_end'
            
            self.last_dit_state = current_dit_state
            self.last_dit_time = current_time
        
        # === DAH PADDLE HANDLING ===
        current_dah_state = self.dah_paddle.value
        if (current_dah_state != self.last_dah_state and 
            current_time - self.last_dah_time > DEBOUNCE_TIME):
            
            if not current_dah_state:  # Pressed (LOW)
                if not self.dah_pressed:
                    self.dah_pressed = True
                    element_detected = 'dah_start'
            else:  # Released (HIGH)
                if self.dah_pressed:
                    self.dah_pressed = False
                    element_detected = 'dah_end'
            
            self.last_dah_state = current_dah_state
            self.last_dah_time = current_time
        
        # Update LED to show paddle state
        self.led.value = self.dit_pressed or self.dah_pressed
        
        return element_detected
    
    def process_morse_input(self):
        """Process morse code input from paddle"""
        current_time = time.monotonic()
        
        # Read current paddle state with debouncing
        paddle_event = self.read_paddle_input()
        
        if paddle_event:
            # Update last activity time
            self.last_activity = current_time
            
            if paddle_event == 'dit_start':
                print("Dit pressed")
            elif paddle_event == 'dit_end':
                self.current_morse += '.'
                print(f"Dit complete - Current: {self.current_morse}")
                
            elif paddle_event == 'dah_start':
                print("Dah pressed")
            elif paddle_event == 'dah_end':
                self.current_morse += '-'
                print(f"Dah complete - Current: {self.current_morse}")
        
        # Check for letter completion (no activity for LETTER_GAP time)
        elif self.current_morse and (current_time - self.last_activity > LETTER_GAP):
            # Try to decode the morse code
            if self.current_morse in MORSE_TO_CHAR:
                char = MORSE_TO_CHAR[self.current_morse]
                self.send_character(char, self.current_morse)
            else:
                print(f"Unknown morse code: {self.current_morse}")
                # Send as unrecognized
                self.send_character('?', self.current_morse)
            
            # Reset for next character
            self.current_morse = ""
        
        # Check for word completion (no activity for WORD_GAP time)
        elif not self.current_morse and (current_time - self.last_activity > WORD_GAP):
            # Send space to indicate word break
            self.send_space()
            self.last_activity = current_time  # Reset timer
    
    def status_blink(self):
        """Blink LED to show system is running"""
        self.led.value = True
        time.sleep(0.1)
        self.led.value = False
    
    def run(self):
        """Main program loop"""
        print("CW Paddle Morse Code Sender")
        print("===========================")
        print("DIT paddle: GP15")
        print("DAH paddle: GP10") 
        print("LED: Onboard LED")
        print(f"Speed: {WPM} WPM")
        print(f"Dit time: {DIT_TIME:.3f}s")
        print()
        
        # Connect to WiFi
        if not self.connect_to_wifi():
            print("Cannot proceed without WiFi connection")
            while True:
                # Error blink pattern
                for _ in range(5):
                    self.led.value = True
                    time.sleep(0.1)
                    self.led.value = False
                    time.sleep(0.1)
                time.sleep(2)
        
        print(f"Connected to server at {SERVER_IP}:{SERVER_PORT}")
        print("Ready for CW input!")
        print("- Short press Dit paddle for dots (.)")
        print("- Short press Dah paddle for dashes (-)")
        print("- Pause between letters to send character")
        print("- Longer pause between words to send space")
        print()
        
        # Status indication - 3 long blinks
        for _ in range(3):
            self.led.value = True
            time.sleep(0.3)
            self.led.value = False
            time.sleep(0.3)
        
        last_status_blink = time.monotonic()
        
        # Main loop
        while True:
            try:
                # Process paddle input
                self.process_morse_input()
                
                # Status blink every 5 seconds when idle
                current_time = time.monotonic()
                if (current_time - last_status_blink > 5.0 and 
                    current_time - self.last_activity > 2.0):
                    self.status_blink()
                    last_status_blink = current_time
                
                # Small delay for responsiveness (from your simulator)
                time.sleep(LOOP_DELAY)
                
            except KeyboardInterrupt:
                print("\nProgram interrupted")
                break
            except Exception as e:
                print(f"Error in main loop: {e}")
                time.sleep(1)

def main():
    """Initialize and run the morse paddle system"""
    paddle = MorsePaddle()
    paddle.run()

if __name__ == "__main__":
    main()
