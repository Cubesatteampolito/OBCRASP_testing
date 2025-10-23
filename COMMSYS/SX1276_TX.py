import spidev
import RPi.GPIO as GPIO
import time

# SPI and GPIO setup
SPI_BUS = 0
SPI_DEVICE = 0
GPIO_RESET = 17  # GPIO pin for Reset
GPIO_CS = 8      # GPIO pin for Chip Select (connected to NSS)
GPIO_DIO0 = 24   # GPIO pin for DIO0 (interrupt)

# Register definitions for SX1276 (FSK/OOK mode)
REG_OP_MODE = 0x01
REG_FRF_MSB = 0x06
REG_FRF_MID = 0x07
REG_FRF_LSB = 0x08
REG_BITRATE_MSB = 0x02
REG_BITRATE_LSB = 0x03
REG_FDEV_MSB = 0x04
REG_FDEV_LSB = 0x05
REG_FIFO = 0x00
REG_PAYLOAD_LENGTH = 0x31

#FSK/OOK mode settings
FREQ = 867000000  # 867 MHz
BITRATE = 9600    # 9600 bps
FDEV = 5000       # FSK deviation in Hz (e.g., 5 kHz)

# Header settings
PREAMBLE_SIZE = 4   # Number of preamble bytes (0xAA)
ACCESS_CODE = [0xE1, 0x5A, 0xE8, 0x93]

def calculate_frf(freq):
    # Calculate Frequency Register Value
    # GA: more on that in 4.1.4
    # GA: info sulle operazioni che svolge: frf >> 16 sposta di 2 byte, poi AND con 0xFF (11111111) come maschera. Lui chiede un 24 bit rappresentativo di frf diviso in 3 parti da 1 byte (quindi msb, mid, lsb)
    frf = int(freq / 61.03515625) # 61.03515625 = Fosc / 2^19 = 32MHz / 2^19
    return (frf >> 16) & 0xFF, (frf >> 8) & 0xFF, frf & 0xFF

def calculate_bitrate(bitrate):
    # Calculate Bitrate Register Value
    # GA: more on 4.2.1, E' ERRATO QUI, VA SISTEMATA LA FORMULA CON I FRAZIONARI
    br_val = int(32000000 / bitrate)
    return (br_val >> 8) & 0xFF, br_val & 0xFF

def calculate_fdev(fdev):
    # Calculate Frequency Deviation Register Value
    # GA: concordo, ma andrebbe moltiplicata per RegFdevMsb e RegFdevLsb
    fdev_val = int(fdev / 61.03515625) # 61.03515625 = Fosc / 2^19
    return (fdev_val >> 8) & 0xFF, fdev_val & 0xFF

def spi_write_register(reg, value):
    # Write a single byte to an SX1276 register
    # GA: svolge un OR tra reg e 0x80 (10000000) così da forzare 1 come msb che viene richiesto per scrivere in un registro (0 per leggere) (per leggere 0 basta un AND con 0x7F (01111111), quindi scelgo il value da applicare a quel registro.
    spi.xfer2([reg | 0x80, value])

def setup_sx1276():
    # Setup GPIO
    # GA: STANDARD
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(GPIO_RESET, GPIO.OUT)
    GPIO.setup(GPIO_CS, GPIO.OUT)
    
    # Reset the module
    GPIO.output(GPIO_RESET, GPIO.LOW)
    time.sleep(0.01)
    GPIO.output(GPIO_RESET, GPIO.HIGH)
    time.sleep(0.01)

    # Put the module in FSK mode
    # GA: 0x02: 00000010 > 010 FS mode TX, 0 high frequency, 0 res, modulation 00 FSK, mode  0 FSK. Questo prepara il trasmettitore a sintonizzare la frequenza senza trasmettere.
    spi_write_register(REG_OP_MODE, 0x02)  # Standby mode, FSK/OOK mode
    time.sleep(0.01)
    
    # Set frequency
    # GA: ok
    frf_msb, frf_mid, frf_lsb = calculate_frf(FREQ)
    spi_write_register(REG_FRF_MSB, frf_msb)
    spi_write_register(REG_FRF_MID, frf_mid)
    spi_write_register(REG_FRF_LSB, frf_lsb)
    
    # Set bitrate
    # GA: già calcolato prima, solo scrittura
    br_msb, br_lsb = calculate_bitrate(BITRATE)
    spi_write_register(REG_BITRATE_MSB, br_msb)
    spi_write_register(REG_BITRATE_LSB, br_lsb)
    
    # Set FSK deviation
    # GA: uh uh
    fdev_msb, fdev_lsb = calculate_fdev(FDEV)
    spi_write_register(REG_FDEV_MSB, fdev_msb)
    spi_write_register(REG_FDEV_LSB, fdev_lsb)



def ping_module():
    """Read a known register to verify SPI communication with SX1276."""
    WHO_AM_I_REG = 0x42  # RegVersion in SX1276
    try:
        version = spi.xfer2([WHO_AM_I_REG & 0x7F, 0x00])[1]
        if version in (0x12, 0x11, 0x10):  # valid SX127x IDs
            print(f"SX1276 detected. RegVersion = 0x{version:02X}")
            return True
        else:
            print(f"No valid response. RegVersion = 0x{version:02X}")
            return False
    except Exception as e:
        print(f"SPI communication failed: {e}")
        return False


def radio_transmit_data(data):
    
    
    
    
    
    
    
    # Go to standby mode
    # GA: di nuovo??
    spi_write_register(REG_OP_MODE, 0x02) # Standby, FSK/OOK
    
    # GA: meglio fare un altra funzione per la creazione del pacchetto
    # PACKET ==================================================
    preamble = [0xAA] * PREAMBLE_SIZE
    access_code = ACCESS_CODE
    payload_length = [len(data)]
    payload = list(data)
    
    packet = preamble + access_code + payload_length + payload
    print(f"Packet to transmit (hex): {[hex(b) for b in packet]}")
    # PACKET ==================================================

    # Write the full packet to the FIFO
    # GA: packet length serve per capire dove deve essere posizionato il pointer dentro la ram FIFO. La scrittura del pacchetto invece di farla byte per byte nel fifo la farei tutta in uno e manderei un RegFifoAddrPtr a RegFifoTxBaseAddr.
    spi_write_register(REG_PAYLOAD_LENGTH, len(packet))
    for byte in packet:
        spi_write_register(REG_FIFO, byte)
    
    # Go to transmit mode
    # GA: finalmente sto pacchetto parte ahaha. dopo la trasmissione però bisongna riportare a 0 il Pointer.
    spi_write_register(REG_OP_MODE, 0x03) # Transmit, FSK/OOK

    print(f"Transmitting packet with payload: '{data.decode()}'...")

    # Wait for transmission to finish
    time.sleep(0.1) 
    
    print("Transmission complete.")

# =======================================================================
# Here how the TX chain should be:
# set the FIFO TX base address after every tx (0x80 is the start of the FIFO buffer for TX mode)
#   spi_write_register(0x0E | 0x80, 0x80)
# move the pointer to the start of the buffer
#   spi_write_register(0x0D | 0x80, 0x80)
# write the new payload length
#   spi_write_register(0xA2, len(packet))
# tx (00000011) where 011 is TX, so 0x03
#   spi_write_register(0x81, 0x03)

if __name__ == "__main__":
    spi = spidev.SpiDev()
    try:
        # Open SPI bus
        spi.open(SPI_BUS, SPI_DEVICE)
        spi.max_speed_hz = 1000000 # 1 MHz

        if not ping_module():
            raise RuntimeError("SX1276 not responding on SPI")

        # Configure the SX1276 module
        setup_sx1276()
        
        # MESSAGE TO TRANSMIT
        message = "Almeno COMMS funziona"  #Example message, to be removed
        data_to_transmit = message.encode('utf-8')  
        
        radio_transmit_data(data_to_transmit)    #Use this function to transmit data in main code

    except Exception as e:
        print(f"An error occurred: I can't open SPI BUS: Error ---> {e}")
    finally:
        spi.close()
        GPIO.cleanup()
        print("Cleanup complete.")
