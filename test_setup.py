"""
Test script to verify hardware setup and basic functionality.
Run this before main.py to ensure everything is working correctly.
"""

from machine import Pin, ADC
import time

def test_led():
    """Test the built-in LED"""
    print("Testing LED...")
    led = Pin(25, Pin.OUT)
    
    # Blink LED 3 times
    for i in range(3):
        led.value(True)
        print("LED ON")
        time.sleep(0.5)
        led.value(False)
        print("LED OFF")
        time.sleep(0.5)
    
    print("LED test completed")

def test_adc():
    """Test the ADC reading"""
    print("Testing ADC...")
    adc = ADC(26)
    
    # Take 5 readings
    for i in range(5):
        value = adc.read_u16()
        print(f"ADC Reading {i+1}: {value}")
        time.sleep(1)
    
    print("ADC test completed")

def test_wifi():
    """Test WiFi functionality"""
    print("Testing WiFi...")
    try:
        import network
        ap = network.WLAN(network.AP_IF)
        ap.active(True)
        ap.config(essid='TestHotspot', password='12345678')
        
        # Wait a moment for AP to start
        time.sleep(2)
        
        if ap.active():
            print("WiFi Access Point created successfully")
            print(f"SSID: TestHotspot")
            print(f"IP: {ap.ifconfig()[0]}")
        else:
            print("Failed to create WiFi Access Point")
            
        # Clean up
        ap.active(False)
        
    except Exception as e:
        print(f"WiFi test failed: {e}")

def main():
    """Run all tests"""
    print("=== Pico Hardware Test ===")
    print()
    
    test_led()
    print()
    
    test_adc()
    print()
    
    test_wifi()
    print()
    
    print("=== Test completed ===")
    print("If all tests passed, you can run main.py")

if __name__ == '__main__':
    main()
