# MicroPython / uasyncio version (no _thread)
import network
import uasyncio as asyncio
import socket
import time  # fine to keep, but we won't call time.sleep()
from machine import Pin, ADC
import gc
from XRPLib.encoded_motor import EncodedMotor
from XRPLib.board import Board
import ncsv

# -------------------------------
# Global configuration & hardware
# -------------------------------

# False = autonomous | True = Config
is_config_mode = False

# Two plants by default
moisture_thresholds = [1000, 1000]      # per-plant soil moisture thresholds
auto_water_seconds = [3.0, 3.0]         # per-plant pump runtime when dry

_server_obj = None  # asyncio server object (so we can close it cleanly)

# --- Hardware Pin Assignments (update these for your wiring) ---
PLANT_PINS = [
    {"led": "LED", "adc": 0, "pump": 3},   # Plant 1: LED, ADC0, GP3
    {"led": 4, "adc": 1, "pump": 5},       # Plant 2: GP4, ADC1, GP5
    # {"led": 6, "adc": 2, "pump": 7},     # Plant 3 example
    # {"led": 8, "adc": 3, "pump": 9},     # Plant 4 example
]

# NOTE: These pins (36, 44) are board-specific; keep as-is per your original code.
USER_BUTTON  = Pin(36, Pin.IN, Pin.PULL_UP)
SOIL_ADCs = [ADC(Pin(44)), ADC(Pin(45)) ]       # create ADC objects acting on the soil sensor pins

# --- Initialize hardware for all plants ---
leds  = [Pin(p["led"],  Pin.OUT) for p in PLANT_PINS]
adcs  = [ADC(p["adc"]) for p in PLANT_PINS]
pumps = [Pin(p["pump"], Pin.OUT) for p in PLANT_PINS]

# --- Global state for all plants ---
led_states = [False] * len(PLANT_PINS)
adc_values = [0]     * len(PLANT_PINS)

# A simple per-plant lock so pump actions don't overlap
pump_locks = [asyncio.Lock() for _ in PLANT_PINS]


board = Board.get_default_board()

def _send_json(sock, obj, code=200):
    import json
    body = json.dumps(obj).encode()
    hdr = (
        f"HTTP/1.1 {code} OK\r\n"
        "Content-Type: application/json\r\n"
        "Cache-Control: no-store\r\n"
        "Connection: close\r\n\r\n"
    ).encode()
    sock.send(hdr + body)  
    
# ---------------
# WiFi / AP utils
# ---------------
def create_ap():
    """Create WiFi Access Point (blocking until active)"""
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


# --------------------
# HTTP / HTML frontend
# --------------------
def generate_html():
    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
body{margin-top:150px;background-color:lightgray;display:flex;flex-direction:column;justify-content:center;font-family:'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;}
.plants-area{display:flex;flex-direction:row;gap:120px;justify-content:center;}
.plant-box{padding:20px;background-color:white;border:3px solid grey;border-radius:8px;display:flex;flex-direction:column}
.plant-box header{text-align:center;margin-bottom:20px;font-size:20px;}
.attribute{display:flex;flex-direction:row;align-items:center}
.attribute p{width:150px;margin-right:30px;}
.attribute input{width:80px;margin-right:20px;}
.text-box{margin:10px;border:3px solid grey;border-radius:5px;padding:3px;}
button{padding:4px;width:50px;}
button:active{translate:1px 1px}
.start-btn{background-color:orange;border-radius:3px;border-style:none;}
.apply-btn{background-color:lightgreen;border-radius:3px;border-style:none;}
.auto-button{background-color:mediumblue;border-radius:3px;color:white;width:120px;height:80px;}
.auto-button-container{display:flex;justify-content:center;margin-top:20px;}
</style>
</head>
<body>
<div class="plants-area">
  <div class="plant-box">
    <header>Plant 1</header>
    <div class="attribute">
      <p>Soil moisture:</p>
      <input id="soil-field0" class="text-box" type="text" readonly>
    </div>
    <div class="attribute">
      <p>Pump for:</p>
      <input id="pump0" class="text-box" type="text">
      <button class="start-btn" onclick="runPump(0)">Start</button>
    </div>
    <div class="attribute">
      <p>Moisture threshold:</p>
      <input id="threshold0" class="text-box" type="text">
      <button class="apply-btn" onclick="applyThreshold(0)">Apply</button>
    </div>
    <div class="attribute">
      <p>Water seconds:</p>
      <input id="water0" class="text-box" type="text">
      <button class="apply-btn" onclick="applyWater(0)">Apply</button>
    </div>
  </div>
  <div class="plant-box">
    <header>Plant 2</header>
    <div class="attribute">
      <p>Soil moisture:</p>
      <input id="soil-field1" class="text-box" type="text" readonly>
    </div>
    <div class="attribute">
      <p>Pump for:</p>
      <input id="pump1" class="text-box" type="text">
      <button class="start-btn" onclick="runPump(1)">Start</button>
    </div>
    <div class="attribute">
      <p>Moisture threshold:</p>
      <input id="threshold1" class="text-box" type="text">
      <button class="apply-btn" onclick="applyThreshold(1)">Apply</button>
    </div>
    <div class="attribute">
      <p>Water seconds:</p>
      <input id="water1" class="text-box" type="text">
      <button class="apply-btn" onclick="applyWater(1)">Apply</button>
    </div>
  </div>
</div>
<div class="auto-button-container">
  <button class="auto-button" onclick="toggleAutonomous()">Autonomous Mode</button>
</div>
<script>
async function runPump(i){
  const secs = Number(document.getElementById("pump" + i).value || '0');
  if (isNaN(secs)){ alert("Please enter a number."); return; }
  if (secs <= 0){ alert("Please enter a number greater than 0."); return; }
  try { await fetch('/api/pump/' + i + '/' + secs, { method: 'POST' }); }
  catch(e){ console.log("Error sending pump request:", e); }
}
async function applyThreshold(i){
  const v = Number(document.getElementById("threshold" + i).value);
  if (isNaN(v)){ alert("Enter a number"); return; }
  try { await fetch('/api/set_threshold/' + i + '/' + v, { method: 'POST' }); }
  catch(e){ console.log("error setting moisture threshold:", e); }
}
async function applyWater(i){
  const v = Number(document.getElementById("water" + i).value);
  if (isNaN(v) || v < 0){ alert("Enter a non-negative number"); return; }
  try { await fetch('/api/set_water/' + i + '/' + v, { method: 'POST' }); }
  catch(e){ console.log("error setting water duration:", e); }
}
 async function updateSoil(i){
                try{
                    const res = await fetch('/api/update_soil/' + i, { method: 'GET' });
                    const json_res = await res.json();
                    document.getElementById("soil-field" + i).value = json_res.raw;
                } catch (e){
                    console.log("error updating soil moisture: ", e)
                }
            }

            setInterval(() => updateSoil(0), 1000);
            setInterval(() => updateSoil(1), 1000);
            updateSoil(0);
            updateSoil(1);
        
async function toggleAutonomous(){
  try { await fetch('/api/toggle_mode', { method: 'POST' }); }
  catch(e){ console.log("error toggling mode:", e); }
}
</script>
</body>
</html>"""
    return html


async def handle_client(reader, writer):
    """Async HTTP 1.0/1.1 handler (very small, just enough for this UI)."""
    try:
        req = await reader.read(1024)
        if not req:
            return
        try:
            req_s = req.decode()
        except:
            req_s = str(req)

        first_line = req_s.split('\n', 1)[0].strip()  # "POST /api/pump/0/2 HTTP/1.1"
        parts = first_line.split()
        if len(parts) < 2:
            return
        method, path = parts[0], parts[1]

        # Serve HTML
        if method == 'GET' and path == '/':
            body = generate_html()
            resp = (
                'HTTP/1.1 200 OK\r\n'
                'Content-Type: text/html\r\n'
                'Connection: close\r\n\r\n' + body
            )
            writer.write(resp.encode())
            await writer.drain()
            return

        # Toggle mode (UI button) — flips to autonomous and button task will also work
        if method == 'POST' and path == '/api/toggle_mode':
            global is_config_mode
            is_config_mode = not is_config_mode
            writer.write(b'HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\nOK')
            await writer.drain()
            return
        
        #API: get soil moisture
        if method == 'GET' and path.startswith('/api/update_soil/'):
            try:
                _, _, _, idx_str = path.split('/')
                idx = int(idx_str)
                if idx < 0 or idx >= len(SOIL_ADCs): raise ValueError('bad plant index')
                raw_val = SOIL_ADCs[idx].read_u16()
                import json
                body = json.dumps({"raw": raw_val}).encode()
                hdr = (
                    "HTTP/1.1 200 OK\r\n"
                    "Content-Type: application/json\r\n"
                    "Cache-Control: no-store\r\n"
                    "Connection: close\r\n\r\n"
                ).encode()
                writer.write(hdr + body)
            except Exception as e:
                print('error reading soil sensor', e)
                writer.write(b'HTTP/1.1 400 Bad Request\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\nERR')
            await writer.drain()
            return

        # API: pump (indexes 0..N-1)
        if method == 'POST' and path.startswith('/api/pump/'):
            try:
                _, _, _, idx_str, sec_str = path.split('/')
                idx = int(idx_str)
                secs = float(sec_str)
                if idx < 0 or idx >= len(PLANT_PINS):
                    raise ValueError('bad plant index')
                if secs <= 0:
                    raise ValueError('seconds must be > 0')

                async with pump_locks[idx]:
                    motor = EncodedMotor.get_default_encoded_motor(idx + 1)
                    motor.set_effort(1.0)
                    await asyncio.sleep(secs)
                    motor.set_effort(0.0)

                writer.write(b'HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\nOK')
            except Exception as e:
                print('pump route error:', e)
                writer.write(b'HTTP/1.1 400 Bad Request\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\nERR')
            await writer.drain()
            return

        # API: set per-plant moisture threshold
        if method == 'POST' and path.startswith('/api/set_threshold/'):
            try:
                _, _, _, idx_str, val_str = path.split('/')
                idx = int(idx_str)
                threshold_val = int(val_str)
                if idx < 0 or idx >= len(moisture_thresholds):
                    raise ValueError('bad plant index') 
                moisture_thresholds[idx] = threshold_val
                writer.write(b'HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\nOK')
            except Exception as e:
                print('set_threshold error:', e)
                writer.write(b'HTTP/1.1 400 Bad Request\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\nERR')
            await writer.drain()
            return

        # API: set per-plant autonomous watering duration (seconds)
        if method == 'POST' and path.startswith('/api/set_water/'):
            try:
                _, _, _, idx_str, val_str = path.split('/')
                idx = int(idx_str)
                water_secs = float(val_str)
                if idx < 0 or idx >= len(auto_water_seconds):
                    raise ValueError('bad plant index')
                if water_secs < 0:
                    raise ValueError('Please enter non-negative seconds')  # FIX: variable name
                auto_water_seconds[idx] = water_secs
                writer.write(b'HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\nOK')
            except Exception as e:
                print('set_water error:', e)
                writer.write(b'HTTP/1.1 400 Bad Request\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\nERR')
            await writer.drain()
            return

        # Not found
        writer.write(b'HTTP/1.1 404 Not Found\r\nContent-Type: text/plain\r\nConnection: close\r\n\r\nNot Found')
        await writer.drain()

    except Exception as e:
        print("Error handling request:", e)
    finally:
        try:
            await writer.drain()
        except:
            pass
        try:
            # Some MicroPython builds may not have wait_closed(); ignore if so
            await writer.wait_closed()
        except:
            try:
                writer.close()
            except:
                pass


# -----------------------
# Mode handlers (asyncio)
# -----------------------
async def start_webserver():
    """Start async web server on port 80 (returns server object)."""
    print('Web server starting on port 80...')
    server = await asyncio.start_server(handle_client, '0.0.0.0', 80, backlog=2)
    print('Web server started. Visit: http://192.168.4.1')
    return server


async def stop_webserver(server):
    """Stop the async web server cleanly."""
    try:
        print("Stopping web server...")
        server.close()
        await server.wait_closed()
        print("Web server stopped.")
    except Exception as e:
        print("Error stopping server:", e)


async def config_mode_task():
    """Run configuration mode: bring up AP and serve the UI until mode flips false."""
    global _server_obj

    # Ensure all pumps off when entering config
    for i in range(len(PLANT_PINS)):
        try:
            motor = EncodedMotor.get_default_encoded_motor(i + 1)
            motor.set_effort(0.0)
        except Exception as e:
            print("Motor init off error:", e)

    ap = create_ap()

    # Start server
    _server_obj = await start_webserver()

    try:
        # Poll until mode flips off (button task or UI endpoint will flip)
        while is_config_mode:
            await asyncio.sleep(0.2)
            gc.collect()
    finally:
        # Stop server and AP
        if _server_obj:
            await stop_webserver(_server_obj)
            _server_obj = None
        try:
            ap.active(False)
            print("AP deactivated")
        except:
            pass


async def autonomous_cycle_once():
    """One short autonomous scan of all plants."""
    for i in range(len(PLANT_PINS)):
        try:
            adc_values[i] = SOIL_ADCs[i].read_u16()
        except Exception as e:
            print("ADC read fail plant", i, e)
            adc_values[i] = 0

        print(f"Plant {i+1} ADC Value: {adc_values[i]} (threshold {moisture_thresholds[i]})")

        if adc_values[i] < moisture_thresholds[i]:
            # Soil is "dry" by your convention: lower value = drier.
            secs = float(auto_water_seconds[i])
            print(f"Plant {i+1} soil is dry. Activating pump for {secs} seconds.")
            try:
                async with pump_locks[i]:
                    motor = EncodedMotor.get_default_encoded_motor(i + 1)
                    motor.set_effort(1.0)
                    await asyncio.sleep(secs)
                    motor.set_effort(0.0)
            except Exception as e:
                print("Pump error:", e)


# -------------------
# Button watcher task
# -------------------
async def button_watcher():
    """Poll a pull-up button; short press toggles config/autonomous."""
    global is_config_mode
    last = 1

    while True:
        try:
            val = USER_BUTTON.value()  # 0 when pressed
            # simple edge detect w/ debounce
            if val == 0 and last == 1:
                await asyncio.sleep_ms(50)
                if USER_BUTTON.value() == 0:
                    is_config_mode = not is_config_mode
                    print("Button pressed -> is_config_mode:", is_config_mode)
                    # wait for release
                    while USER_BUTTON.value() == 0:
                        await asyncio.sleep_ms(10)
            last = val
        except Exception as e:
            print("Button watcher error:", e)
        await asyncio.sleep_ms(20)


# -----
# main
# -----
async def main():
    global is_config_mode

    print("Starting Pico (u)asyncio app...")

    # Kick off the button watcher (no threads)
    asyncio.create_task(button_watcher())

    # Start in autonomous unless user flips the mode
    while True:
        print("Main loop. is_config_mode =", is_config_mode)

        if is_config_mode:
            print("Entering Configuration Mode")
            board.led_on()
            await config_mode_task()  # returns when mode flips to False
            # loop continues, next iteration will run autonomous
        else:
            # Run a single quick autonomous cycle, then yield back to loop
            board.led_off()
            await autonomous_cycle_once()
            await asyncio.sleep(0.1)

        gc.collect()


# Entry point
try:
    asyncio.run(main())
finally:
    # Ensure pumps off if we ever exit
    try:
        for i in range(len(PLANT_PINS)):
            motor = EncodedMotor.get_default_encoded_motor(i + 1)
            motor.set_effort(0.0)
    except:
        pass


