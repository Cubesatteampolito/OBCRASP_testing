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

# FSK Packet and FIFO Configuration
REG_FIFO_ADDR_PTR = 0x0D      # FIFO Address Pointer
REG_FIFO_TX_BASE_ADDR = 0x0E  # FIFO Transmit Base Address (set to 0x00)
REG_PREAMBLE_MSB = 0x25       # Preamble Length MSB
REG_PREAMBLE_LSB = 0x26       # Preamble Length LSB
REG_SYNC_CONFIG = 0x27        # Sync Word Configuration
REG_SYNC_VALUE_1 = 0x28       # Start of Sync Word
REG_PACKET_CONFIG_1 = 0x2D    # Packet Format Configuration (e.g., Variable/Fixed length)
REG_PAYLOAD_LENGTH = 0x31     # Payload Length (only used for variable/fixed modes)
REG_IRQ_FLAGS_1 = 0x3E        # Interrupt flags
REG_DIO_MAPPING_1 = 0x40      # DIO mapping for TxDone

# --- FSK/OOK Mode Settings ---
FREQ = 868000000        # 868 MHz
BITRATE = 9600          # 9600 bps
FDEV = 5000             # FSK deviation in Hz (5 kHz)
PREAMBLE_SIZE_SYMBOLS = 8 # 8 symbols (8 * 1 byte * bitrate)
# The Access Code (Sync Word) will be handled by the chip's internal registers (up to 8 bytes)
SYNC_WORD = [0xE1, 0x5A, 0xE8, 0x93] # 4-byte Sync Word

def spi_write_register(reg, value):
    """Write a single byte to an SX1276 register."""
    # Write operation requires MSB of address to be set (reg | 0x80)
    spi.xfer2([reg | 0x80, value])

def spi_read_register(reg):
    """Read a single byte from an SX1276 register."""
    # Read operation requires MSB of address to be 0 (reg & 0x7F)
    # The second byte is a dummy byte for the chip to return the value
    resp = spi.xfer2([reg & 0x7F, 0x00])
    return resp[1]

def calculate_frf(freq):
    """Calculate Frequency Register Value (24-bit). Fstep = 61.03515625 Hz."""
    frf = int(freq / 61.03515625)
    return (frf >> 16) & 0xFF, (frf >> 8) & 0xFF, frf & 0xFF

def calculate_bitrate(bitrate):
    """Calculate Bitrate Register Value (16-bit). Rbitrate = Fosc / Bitrate."""
    # Fosc = 32 MHz
    br_val = int(32000000 / bitrate)
    return (br_val >> 8) & 0xFF, br_val & 0xFF

def calculate_fdev(fdev):
    """Calculate Frequency Deviation Register Value (16-bit). Fdev = Fstep * RegFdev."""
    fdev_val = int(fdev / 61.03515625)
    return (fdev_val >> 8) & 0xFF, fdev_val & 0xFF

def setup_sx1276():
    """Configures the SX1276 module for FSK transmission."""
    
    # Setup GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(GPIO_RESET, GPIO.OUT)
    GPIO.setup(GPIO_CS, GPIO.OUT)
    # Setup DIO0 as input for interrupt handling (TxDone)
    GPIO.setup(GPIO_DIO0, GPIO.IN, pull_up_down=GPIO.PUD_DOWN) 
    
    # Reset the module
    GPIO.output(GPIO_RESET, GPIO.LOW)
    time.sleep(0.01)
    GPIO.output(GPIO_RESET, GPIO.HIGH)
    time.sleep(0.01)
    
    # 1. Enter Standby mode, FSK/OOK mode
    spi_write_register(REG_OP_MODE, 0x02)  # Standby mode, FSK/OOK mode (Mode 010)
    time.sleep(0.01)
    
    # 2. Set frequency
    frf_msb, frf_mid, frf_lsb = calculate_frf(FREQ)
    spi_write_register(REG_FRF_MSB, frf_msb)
    spi_write_register(REG_FRF_MID, frf_mid)
    spi_write_register(REG_FRF_LSB, frf_lsb)
    
    # 3. Set bitrate
    br_msb, br_lsb = calculate_bitrate(BITRATE)
    spi_write_register(REG_BITRATE_MSB, br_msb)
    spi_write_register(REG_BITRATE_LSB, br_lsb)
    
    # 4. Set FSK deviation
    fdev_msb, fdev_lsb = calculate_fdev(FDEV)
    spi_write_register(REG_FDEV_MSB, fdev_msb)
    spi_write_register(REG_FDEV_LSB, fdev_lsb)
    
    # 5. Set Preamble Length (in symbols)
    # The preamble is 8 symbols long (0x0008)
    spi_write_register(REG_PREAMBLE_MSB, 0x00)
    spi_write_register(REG_PREAMBLE_LSB, PREAMBLE_SIZE_SYMBOLS) 
    
    # 6. Configure Sync Word (Access Code)
    # 0x18: SyncOn=1, SyncSize=4 bytes, AutoRestartRx=00 (off)
    spi_write_register(REG_SYNC_CONFIG, 0x18) 
    for i, byte in enumerate(SYNC_WORD):
        spi_write_register(REG_SYNC_VALUE_1 + i, byte)
        
    # 7. Configure Packet Format (Variable length, CRC check off for simplicity)
    # 0x02: Variable length, DC-free encoding (none), CRC off, Address filtering off.
    spi_write_register(REG_PACKET_CONFIG_1, 0x02)
    
    # 8. Set FIFO TX Base Address (Start writing from the beginning of the buffer)
    spi_write_register(REG_FIFO_TX_BASE_ADDR, 0x00)
    
    # 9. Map DIO0 to TxDone Interrupt
    # 0x80: DIO0 mapping set to 00 (TxDone)
    spi_write_register(REG_DIO_MAPPING_1, 0x80) 
    
    print("SX1276 FSK setup complete.")


def radio_transmit_data(data):
    """
    Transmits data using FSK mode.
    The chip handles Preamble and Sync Word automatically based on setup.
    """
    
    payload = list(data)
    payload_len = len(payload)
    
    # 1. Go to Standby mode
    spi_write_register(REG_OP_MODE, 0x02) # Standby, FSK/OOK
    time.sleep(0.005)

    # 2. Reset and Clear IRQ flags (Clear TxDone flag if it was set)
    # Reading RegIrqFlags1 (0x3E) clears the flags
    spi_read_register(REG_IRQ_FLAGS_1) 

    # 3. Set FIFO Pointer to TX Base Address (0x00)
    spi_write_register(REG_FIFO_ADDR_PTR, 0x00)
    
    # 4. Write the payload length to the register
    spi_write_register(REG_PAYLOAD_LENGTH, payload_len)
    
    # 5. Write the actual payload to the FIFO
    print(f"Writing {payload_len} bytes to FIFO (Payload: '{data.decode()[:20]}...')")
    
    # Create the full command: REG_FIFO | 0x80 (write) followed by the data
    # We write directly to the FIFO register 0x00, but the hardware auto-increments the pointer
    spi.xfer2([REG_FIFO | 0x80] + payload)
    
    # 6. Go to Transmit mode
    # 0x03: Transmit mode, FSK/OOK (Mode 011) - **FIXED THIS**
    spi_write_register(REG_OP_MODE, 0x03) 
    print(f"Starting transmission...")
    
    # 7. Wait for transmission to finish (TxDone interrupt on DIO0)
    # 5-second timeout for safety
    try:
        # Wait for a falling edge (change from HIGH to LOW) on the DIO0 pin
        # The TxDone IRQ is a pulse. We wait for it to happen.
        GPIO.wait_for_edge(GPIO_DIO0, GPIO.RISING, timeout=5000)
        
        # Read IRQ flags to confirm TxDone and clear the flag
        irq_flags = spi_read_register(REG_IRQ_FLAGS_1)
        if irq_flags & 0x08: # Check bit 3 (TxDone)
            print("Transmission complete (TxDone confirmed by IRQ flag).")
        else:
            print("Transmission timed out or failed to set TxDone flag.")

    except RuntimeWarning:
        print("Timeout waiting for TxDone interrupt.")
        
    except Exception as e:
        print(f"An error occurred during wait_for_edge: {e}")
        
    # 8. Return to Standby mode
    spi_write_register(REG_OP_MODE, 0x02)


if __name__ == "__main__":
    spi = spidev.SpiDev()
    try:
        # Open SPI bus
        spi.open(SPI_BUS, SPI_DEVICE)
        spi.max_speed_hz = 1000000 # 1 MHz
        
        # Configure the SX1276 module
        setup_sx1276()
        
        # --- MESSAGE TO TRANSMIT ---
        # The message length must be <= 255 bytes for FSK mode
        message = "Almeno COMMS funziona - This is a test message over FSK/OOK."
        data_to_transmit = message.encode('utf-8')
        
        radio_transmit_data(data_to_transmit)

    except Exception as e:
        # Check if running on a real Pi environment
        if 'RPi' in sys.modules:
            print(f"An error occurred: {e}")
        else:
            print(f"An error occurred (Did you run this on a Raspberry Pi?): {e}")

    finally:
        if 'spi' in locals() and spi:
            spi.close()
        GPIO.cleanup()
        print("Cleanup complete.")
