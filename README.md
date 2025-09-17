# Raspberry Pi Pico WiFi Hotspot Web Server

This MicroPython project creates a WiFi hotspot on the Raspberry Pi Pico and serves a web interface that allows you to control the built-in LED and read analog values.

## Features

- **WiFi Hotspot**: Creates an access point named "PicoHotspot"
- **Web Interface**: Modern, responsive web interface accessible from any device
- **LED Control**: Toggle the built-in LED on/off via web interface
- **Analog Reading**: Read analog values from ADC pin and display on website
- **Real-time Updates**: See current LED status and latest ADC reading

## Hardware Requirements

- Raspberry Pi Pico (or Pico W for WiFi capability)
- Micro USB cable for power and programming
- Optional: Analog sensor (potentiometer, light sensor, etc.) connected to GP26

## Pin Connections

- **Built-in LED**: GP25 (automatically configured)
- **ADC Input**: GP26 (ADC0) - for analog readings

## Setup Instructions

### 1. Install MicroPython on Pico

1. Download the latest MicroPython firmware for Raspberry Pi Pico from [micropython.org](https://micropython.org/download/rp2/)
2. Hold the BOOTSEL button on the Pico while connecting it to your computer
3. The Pico will appear as a USB mass storage device
4. Copy the `.uf2` firmware file to the Pico
5. The Pico will restart and run MicroPython

### 2. Upload the Code

1. Connect the Pico to your computer
2. Copy `main.py` to the Pico's file system
3. The Pico will automatically run `main.py` on boot

### 3. Connect to the Hotspot

1. Power on the Pico
2. Look for a WiFi network named "PicoHotspot"
3. Connect to it using password: `12345678`
4. Open a web browser and navigate to: `http://192.168.4.1`

## Usage

### Web Interface

The web interface provides:

1. **LED Control Button**: Click to toggle the built-in LED on/off
2. **Read Analog Button**: Click to read the current analog value from GP26
3. **Status Display**: Shows current LED state and latest ADC reading

### LED Control

- The LED button changes color based on current state (green = off, red = on)
- Click the button to toggle between ON and OFF states
- The built-in LED on the Pico will physically turn on/off

### Analog Reading

- Connect an analog sensor (like a potentiometer) to GP26
- Click "Read Analog Value" to get the current reading
- Values range from 0 to 65535 (16-bit ADC)
- The reading is displayed prominently on the webpage

## Code Structure

- `main.py`: Main program file containing all functionality
- WiFi hotspot creation and configuration
- Web server implementation
- HTML generation with embedded CSS
- HTTP request handling
- Hardware control (LED and ADC)

## Customization

### Change WiFi Settings

Edit these lines in `main.py`:

```python
ap.config(essid='YourNetworkName', password='YourPassword', authmode=network.AUTH_WPA_WPA2_PSK)
```

### Change ADC Pin

To use a different ADC pin, modify:

```python
adc = ADC(26)  # Change 26 to your desired pin (26, 27, or 28)
```

### Modify Web Interface

The HTML and CSS are embedded in the `generate_html()` function. You can customize the appearance by modifying the HTML string.

## Troubleshooting

### Pico Not Creating Hotspot

- Ensure you're using a Pico W (has WiFi capability)
- Check that MicroPython is properly installed
- Verify the code is uploaded as `main.py`

### Can't Connect to Hotspot

- Make sure the Pico is powered on
- Check that the SSID "PicoHotspot" appears in your WiFi list
- Try the password: `12345678`
- Some devices may take a moment to connect

### Web Interface Not Loading

- Ensure you're connected to the PicoHotspot WiFi
- Try accessing `http://192.168.4.1` in your browser
- Check the Pico's serial output for error messages

### ADC Readings Not Working

- Verify your analog sensor is connected to GP26
- Check wiring connections
- Ensure the sensor is powered if required

## Technical Details

- **WiFi Mode**: Access Point (AP) mode
- **IP Address**: 192.168.4.1 (default AP address)
- **Port**: 80 (HTTP)
- **ADC Resolution**: 16-bit (0-65535)
- **Memory Management**: Includes garbage collection to prevent memory issues

## Security Notes

- The default WiFi password is simple for testing
- Change the password for production use
- The web interface has no authentication
- Consider adding security measures for sensitive applications

## License

This project is open source and available under the MIT License.
