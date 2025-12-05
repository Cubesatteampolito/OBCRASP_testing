#!/usr/bin/env python3
"""
Quick GNSS bring-up:
  1) Scan I2C bus for the MCP23017 (I/O expander used for GNSS control lines)
  2) Read a single NMEA sentence from the NEO-M9N over SPI

This does NOT configure the receiver yet, it just proves that:
  - the PC104 → COMMSYS path is alive
  - the GNSS is running and talking
"""

import time
from smbus2 import SMBus
import spidevgit 
import sys

# ---------- I2C / MCP23017 ----------

I2C_BUS_NUM = 1               # /dev/i2c-1 on Raspberry Pi
MCP_ADDR_RANGE = range(0x20, 0x28)  # valid MCP23017 addresses (A2..A0)
MCP_ADDR_GUESS = 0x20              # expected if A2..A0 are all tied low

def scan_for_mcp(bus_num=I2C_BUS_NUM):
    print(f"[I2C] Scanning bus {bus_num} for MCP23017...")

    found = []
    with SMBus(bus_num) as bus:
        for addr in MCP_ADDR_RANGE:
            try:
                # Any simple read will do; MCP23017 ACKs the address.
                bus.read_byte(addr)
                found.append(addr)
            except OSError:
                pass

    if not found:
        print("  -> No MCP23017 found in 0x20–0x27. Check SDA/SCL, power, and address pins.")
    else:
        print("  -> Detected devices:")
        for a in found:
            mark = " (expected)" if a == MCP_ADDR_GUESS else ""
            print(f"     - 0x{a:02X}{mark}")

    return found

def simple_mcp_readback(addr=MCP_ADDR_GUESS, bus_num=I2C_BUS_NUM):
    """
    Not a true 'ID' (MCP23017 has no ID register), but proves we can
    read its registers. We dump the two IODIR registers.
    """
    IODIRA = 0x00
    IODIRB = 0x01

    with SMBus(bus_num) as bus:
        try:
            iodira = bus.read_byte_data(addr, IODIRA)
            iodirb = bus.read_byte_data(addr, IODIRB)
        except OSError as e:
            print(f"[I2C] Failed to talk to MCP23017 at 0x{addr:02X}: {e}")
            return

    print(f"[I2C] MCP23017 @ 0x{addr:02X} IODIRA=0x{iodira:02X}, IODIRB=0x{iodirb:02X}")
    print("      (Default after reset is 0xFF/0xFF = all pins inputs; "
          "if you see something else, something has already configured it.)")


# ---------- SPI / NEO-M9N ----------

SPI_BUS = 0      # /dev/spidev0.*
SPI_DEV = 0      # CE0 → check against your COMMSYS routing
SPI_SPEED_HZ = 1_000_000  # 1 MHz; NEO-M9N SPI supports this comfortably

def open_spi(bus=SPI_BUS, dev=SPI_DEV, speed=SPI_SPEED_HZ):
    spi = spidev.SpiDev()
    spi.open(bus, dev)
    spi.max_speed_hz = speed
    spi.mode = 0          # CPOL=0, CPHA=0 is what u-blox expects
    spi.bits_per_word = 8
    return spi

def read_one_nmea_sentence(timeout_s=5.0):
    """
    Clock the NEO-M9N SPI and extract the first clean NMEA line.
    We just send dummy 0x00 bytes; the receiver will return either 0xFF
    (idle) or actual ASCII ($GNGGA, $GNRMC, ...).
    """
    print(f"[SPI] Trying to read one NMEA sentence from NEO-M9N "
          f"on /dev/spidev{SPI_BUS}.{SPI_DEV}...")

    try:
        spi = open_spi()
    except FileNotFoundError:
        print("  -> SPI device not found. Enable SPI in raspi-config and check the bus/device.")
        return None
    except PermissionError:
        print("  -> Permission error opening SPI. Run with sudo or fix /dev/spidev* permissions.")
        return None

    buffer = bytearray()
    start = time.time()

    try:
        while time.time() - start < timeout_s:
            # Clock, say, 64 bytes per iteration.
            rx = spi.xfer2([0x00] * 64)
            buffer.extend(rx)

            # Process complete lines
            while b"\n" in buffer:
                line, _, remainder = buffer.partition(b"\n")
                buffer = bytearray(remainder)

                # Strip leading idle 0xFF and junk before '$'
                # (SPI idle from u-blox is typically 0xFF bytes)
                if b"$" not in line:
                    continue
                line = line[line.find(b"$"):]
                try:
                    text = line.decode("ascii", errors="ignore").strip()
                except UnicodeDecodeError:
                    continue

                if not text:
                    continue

                print(f"[SPI] First NMEA sentence from receiver:")
                print(f"      {text}")
                print("      (If this starts with $GNGGA / $GNRMC / $GNTXT etc, "
                      "your GNSS link is alive.)")
                return text

            # Small delay so we’re not hammering the CPU needlessly
            time.sleep(0.01)

        print("[SPI] Timeout: no valid NMEA sentence seen. "
              "Check CS/SCK/MOSI/MISO wiring and that D_SEL really selects SPI.")
        return None

    finally:
        spi.close()


# ---------- main ----------

def main():
    print("=== GNSS bring-up test (MCP23017 + NEO-M9N) ===\n")

    # 1) Ping the I2C lines and confirm the MCP23017 is present
    found = scan_for_mcp()
    if MCP_ADDR_GUESS in found:
        simple_mcp_readback(MCP_ADDR_GUESS)
    elif found:
        # Pick first device as "the" MCP if address straps differ
        simple_mcp_readback(found[0])

    print("\n---\n")

    # 2) Try to read the GNSS ID / first sentence via SPI
    nmea = read_one_nmea_sentence(timeout_s=5.0)

    if nmea is None:
        sys.exit(1)
    else:
        # Optional: very rough "ID" extraction
        if nmea.startswith("$GNTXT"):
            print("\n[INFO] That TXT sentence often carries version/build info – "
                  "you can treat that as a basic 'ID'.")
        else:
            print("\n[INFO] You are at least seeing valid NMEA from the NEO-M9N. "
                  "Next step is to parse these or switch to UBX messages.")


if __name__ == "__main__":
    main()
