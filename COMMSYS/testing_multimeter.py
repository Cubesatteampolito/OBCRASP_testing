import time

import RPi.GPIO as GPIO

# BCM pin numbers for SPI0
CE0 = 8      # NSS / CE0
SCLK = 11
MOSI = 10
MISO = 9
GND = 6      # any GND pin for reference (not used by script)

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

# Setup
GPIO.setup(CE0, GPIO.OUT, pull_up_down=GPIO.PUD_OFF)
GPIO.setup(SCLK, GPIO.OUT, pull_up_down=GPIO.PUD_OFF)
GPIO.setup(MOSI, GPIO.OUT, pull_up_down=GPIO.PUD_OFF)
GPIO.setup(MISO, GPIO.IN, pull_up_down=GPIO.PUD_OFF)  # leave floating if no slave

try:
    # Make sure idle lines are high (SPI idle = high on many setups)
    GPIO.output(CE0, GPIO.LOW)
    GPIO.output(SCLK, GPIO.HIGH)
    GPIO.output(MOSI, GPIO.HIGH)
    print("MOSI set HIGH for 5s -> multimeter should read ~3.3V")
    time.sleep(5)

    GPIO.output(MOSI, GPIO.LOW)
    print("MOSI set LOW for 5s -> multimeter should read ~0V")
    time.sleep(5)

    # Slow toggle to let you see changing average voltage on a multimeter
    print("Toggling MOSI slowly (1 Hz) for 8 seconds")
    for _ in range(8):
        GPIO.output(MOSI, GPIO.HIGH)
        time.sleep(0.5)
        GPIO.output(MOSI, GPIO.LOW)
        time.sleep(0.5)

    # Simple SPI-like transfer (CE0 low while clock pulses)
    # Send a byte 0b10101010 on MOSI at a slow rate so a meter/logic probe can observe.
    byte_to_send = 0b10101010
    bit_period = 0.001  # 1 kHz clock -> 1 ms period (adjust slower if needed)
    print("Emulating SPI transfer. Pull CE0 LOW, clock pulses, MOSI driven.")
    GPIO.output(CE0, GPIO.LOW)
    time.sleep(0.01)
    for bit in range(7, -1, -1):
        bit_val = (byte_to_send >> bit) & 1
        GPIO.output(MOSI, GPIO.HIGH if bit_val else GPIO.LOW)
        # clock falling->rising (adjust to match your target CPOL/CPHA if needed)
        GPIO.output(SCLK, GPIO.LOW)
        time.sleep(bit_period / 2)
        GPIO.output(SCLK, GPIO.HIGH)
        time.sleep(bit_period / 2)
    GPIO.output(CE0, GPIO.HIGH)
    print("Transfer complete. If a slave is present and drives MISO, you should see changes on MISO while CE0 was LOW.")

    time.sleep(1)

finally:
    GPIO.cleanup()
    print("GPIO cleaned up. Done.")
