from flask import Flask, render_template, request, send_from_directory
import RPi.GPIO as GPIO
import threading
import time

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
    'mode': 'auto',
    'source_priority': ['solar', 'battery', 'grid'],
    'solar_available': True,
    'battery_available': True,
    'grid_available': True,
    'active_source': None,
    'output_enabled': False
}

def update_power_source():
    while True:
        if state['mode'] == 'auto':
            # Auto source selection logic
            for source in state['source_priority']:
                if source == 'solar' and state['solar_available']:
                    activate_source('solar')
                    break
                elif source == 'battery' and state['battery_available']:
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
        GPIO.output(RELAY_OUTPUT, GPIO.LOW)
    else:
        GPIO.output(RELAY_OUTPUT, GPIO.HIGH)

# Start background thread
thread = threading.Thread(target=update_power_source, daemon=True)
thread.start()

@app.route('/')
def index():
    return render_template('index.html', state=state)

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

@app.route('/set_mode', methods=['POST'])
def set_mode():
    state['mode'] = request.form['mode']
    return index()

@app.route('/set_source', methods=['POST'])
def set_source():
    if state['mode'] == 'manual':
        source = request.form['source']
        state['solar_available'] = source == 'solar'
        state['battery_available'] = source == 'battery'
        state['grid_available'] = source == 'grid'
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