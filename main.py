import network
import socket
import machine
import time
from machine import Pin, ADC
import gc

# Initialize hardware
#led = Pin(25, Pin.OUT)  # Built-in LED on Pico
#adc = ADC(0)  # ADC0 on GP26
#pump = Pin("LED", Pin.OUT)  # Pump control pin on GP27

# Global variables
led_state = False
adc_value = 0
is_config_mode = False # False = Autonomous | True = Config


# --- Hardware Pin Assignments (update these for your wiring) ---
PLANT_PINS = [
    {"led": "LED", "adc": 0, "pump": 3},   # Plant 1: GP2, ADC0, GP3
    {"led": 4, "adc": 1, "pump": 5},   # Plant 2: GP4, ADC1, GP5
    # {"led": 6, "adc": 2, "pump": 7},   # Plant 3: GP6, ADC2, GP7
    # {"led": 8, "adc": 3, "pump": 9},   # Plant 4: GP8, ADC3, GP9
]
USER_BUTTON = Pin(36, Pin.IN, Pin.PULL_UP) 

# --- Initialize hardware for all plants ---
leds = [Pin(p["led"], Pin.OUT) for p in PLANT_PINS]
adcs = [ADC(p["adc"]) for p in PLANT_PINS]
pumps = [Pin(p["pump"], Pin.OUT) for p in PLANT_PINS]

# --- Global state for all plants ---
led_states = [False] * 2
adc_values = [0] * 2

def create_ap():
    """Create WiFi Access Point"""
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(essid='PicoHotspot', password='12345678')
    
    while not ap.active():
        pass
    
    print('Access Point created')
    print('SSID: PicoHotspot')
    print('Password: 12345678')
    print('IP Address:', ap.ifconfig()[0])
    return ap

def generate_html():
    html = """<!DOCTYPE html>
<html>
<head>
    <title>Plant Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background-color: #f0f0f0; }
        .container { background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 30px; }
        h1 { color: #333; text-align: center; margin-bottom: 30px; }
        .button { background-color: #4CAF50; border: none; color: white; padding: 15px 32px; text-align: center; text-decoration: none; display: inline-block; font-size: 16px; margin: 4px 2px; cursor: pointer; border-radius: 5px; width: 200px; }
        .button:hover { background-color: #45a049; }
        .led-button { background-color: #4CAF50; }
        .led-on { background-color: #ff4444; }
        .pump-button { background-color: #2196F3; }
        .pump-button:hover { background-color: #1976D2; }
        .status { margin: 20px 0; padding: 15px; background-color: #e7f3ff; border-radius: 5px; border-left: 4px solid #2196F3; }
        .adc-value { font-size: 24px; font-weight: bold; color: #333; }
    </style>
</head>
<body>
    <h1>Plant Dashboard</h1>
"""
    for i in range(2):
        html += f"""
    <div class="container">
        <h2>Plant {i+1}</h2>
        <div class="status">
            <strong>LED Status:</strong> {"ON" if led_states[i] else "OFF"}
        </div>
        <div style="text-align: center; margin: 20px 0;">
            <form method="POST" action="/toggle_led_{i}">
                <button type="submit" class="button led-button{' led-on' if led_states[i] else ''}">
                    {"Turn OFF LED" if led_states[i] else "Turn ON LED"}
                </button>
            </form>
        </div>
        <div style="text-align: center; margin: 20px 0;">
            <form method="POST" action="/read_adc_{i}">
                <button type="submit" class="button">
                    Read Soil Moisture Value
                </button>
            </form>
        </div>
        <div style="text-align: center; margin: 20px 0;">
            <form method="POST" action="/activate_pump_{i}">
                <button type="submit" class="button pump-button">
                    Activate Pump
                </button>
            </form>
        </div>
        <div class="status">
            <strong>Latest Soil Moisture Reading:</strong>
            <div class="adc-value">{adc_values[i]}</div>
        </div>
    </div>
"""
    html += """
    <div style="text-align: center; margin-top: 30px; color: #666;">
        <small>Connected to PicoHotspot WiFi</small>
    </div>
</body>
</html>"""
    return html

def handle_request(client_socket):
    global led_states, adc_values
    try:
        request = client_socket.recv(1024).decode()
        if not request:
            return
        lines = request.split('\n')
        first_line = lines[0]

        if first_line.startswith('GET /'):
            response = 'HTTP/1.1 200 OK\r\n'
            response += 'Content-Type: text/html\r\n'
            response += 'Connection: close\r\n\r\n'
            response += generate_html()
        else:
            handled = False
            for i in range(4):
                if first_line.startswith(f'POST /toggle_led_{i}'):
                    led_states[i] = not led_states[i]
                    leds[i].value(led_states[i])
                    handled = True
                elif first_line.startswith(f'POST /read_adc_{i}'):
                    adc_values[i] = adcs[i].read_u16()
                    handled = True
                elif first_line.startswith(f'POST /activate_pump_{i}'):
                    pumps[i].value(True)
                    time.sleep(5)
                    pumps[i].value(False)
                    handled = True
                if handled:
                    response = 'HTTP/1.1 303 See Other\r\n'
                    response += 'Location: /\r\n'
                    response += 'Connection: close\r\n\r\n'
                    break
            if not handled:
                response = 'HTTP/1.1 404 Not Found\r\n'
                response += 'Content-Type: text/html\r\n'
                response += 'Connection: close\r\n\r\n'
                response += '<h1>404 Not Found</h1>'
        client_socket.send(response.encode())
    except Exception as e:
        print(f"Error handling request: {e}")
    finally:
        client_socket.close()

def start_webserver():
    """Start the web server"""
    addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
    server_socket = socket.socket()
    server_socket.bind(addr)
    server_socket.listen(1)
    
    print('Web server started on port 80')
    print('Connect to PicoHotspot WiFi and visit: http://192.168.4.1')
    
    while True:
        try:
            client_socket, addr = server_socket.accept()
            print(f'Client connected from {addr}')
            handle_request(client_socket)
            gc.collect()  # Garbage collection to prevent memory issues
        except Exception as e:
            print(f"Server error: {e}")
            try:
                client_socket.close()
            except:
                pass

def main():

    while not is_config_mode:
        if USER_BUTTON.value() == 0:
            is_config_mode = True
            time.sleep(0.1)
    
    # Initialize all LEDs to OFF
    for l in leds:
        l.value(False)
    
    """Main function"""
    print("Starting Pico Web Server...")
    
    # Create WiFi access point
    ap = create_ap()
    
   
    
    # Start web server
    start_webserver()

if __name__ == '__main__':
    main()
