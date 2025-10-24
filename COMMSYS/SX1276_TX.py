#!/usr/bin/env python3
import spidev
import RPi.GPIO as GPIO
import time
import sys

# --- SPI and GPIO Setup ---
SPI_BUS = 0
SPI_DEVICE = 1
GPIO_RESET = 17    # GPIO pin for Reset
GPIO_CS = 8        # GPIO pin for Chip Select (connected to NSS)
GPIO_DIO0 = 24     # GPIO pin for DIO0 (interrupt, mapped to TxDone)

# --- Register Definitions for FSK/OOK Mode ---
REG_FIFO = 0x00
REG_OP_MODE = 0x01
REG_BITRATE_MSB = 0x02
REG_BITRATE_LSB = 0x03
REG_FDEV_MSB = 0x04
REG_FDEV_LSB = 0x05
REG_FRF_MSB = 0x06
REG_FRF_MID = 0x07
REG_FRF_LSB = 0x08
REG_VERSION = 0x42

# Power Amplifier (PA) Configuration
REG_PA_CONFIG = 0x09
REG_PA_RAMP = 0x0A

# FSK Packet and FIFO Configuration
REG_FIFO_ADDR_PTR = 0x0D
REG_FIFO_TX_BASE_ADDR = 0x0E
REG_FIFO_RX_BASE_ADDR = 0x0F # Added for good practice
REG_PREAMBLE_MSB = 0x25
REG_PREAMBLE_LSB = 0x26
REG_SYNC_CONFIG = 0x27
REG_SYNC_VALUE_1 = 0x28
REG_PACKET_CONFIG_1 = 0x2D # Renamed from 0x2D, but it's 0x30 in FSK
REG_PAYLOAD_LENGTH = 0x31 # This is RegPacketConfig2
# --- CORRECTION: FSK Packet Registers are different from LoRa ---
# Based on datasheet, FSK packet handling registers are:
REG_PACKET_CONFIG_1 = 0x30    # Packet Config 1 (FSK)
REG_PAYLOAD_LENGTH_FSK = 0x32 # Payload Length (FSK)
REG_IRQ_FLAGS_1 = 0x3E
REG_DIO_MAPPING_1 = 0x40

# --- FSK/OOK Mode Settings ---
FREQ = 868000000       # 868 MHz
BITRATE = 9600         # 9600 bps
FDEV = 5000            # FSK deviation in Hz (5 kHz)
PREAMBLE_SIZE_SYMBOLS = 8 # 8 bytes
SYNC_WORD = [0xE1, 0x5A, 0xE8, 0x93] # 4-byte Sync Word

def spi_write_register(reg, value):
    """Write a single byte to an SX1276 register."""
    spi.xfer2([reg | 0x80, value])

def spi_read_register(reg):
    """Read a single byte from an SX1276 register."""
    resp = spi.xfer2([reg & 0x7F, 0x00])
    return resp[1]

def calculate_frf(freq):
    """Calculate Frequency Register Value (24-bit). Fstep = 61.03515625 Hz."""
    frf = int(freq / 61.03515625)
    return (frf >> 16) & 0xFF, (frf >> 8) & 0xFF, frf & 0xFF

def calculate_bitrate(bitrate):
    """Calculate Bitrate Register Value (16-bit). Rbitrate = Fosc / Bitrate."""
    br_val = int(32000000 / bitrate)
    return (br_val >> 8) & 0xFF, br_val & 0xFF

def calculate_fdev(fdev):
    """Calculate Frequency Deviation Register Value (16-bit). Fdev = Fstep * RegFdev."""
    fdev_val = int(fdev / 61.03515625)
    return (fdev_val >> 8) & 0xFF, fdev_val & 0xFF


def ping_module():
    try:
        # Read the Version Register (0x42)
        version = spi_read_register(REG_VERSION)
        
        if version == 0x12:
            print(f"Ping successful! SX1276 Version Register (0x42) reads: {hex(version)}")
            return True
        else:
            print(f"Failed to ping! Version Register (0x42) returned: {hex(version)} (Expected: 0x12)")
            return False
            
    except Exception as e:
        print(f"Ping failed due to SPI error: {e}")
        return False



def setup_sx1276():
    """Configures the SX1276 module for FSK transmission."""
    
    # Setup GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(GPIO_RESET, GPIO.OUT)
    GPIO.setup(GPIO_CS, GPIO.OUT)
    GPIO.setup(GPIO_DIO0, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)  
    
    # Reset the module
    GPIO.output(GPIO_RESET, GPIO.LOW)
    time.sleep(0.01)
    GPIO.output(GPIO_RESET, GPIO.HIGH)
    time.sleep(0.01)
    
    if not ping_module():
            print("SX1276 module not responding correctly. Aborting.")
            
    # 1. Enter Sleep mode and set FSK/OOK mode
    # We must be in Sleep mode to set LongRangeMode (Bit 7) to 0 (FSK).
    spi_write_register(REG_OP_MODE, 0x00)  # 0x00 = FSK/OOK mode, Sleep
    time.sleep(0.01)
    
    # 2. Enter Standby mode
    spi_write_register(REG_OP_MODE, 0x02)  # 0x02 = FSK/OOK mode, Standby
    time.sleep(0.01)
    
    # 3. Set frequency
    frf_msb, frf_mid, frf_lsb = calculate_frf(FREQ)
    spi_write_register(REG_FRF_MSB, frf_msb)
    spi_write_register(REG_FRF_MID, frf_mid)
    spi_write_register(REG_FRF_LSB, frf_lsb)
    
    # 4. Set bitrate
    br_msb, br_lsb = calculate_bitrate(BITRATE)
    spi_write_register(REG_BITRATE_MSB, br_msb)
    spi_write_register(REG_BITRATE_LSB, br_lsb)
    
    # 5. Set FSK deviation
    fdev_msb, fdev_lsb = calculate_fdev(FDEV)
    spi_write_register(REG_FDEV_MSB, fdev_msb)
    spi_write_register(REG_FDEV_LSB, fdev_lsb)
    
    # 6. Set Preamble Length (in bytes)
    spi_write_register(REG_PREAMBLE_MSB, 0x00)
    spi_write_register(REG_PREAMBLE_LSB, PREAMBLE_SIZE_SYMBOLS) # 8 bytes
    
    # 7. Configure Sync Word (Access Code)
    # 0x83: SyncOn=1 (Bit 7), SyncSize=3 (bits 2-0, for 3+1 = 4 bytes)
    spi_write_register(REG_SYNC_CONFIG, 0x83)  ### CORRECTED ###
    for i, byte in enumerate(SYNC_WORD):
        spi_write_register(REG_SYNC_VALUE_1 + i, byte)
        
    # 8. Configure Packet Format (Variable length)
    # This is REG_PACKET_CONFIG_1 (0x30)
    # 0x40: Variable length (Bit 7=1), DC-free (none), CRC off, Addr filtering off.
    spi_write_register(REG_PACKET_CONFIG_1, 0x80)  ### CORRECTED ###
    
    # 9. Set FIFO TX Base Address
    spi_write_register(REG_FIFO_TX_BASE_ADDR, 0x00)
    spi_write_register(REG_FIFO_RX_BASE_ADDR, 0x00)
    
    # 10. Configure PA Output Power (Switch to PA_BOOST)
    # 0x8F: PaSelect=1 (PA_BOOST pin), OutputPower=15 (0xF)
    # This gives Pout = 17 - (15 - 15) = +17dBm.
    spi_write_register(REG_PA_CONFIG, 0x8F)  ### CORRECTED ###
    
    # 11. Set PA Ramp Time
    # 0x09: FSK/OOK mode default (40 us)
    spi_write_register(REG_PA_RAMP, 0x09)  
    
    # 12. Map DIO0 to TxDone Interrupt
    # 0x00: DIO0 mapping set to 00 (TxDone).
    spi_write_register(REG_DIO_MAPPING_1, 0x00)  ### CORRECTED ###
    
    print("SX1276 FSK setup complete (Corrected).")


def radio_transmit_data(data):
    """
    Transmits data using FSK mode.
    """
    
    payload = list(data)
    payload_len = len(payload)
    
    if payload_len > 64:
        print(f"Error: Payload too long ({payload_len} bytes). FSK FIFO is 64 bytes.")
        return
    
    # 1. Go to Standby mode
    spi_write_register(REG_OP_MODE, 0x02) # Standby, FSK/OOK
    time.sleep(0.005)

    # 2. Clear IRQ flags (Reading RegIrqFlags1 clears the flags)
    spi_read_register(REG_IRQ_FLAGS_1)  

    # 3. Set FIFO Pointer to TX Base Address (0x00)
    spi_write_register(REG_FIFO_ADDR_PTR, 0x00)
    
    # 4. Write the payload length to the register
    # This is the FIRST byte written to the FIFO in variable length mode.
    # It is NOT written to REG_PAYLOAD_LENGTH_FSK (0x32).
    # Ref: SX1276 Datasheet, section 4.2.12. Packet Handling in FSK
    
    # 5. Write the actual payload to the FIFO
    # We must write the length as the first byte.
    fifo_data = [payload_len] + payload
    print(f"Writing {len(fifo_data)} bytes to FIFO (Len: {payload_len}, Payload: '{data.decode()[:20]}...')")
    
    # Burst write to the FIFO
    spi.xfer2([REG_FIFO | 0x80] + fifo_data)
    
    # 6. Go to Transmit mode
    # 0x03: Transmit mode, FSK/OOK (Mode 011)
    spi_write_register(REG_OP_MODE, 0x03)  
    print("Starting transmission...")
    
    # 7. Wait for transmission to finish (Polling IRQ flags)
    start_time = time.time()
    
    # Preamble + SyncWord + PayloadLengthByte + Payload + CRC (if on)
    total_bytes = PREAMBLE_SIZE_SYMBOLS + len(SYNC_WORD) + 1 + payload_len
    time_on_air = (total_bytes * 8) / BITRATE
    timeout = max(1.0, time_on_air * 5.0)  
    tx_done = False

    while time.time() - start_time < timeout:
        irq_flags = spi_read_register(REG_IRQ_FLAGS_1)
        # Check bit 3 (TxDone = 0x08)
        if irq_flags & 0x08:  
            tx_done = True
            break
        time.sleep(0.01) # Poll every 10ms
        
    # 8. Return to Standby mode
    spi_write_register(REG_OP_MODE, 0x02)
    
    # 9. Report result and clear flags
    if tx_done:
        spi_read_register(REG_IRQ_FLAGS_1) # Clear flags
        print("Transmission complete (TxDone confirmed by IRQ flag polling).")
        print(f"Time on Air estimate: {time_on_air:.3f} s. Polling took: {time.time() - start_time:.3f} s.")
    else:
        spi_read_register(REG_IRQ_FLAGS_1) # Clear flags
        print(f"Transmission failed: Timeout waiting for TxDone flag (Timeout was {timeout:.2f} s).")


if __name__ == "__main__":
    spi = spidev.SpiDev()
    try:
        # Open SPI bus
        spi.open(SPI_BUS, SPI_DEVICE)
        spi.max_speed_hz = 1000000 # 1 MHz
        
        # Configure the SX1276 module
        setup_sx1276()
        
        counter = 0
        print("\n--- Starting Transmission Test Loop ---")
        print("Press Ctrl+C to stop.")
        
        while True:
            counter += 1
            message = f"Packet {counter}: Almeno COMMS funziona! Test test 123."
            data_to_transmit = message.encode('utf-8')
            
            print(f"\n--- Transmitting Packet {counter} ---")
            radio_transmit_data(data_to_transmit)
            
            time.sleep(2) # Wait 2 seconds before next packet

    except KeyboardInterrupt:
        print("\nTest stopped by user.")
        
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()

    finally:
        if 'spi' in locals() and spi:
            spi.close()
        GPIO.cleanup()
        print("Cleanup complete.")