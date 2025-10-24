import spidev
import time

# Registers
REG_FIFO       = 0x00
REG_OPMODE     = 0x01
REG_FRFMSB     = 0x06
REG_FRFMID     = 0x07
REG_FRFLSB     = 0x08
REG_BITRATEMSB = 0x02
REG_BITRATELSB = 0x03
REG_PACKETCFG1 = 0x37
REG_PAYLOADLEN = 0x38
REG_IRQFLAGS1  = 0x27
REG_IRQFLAGS2  = 0x28
REG_VERSION    = 0x42

# Modes
MODE_SLEEP = 0x00
MODE_STDBY = 0x01
MODE_TX    = 0x03

EXPECTED_VERSION = 0x12

spi = spidev.SpiDev()

def write_reg(addr, value):
    spi.xfer2([addr | 0x80, value])

def read_reg(addr):
    return spi.xfer2([addr & 0x7F, 0x00])[1]

def set_mode(mode):
    opmode = read_reg(REG_OPMODE)
    opmode = (opmode & 0xF8) | (mode & 0x07)
    write_reg(REG_OPMODE, opmode)

def clear_irqs():
    read_reg(REG_IRQFLAGS1)
    read_reg(REG_IRQFLAGS2)

def check_chip():
    version = read_reg(REG_VERSION)
    print(f"🔎 RegVersion = 0x{version:02X}")
    return version == EXPECTED_VERSION

def setup_fsk():
    # Force FSK (clear LoRa mode bit)
    opmode = read_reg(REG_OPMODE)
    opmode &= ~(1 << 7)
    write_reg(REG_OPMODE, opmode)

    set_mode(MODE_STDBY)

    # Frequency 867 MHz
    write_reg(REG_FRFMSB, 0xD8)
    write_reg(REG_FRFMID, 0x01)
    write_reg(REG_FRFLSB, 0x3F)

    # Bitrate 9600 bps
    write_reg(REG_BITRATEMSB, 0x0D)
    write_reg(REG_BITRATELSB, 0x05)

    # Packet config: variable length, CRC on
    write_reg(REG_PACKETCFG1, 0x80)

    # Default payload length (used in fixed mode, ignored in variable)
    write_reg(REG_PAYLOADLEN, 0x40)

    clear_irqs()
    print("✅ FSK setup 867MHz / 9600bps complete")

def transmit(data: str):
    if isinstance(data, str):
        payload = data.encode("utf-8")
    else:
        payload = data

    length = len(payload)
    print(f"➡️ Sending {length} bytes")

    # Update payload length
    write_reg(REG_PAYLOADLEN, length)

    clear_irqs()

    # Write payload to FIFO
    for byte in payload:
        write_reg(REG_FIFO, byte)

    set_mode(MODE_TX)

    timeout = time.time() + 2
    while True:
        irq2 = read_reg(REG_IRQFLAGS2)
        print(f"   RegIrqFlags2 = 0x{irq2:02X}")
        if irq2 & 0x08:
            print("✅ Packet sent (PacketSent flag set)!")
            break
        if time.time() > timeout:
            print("❌ TX timeout!")
            break
        time.sleep(0.05)

    set_mode(MODE_STDBY)

def setup_spi():
    spi.open(0, 1)  # CE1
    spi.max_speed_hz = 500000
    spi.mode = 0
    print("⚡ SPI setup complete")

if __name__ == "__main__":
    setup_spi()
    if check_chip():
        print("✅ SX1276 detected")
        setup_fsk()
        transmit("Hello 867MHz FSK!")
    else:
        print("❌ SX1276 not detected")
    spi.close()