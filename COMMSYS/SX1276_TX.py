import spidev
import RPi.GPIO as GPIO
import time
import sys
import traceback

# --- SPI and GPIO Setup ---
SPI_BUS = 0
SPI_DEVICE = 1
GPIO_RESET = 17    # GPIO pin for Reset
GPIO_CS = 8        # GPIO pin for Chip Select (connected to NSS)
GPIO_DIO0 = 24     # GPIO pin for DIO0 (interrupt, mapped to PacketSent)

# --- Register Definitions for FSK/OOK Mode (Datasheet Verified) ---
REG_FIFO = 0x00
REG_OP_MODE = 0x01
REG_BITRATE_MSB = 0x02
REG_BITRATE_LSB = 0x03
REG_FDEV_MSB = 0x04
REG_FDEV_LSB = 0x05
REG_FRF_MSB = 0x06
REG_FRF_MID = 0x07
REG_FRF_LSB = 0x08
REG_PA_CONFIG = 0x09
REG_PA_RAMP = 0x0A
REG_OCP = 0x0B
REG_LNA = 0x0C
REG_RX_CONFIG = 0x0D
REG_RSSI_CONFIG = 0x0E
REG_RSSI_COLLISION = 0x0F
REG_RSSI_THRESH = 0x10
REG_RSSI_VALUE = 0x11
REG_RX_BW = 0x12
REG_AFC_BW = 0x13
REG_OOK_PEAK = 0x14
REG_OOK_FIX = 0x15
REG_OOK_AVG = 0x16
REG_AFC_FEI = 0x1A
REG_AFC_MSB = 0x1B
REG_AFC_LSB = 0x1C
REG_FEI_MSB = 0x1D
REG_FEI_LSB = 0x1E
REG_PREAMBLE_DETECT = 0x1F
REG_RX_TIMEOUT_1 = 0x20
REG_RX_TIMEOUT_2 = 0x21
REG_RX_TIMEOUT_3 = 0x22
REG_RX_DELAY = 0x23
REG_OSC = 0x24
REG_PREAMBLE_MSB = 0x25
REG_PREAMBLE_LSB = 0x26
REG_SYNC_CONFIG = 0x27
REG_SYNC_VALUE_1 = 0x28
REG_SYNC_VALUE_2 = 0x29
REG_SYNC_VALUE_3 = 0x2A
REG_SYNC_VALUE_4 = 0x2B
REG_SYNC_VALUE_5 = 0x2C
REG_SYNC_VALUE_6 = 0x2D
REG_SYNC_VALUE_7 = 0x2E
REG_SYNC_VALUE_8 = 0x2F
REG_PACKET_CONFIG_1 = 0x30
REG_PACKET_CONFIG_2 = 0x31
REG_PAYLOAD_LENGTH_FSK = 0x32
REG_NODE_ADRS = 0x33
REG_BROADCAST_ADRS = 0x34
REG_FIFO_THRESH = 0x35
REG_SEQ_CONFIG_1 = 0x36
REG_SEQ_CONFIG_2 = 0x37
REG_IMAGE_CAL = 0x3B
REG_TEMP = 0x3C
REG_LOW_BAT = 0x3D
REG_IRQ_FLAGS_1 = 0x3E
REG_IRQ_FLAGS_2 = 0x3F
REG_DIO_MAPPING_1 = 0x40
REG_DIO_MAPPING_2 = 0x41
REG_VERSION = 0x42
REG_PLL_HOP = 0x44
REG_TCXO = 0x4B
REG_PA_DAC = 0x4D
REG_BITRATE_FRAC = 0x5D

# --- Global Settings ---
# These are used in setup_sx1276 and radio_transmit_data
FREQ = 867000000
BITRATE = 9600
FDEV = 5000
PREAMBLE_LEN_BYTES = 8
SYNC_WORD = [0xE1, 0x5A, 0xE8, 0x93]

# --- SPI Handle (Global for functions) ---
spi = None

# --- SPI Functions ---
def spi_write_register(reg, value):
    """Write a single byte to an SX1276 register."""
    if spi is None:
        print("ERROR: SPI not initialized.")
        return
    spi.xfer2([reg | 0x80, value]) # Set MSb for write [cite: 2313]

def spi_read_register(reg):
    """Read a single byte from an SX1276 register."""
    if spi is None:
        print("ERROR: SPI not initialized.")
        return None
    resp = spi.xfer2([reg & 0x7F, 0x00]) # Clear MSb for read [cite: 2313]
    return resp[1]

# --- Setup Function (Corrected) ---
def setup_sx1276():
    """Configures the SX1276 module for FSK transmission based on datasheet."""
    # ... (Paste the corrected setup_sx1276 function from above here) ...
    # --- GPIO Setup ---
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(GPIO_RESET, GPIO.OUT)
    GPIO.setup(GPIO_CS, GPIO.OUT)
    GPIO.setup(GPIO_DIO0, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
    
    # --- Reset the module ---
    print("Resetting SX1276...")
    GPIO.output(GPIO_RESET, GPIO.LOW)
    time.sleep(0.01)
    GPIO.output(GPIO_RESET, GPIO.HIGH)
    time.sleep(0.05) # Allow a bit longer after reset
    
    # --- Basic Configuration ---
    # 1. Enter Sleep mode & Ensure FSK/OOK Mode
    spi_write_register(REG_OP_MODE, 0b00000000) # Sleep, FSK/OOK 
    time.sleep(0.01)
    
    op_mode = spi_read_register(REG_OP_MODE)
    if op_mode & 0x80:
        print("ERROR: Failed to set FSK/OOK mode. Still in LoRa mode.")
        return False
    if op_mode & 0x07 != 0x00:
        print(f"ERROR: Failed to enter Sleep mode. Current mode: {op_mode & 0x07}")
        return False
    print("Entered Sleep mode, FSK/OOK selected.")

    # 2. Enter Standby mode
    spi_write_register(REG_OP_MODE, 0b00000001) # Standby, FSK/OOK [cite: 1459, 2729]
    time.sleep(0.01)
    op_mode = spi_read_register(REG_OP_MODE)
    if op_mode & 0x07 != 0x01:
         print(f"ERROR: Failed to enter Standby mode. Current mode: {op_mode & 0x07}")
         return False
    print("Entered Standby mode.")

    # --- RF Parameters ---
    # 3. Set frequency to 867 MHz
    frf_val = int(FREQ / (32000000 / (1 << 19))) # F_RF / F_STEP [cite: 876, 335]
    frf_msb = (frf_val >> 16) & 0xFF
    frf_mid = (frf_val >> 8) & 0xFF
    frf_lsb = frf_val & 0xFF
    spi_write_register(REG_FRF_MSB, frf_msb)
    spi_write_register(REG_FRF_MID, frf_mid)
    spi_write_register(REG_FRF_LSB, frf_lsb) # Writing LSB triggers update 
    print(f"Set Frequency: {FREQ/1e6:.3f} MHz (Registers: 0x{frf_msb:02X}{frf_mid:02X}{frf_lsb:02X})")

    # 4. Set bitrate to 9600 bps
    br_val = int(32000000 / BITRATE) # FXOSC / Bitrate [cite: 1226]
    br_msb = (br_val >> 8) & 0xFF
    br_lsb = br_val & 0xFF
    spi_write_register(REG_BITRATE_MSB, br_msb)
    spi_write_register(REG_BITRATE_LSB, br_lsb)
    spi_write_register(REG_BITRATE_FRAC, 0x00) # Set fractional part to 0 [cite: 2841]
    print(f"Set Bitrate: {BITRATE} bps (Registers: 0x{br_msb:02X}{br_lsb:02X})")

    # 5. Set FSK deviation to 5 kHz
    fdev_val = int(FDEV / (32000000 / (1 << 19))) # FDEV / FSTEP [cite: 1246, 335]
    if FDEV + (BITRATE / 2) > 250000: # [cite: 1248]
        print(f"ERROR: FDEV ({FDEV} Hz) + Bitrate/2 ({BITRATE/2} Hz) exceeds 250 kHz!")
        return False
    fdev_msb = (fdev_val >> 8) & 0xFF
    fdev_lsb = fdev_val & 0xFF
    spi_write_register(REG_FDEV_MSB, fdev_msb)
    spi_write_register(REG_FDEV_LSB, fdev_lsb)
    print(f"Set FSK Deviation: {FDEV} Hz (Registers: 0x{fdev_msb:02X}{fdev_lsb:02X})")

    # --- Power Amplifier Configuration ---
    # 6. Configure PA Output (Use RFO Pin, moderate power ~+10dBm)
    pa_config_val = 0x7A # 
    spi_write_register(REG_PA_CONFIG, pa_config_val)
    spi_write_register(REG_PA_DAC, 0x84) # Default value 
    print(f"Set PA Config: RFO pin, target ~+10 dBm (RegPaConfig=0x{pa_config_val:02X})")

    # 7. Set PA Ramp Time
    spi_write_register(REG_PA_RAMP, 0x09) # Default 40 us [cite: 2738]
    print("Set PA Ramp Time: 40 us (Default)")

    # 8. Set Over Current Protection (OCP)
    spi_write_register(REG_OCP, 0x0B) # Default 100mA [cite: 2745]
    print("Set OCP: Enabled, 100 mA (Default)")

    # --- Packet Handler Configuration ---
    # 9. Set Preamble Length to 8 bytes
    spi_write_register(REG_PREAMBLE_MSB, (PREAMBLE_LEN_BYTES >> 8) & 0xFF)
    spi_write_register(REG_PREAMBLE_LSB, PREAMBLE_LEN_BYTES & 0xFF)
    print(f"Set Preamble Length: {PREAMBLE_LEN_BYTES} bytes")

    # 10. Configure Sync Word
    sync_size = len(SYNC_WORD)
    if not 1 <= sync_size <= 8:
        print(f"ERROR: Invalid Sync Word Size ({sync_size}). Must be 1-8 bytes.")
        return False
    sync_config_val = (0b00 << 6) | (0b0 << 5) | (0b1 << 4) | ((sync_size - 1) & 0x07) # 
    spi_write_register(REG_SYNC_CONFIG, sync_config_val)
    for i, byte in enumerate(SYNC_WORD):
        spi_write_register(REG_SYNC_VALUE_1 + i, byte)
    print(f"Set Sync Word: Enabled, Size={sync_size} bytes, Value={['0x{:02X}'.format(b) for b in SYNC_WORD]}")

    # 11. Configure Packet Format
    packet_config_1_val = 0x80 # Variable length, CRC off 
    spi_write_register(REG_PACKET_CONFIG_1, packet_config_1_val)
    packet_config_2_val = 0x40 # Packet mode active 
    spi_write_register(REG_PACKET_CONFIG_2, packet_config_2_val)
    print("Set Packet Mode: Variable Length, Packet Mode Active, CRC Off")

    # 12. Set FIFO Threshold
    spi_write_register(REG_FIFO_THRESH, 0x8F) # Tx starts >= 1 byte 
    print("Set FIFO Threshold: Tx starts when >= 1 byte in FIFO")

    # --- Interrupt/IO Mapping ---
    # 13. Map DIO0 to PacketSent
    spi_write_register(REG_DIO_MAPPING_1, 0x00) # Map DIO0 to 00 [cite: 1917, 2833]
    spi_write_register(REG_DIO_MAPPING_2, 0x00) # Keep others default
    print("Mapped DIO0 to PacketSent IRQ")
    
    # --- Final Check ---
    version = spi_read_register(REG_VERSION)
    print(f"Read Chip Version: 0x{version:02X} (Expected 0x12)")
    if version != 0x12:
        print("WARN: Unexpected chip version read.")
        # return False # Decide if this should be fatal

    print("--- SX1276 FSK setup complete (Datasheet Verified) ---")
    return True

# --- Transmit Function (Corrected) ---
def radio_transmit_data(data):
    """Transmits data using FSK Packet mode (Datasheet Verified)."""
    # ... (Paste the corrected radio_transmit_data function from above here) ...
    payload = list(data)
    payload_len = len(payload)
    
    if payload_len > 63:
        print(f"ERROR: Payload too long ({payload_len} bytes). Max is 63 for FSK FIFO in Variable mode.")
        return False
        
    # 1. Go to Standby mode
    spi_write_register(REG_OP_MODE, 0x01) # Standby, FSK/OOK 
    time.sleep(0.005)

    # 2. Clear IRQ flags
    spi_read_register(REG_IRQ_FLAGS_1) # [cite: 2817]
    spi_read_register(REG_IRQ_FLAGS_2) # [cite: 2824]

    # 3. Write payload (length byte first) to FIFO
    fifo_data = [payload_len] + payload # 
    print(f"Writing {len(fifo_data)} bytes to FIFO (Len: {payload_len}, Payload: '{data.decode()[:20]}...')")
    spi.xfer2([REG_FIFO | 0x80] + fifo_data) # [cite: 2313]
    
    # 4. Go to Transmit mode
    spi_write_register(REG_OP_MODE, 0x03) # Transmit, FSK/OOK 
    print("Starting transmission...")
    
    # 5. Wait for transmission to finish by polling PacketSent flag
    start_time = time.time()
    total_bytes = PREAMBLE_LEN_BYTES + len(SYNC_WORD) + 1 + payload_len
    time_on_air = (total_bytes * 8) / BITRATE
    timeout = max(1.0, time_on_air * 5.0)
    tx_done = False

    while time.time() - start_time < timeout:
        irq_flags_2 = spi_read_register(REG_IRQ_FLAGS_2)
        if irq_flags_2 & 0x08: # Check bit 3 (PacketSent) 
            tx_done = True
            break
        time.sleep(0.01)
        
    # 6. Return to Standby mode
    spi_write_register(REG_OP_MODE, 0x01) # Standby 
    
    # 7. Report result and clear flags
    final_irq_flags_1 = spi_read_register(REG_IRQ_FLAGS_1)
    final_irq_flags_2 = spi_read_register(REG_IRQ_FLAGS_2)
    
    if tx_done:
        print("Transmission complete (PacketSent confirmed by IRQ flag polling).")
        print(f"Time on Air estimate: {time_on_air:.4f} s. Polling took: {time.time() - start_time:.3f} s.")
        return True
    else:
        print(f"Transmission failed: Timeout waiting for PacketSent flag (Timeout was {timeout:.2f} s).")
        print(f"Final IRQ Flags 1: 0x{final_irq_flags_1:02X}, Flags 2: 0x{final_irq_flags_2:02X}")
        current_op_mode = spi_read_register(REG_OP_MODE)
        print(f"Current OpMode after timeout: 0x{current_op_mode:02X}")
        return False

# --- Main Execution Block ---
if __name__ == "__main__":
    try:
        # Initialize SPI
        spi = spidev.SpiDev()
        spi.open(SPI_BUS, SPI_DEVICE)
        spi.max_speed_hz = 1000000 # 1 MHz
        
        # Configure the SX1276 module
        if not setup_sx1276():
            raise RuntimeError("Failed to set up SX1276.")
            
        counter = 0
        print("\n--- Starting Transmission Test Loop ---")
        print("Press Ctrl+C to stop.")
        
        while True:
            counter += 1
            # Keep message reasonably short to fit in FIFO (max 63 bytes payload)
            message = f"Pkt {counter}: Test @ {time.strftime('%H:%M:%S')}"
            data_to_transmit = message.encode('utf-8')
            
            if len(data_to_transmit) > 63:
                 print(f"WARN: Truncating message to fit 63 bytes (was {len(data_to_transmit)})")
                 data_to_transmit = data_to_transmit[:63]

            print(f"\n--- Transmitting Packet {counter} ---")
            success = radio_transmit_data(data_to_transmit)
            if not success:
                print("Transmission attempt failed, check previous logs.")
                # Optional: Add a longer delay or stop after failure
                # time.sleep(5)
            
            time.sleep(2) # Wait 2 seconds before next packet

    except KeyboardInterrupt:
        print("\nTest stopped by user.")
        
    except Exception as e:
        print(f"An error occurred: {e}")
        traceback.print_exc()

    finally:
        # Cleanup
        if spi:
            # Attempt to put the chip in a low power state
            try:
                print("Setting SX1276 to Sleep mode...")
                spi_write_register(REG_OP_MODE, 0x00) # Sleep FSK
            except Exception as cleanup_e:
                print(f"Error during cleanup: {cleanup_e}")
            finally:
                spi.close()
                print("SPI closed.")
        GPIO.cleanup()
        print("GPIO cleanup complete.")