from flask import Flask, render_template, request, send_from_directory
import RPi.GPIO as GPIO
import threading
import time
from datetime import datetime

app = Flask(__name__)

# GPIO Setup
RELAY_GRID = 17
RELAY_BATTERY = 18
RELAY_SOLAR = 27
RELAY_OUTPUT = 22

# Initialize GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Setup relays
for pin in [RELAY_GRID, RELAY_BATTERY, RELAY_SOLAR, RELAY_OUTPUT]:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.HIGH)  # Start in OFF state

# System State
state = {
    'mode': 'auto',  # 'auto', 'manual', or 'cyclic'
    'source_priority': ['solar', 'battery', 'grid'],
    'solar_available': True,
    'battery_available': True,
    'grid_available': True,
    'active_source': None,
    'output_enabled': False,
    'battery_level': 100,  # 0-100%
    'last_battery_update': time.time(),
    'last_source_change': time.time(),
    'cyclic_index': 0
}

def battery_simulator():
    while True:
        if state['output_enabled'] and state['active_source'] == 'battery':
            # Deplete battery only when in use
            elapsed = time.time() - state['last_battery_update']
            depletion_rate = 100 / 3600  # 100% over 1 hour (3600 seconds)
            state['battery_level'] = max(0, state['battery_level'] - elapsed * depletion_rate)
            
            # Reset battery if depleted
            if state['battery_level'] <= 0:
                state['battery_level'] = 100
            
        state['last_battery_update'] = time.time()
        time.sleep(1)

def update_power_source():
    while True:
        current_time = time.time()
        
        # Handle cyclic mode
        if state['mode'] == 'cyclic':
            # Change source every 90 seconds
            if current_time - state['last_source_change'] >= 30:
                next_source = state['source_priority'][state['cyclic_index']]
                activate_source(next_source)
                state['cyclic_index'] = (state['cyclic_index'] + 1) % len(state['source_priority'])
                state['last_source_change'] = current_time
        
        # Handle auto mode
        elif state['mode'] == 'auto':
            # Auto source selection logic
            for source in state['source_priority']:
                if source == 'solar' and state['solar_available']:
                    activate_source('solar')
                    break
                elif source == 'battery' and state['battery_available'] and state['battery_level'] > 45:
                    activate_source('battery')
                    break
                elif source == 'grid' and state['grid_available']:
                    activate_source('grid')
                    break
        
        update_output()
        time.sleep(2)

def activate_source(source):
    # Turn off all sources first
    GPIO.output(RELAY_GRID, GPIO.HIGH)
    GPIO.output(RELAY_BATTERY, GPIO.HIGH)
    GPIO.output(RELAY_SOLAR, GPIO.HIGH)
    
    # Activate selected source
    if source == 'grid':
        GPIO.output(RELAY_GRID, GPIO.LOW)
    elif source == 'battery':
        GPIO.output(RELAY_BATTERY, GPIO.LOW)
    elif source == 'solar':
        GPIO.output(RELAY_SOLAR, GPIO.LOW)
    
    state['active_source'] = source

def update_output():
    # Enable/disable output relay
    if state['output_enabled'] and state['active_source']:
        # Prevent using battery if too low
        if state['active_source'] == 'battery' and state['battery_level'] <= 45:
            GPIO.output(RELAY_OUTPUT, GPIO.HIGH)
        else:
            GPIO.output(RELAY_OUTPUT, GPIO.LOW)
    else:
        GPIO.output(RELAY_OUTPUT, GPIO.HIGH)

# Start background threads
battery_thread = threading.Thread(target=battery_simulator, daemon=True)
battery_thread.start()

power_thread = threading.Thread(target=update_power_source, daemon=True)
power_thread.start()

@app.route('/')
def index():
    # Calculate time to next source change in cyclic mode
    next_change = 0
    if state['mode'] == 'cyclic':
        elapsed = time.time() - state['last_source_change']
        next_change = max(0, 30 - elapsed)
    
    return render_template('index.html', state=state, next_change=next_change)

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

@app.route('/set_mode', methods=['POST'])
def set_mode():
    state['mode'] = request.form['mode']
    
    # Reset cyclic index when switching to cyclic mode
    if state['mode'] == 'cyclic':
        state['cyclic_index'] = 0
        state['last_source_change'] = time.time()
    
    return index()

@app.route('/set_source', methods=['POST'])
def set_source():
    source = request.form['source']
    if state['mode'] == 'manual':
        activate_source(source)
        state['solar_available'] = (source == 'solar')
        state['battery_available'] = (source == 'battery')
        state['grid_available'] = (source == 'grid')
    return index()

@app.route('/toggle_output', methods=['POST'])
def toggle_output():
    state['output_enabled'] = not state['output_enabled']
    update_output()
    return index()

@app.route('/toggle_availability', methods=['POST'])
def toggle_availability():
    source = request.form['source']
    if source == 'solar':
        state['solar_available'] = not state['solar_available']
    elif source == 'battery':
        state['battery_available'] = not state['battery_available']
    elif source == 'grid':
        state['grid_available'] = not state['grid_available']
    return index()

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=80)
    finally:
        GPIO.cleanup()