import network
import socket
import machine
import time
from machine import Pin, ADC
import gc
from XRPLib.encoded_motor import EncodedMotor

# Initialize hardware
#led = Pin(25, Pin.OUT)  # Built-in LED on Pico
#adc = ADC(0)  # ADC0 on GP26
#pump = Pin("LED", Pin.OUT)  # Pump control pin on GP27

# Global variables
led_state = False
adc_value = 0
is_config_mode = False # False = autonomous | True = Config

# --- Hardware Pin Assignments (update these for your wiring) ---
PLANT_PINS = [
    {"led": "LED", "adc": 0, "pump": 3},   # Plant 1: GP2, ADC0, GP3
    {"led": 4, "adc": 1, "pump": 5},   # Plant 2: GP4, ADC1, GP5
    # {"led": 6, "adc": 2, "pump": 7},   # Plant 3: GP6, ADC2, GP7
    # {"led": 8, "adc": 3, "pump": 9},   # Plant 4: GP8, ADC3, GP9
]
USER_BUTTON  = Pin(36, Pin.IN, Pin.PULL_UP)

# --- Initialize hardware for all plants ---
leds = [Pin(p["led"], Pin.OUT) for p in PLANT_PINS]
adcs = [ADC(p["adc"]) for p in PLANT_PINS]
pumps = [Pin(p["pump"], Pin.OUT) for p in PLANT_PINS]

# --- Global state for all plants ---
led_states = [False] * 4
adc_values = [0] * 4

# motors = {}

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


def autonomous_btn_click():
    

def generate_html():
    html = """<!DOCTYPE html>
    <html lang="en">
    <head>
        <title>Plant Dashboard</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body{gap: 120px; margin-top: 150px ;background-color: lightgray; display: flex; flex-direction: row; justify-content: center; font-family:'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;}
            .plant-box{padding: 20px; background-color: white; border: 3px solid grey; border-radius: 8px; display: flex; flex-direction: column}
            .plant-box header{text-align: center; margin-bottom: 20px; font-size: 20px;}
            .attribute{display: flex; flex-direction: row; align-items: center}
            .attribute p{width: 150px; margin-right: 30px;}
            .attribute input{width: 80px; margin-right: 20px;}
            .text-box{margin: 10px; border: 3px solid grey; border-radius: 5px; padding: 3px;}
            button{padding: 4px; width: 50px;}
            .start-btn{background-color: orange; border-radius: 3px; border-style: none;}
            .apply-btn{background-color: lightgreen; border-radius: 3px; border-style: none;}
        </style>
    </head>
    <body>
        <div class="plant-box">
            <header>Plant 1</header>
            <div class="attribute">
                <p>Soil moisture:</p>
                <input class="text-box" type="text" readonly>
            </div>
            <div class="attribute">
                <p>Pump for:</p>
                <input id="pump1" class="text-box" type="text">
                <button class="start-btn" onclick="runPump(1)">Start</button>
            </div>
            <div class="attribute">
                <p>Moisture threshold:</p>
                <input class="text-box" type="text">
                <button class="apply-btn">Apply</button>
            </div>
            <div class="attribute">
                <p>Water seconds:</p>
                <input class="text-box" type="text">
                <button class="apply-btn">Apply</button>
            </div>
        </div>
        <div class="plant-box">
            <header>Plant 2</header>
            <div class="attribute">
                <p>Soil moisture:</p>
                <input class="text-box" type="text" readonly>
            </div>
            <div class="attribute">
                <p>Pump for:</p>
                <input id="pump2" class="text-box" type="text">
                <button class="start-btn" onclick="runPump(2)">Start</button>
            </div>
            <div class="attribute">
                <p>Moisture threshold:</p>
                <input class="text-box" type="text">
                <button class="apply-btn">Apply</button>
            </div>
            <div class="attribute">
                <p>Water seconds:</p>
                <input class="text-box" type="text">
                <button class="apply-btn">Apply</button>
            </div>
        </div>
        <script>
            async function runPump(i){
                const secs = Number(document.getElementById("pump" + i).value || '0');
                
                if (isNaN(secs)) {
                    alert("Please enter a number.");
                    return;
                }
                if (secs <= 0) {
                    alert("Please enter a number greater than 0.");
                    return;
                }

                try {
                    await fetch('/api/pump/' + i + '/' + secs, { method: 'POST' });
                } catch (e) {
                    console.log("Error sending pump request:", e);
                }
            }
        </script>
    </body>
    </html>"""
    return html

def handle_request(client_socket):
    try:
        req = client_socket.recv(1024).decode()
        if not req:
            return

        first_line = req.split('\n', 1)[0].strip()  # "POST /api/pump/0/2 HTTP/1.1"
        parts = first_line.split()
        if len(parts) < 2:
            return
        method, path = parts[0], parts[1]

        # Serve HTML
        if method == 'GET' and path == '/':
            response = 'HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\n\r\n'
            response += generate_html()
            client_socket.send(response.encode())
            return

        # API: pump
        if method == 'POST' and path.startswith('/api/pump/'):
            try:
                _, _, _, idx_str, sec_str = path.split('/')
                idx = int(idx_str)
                secs = float(sec_str)
                if idx < 1 or idx > 2:
                    raise ValueError('bad motor/pump index')

                motor = EncodedMotor.get_default_encoded_motor(idx)
                motor.set_effort(1.0)
                time.sleep(secs)
                motor.set_effort(0.0)

                client_socket.send(b'HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\nOK')
            except Exception as e:
                print('pump route error:', e)
                client_socket.send(b'HTTP/1.1 400 Bad Request\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\nERR')
            return

        client_socket.send(b'HTTP/1.1 404 Not Found\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\nNot Found')

    except Exception as e:
        print(f"Error handling request: {e}")
    finally:
        try: client_socket.close()
        except: pass

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
    """Main function"""
    print("Starting Pico Web Server...")
    
    while not is_config_mode:
        if USER_BUTTON.value() == 0:
            is_config_mode = True
            time.sleep(0.5)

    # Initialize all LEDs to OFF
    for l in leds:
        l.value(False)
    
    # Create WiFi access point
    ap = create_ap()

    # Start web server
    start_webserver()
    
#     m = EncodedMotor.get_default_encoded_motor(2)
#     m.set_effort(0.8)
#     time.sleep(10)

if __name__ == '__main__':
    main()
