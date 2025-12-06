#!/usr/bin/env python3

import time
from datetime import datetime
from pathlib import Path  # <-- added

import spidev  # install with: sudo apt-get install python3-spidev  (or pip3 install spidev)

SPI_BUS = 0
SPI_DEV = 0
SPI_SPEED_HZ = 1_000_000  # 1 MHz


def open_spi(bus=SPI_BUS, dev=SPI_DEV, speed=SPI_SPEED_HZ):
    spi = spidev.SpiDev()
    spi.open(bus, dev)
    spi.max_speed_hz = speed
    spi.mode = 0  # CPOL=0, CPHA=0
    spi.bits_per_word = 8
    return spi


def nmea_strip_checksum(sentence: str) -> str:
    """Remove '*hh' checksum from an NMEA sentence."""
    if "*" in sentence:
        sentence = sentence.split("*", 1)[0]
    return sentence


def parse_coord(coord: str, direction: str, is_lat: bool = True):
    """
    Convert NMEA ddmm.mmmm (lat) / dddmm.mmmm (lon) + N/E/S/W into signed degrees.
    """
    if not coord or not direction:
        return None
    deg_len = 2 if is_lat else 3
    try:
        deg = float(coord[:deg_len])
        minutes = float(coord[deg_len:])
        val = deg + minutes / 60.0
        if direction in ("S", "W"):
            val = -val
        return val
    except ValueError:
        return None


def parse_datetime_utc(date_str: str, time_str: str):
    """
    Convert NMEA date (ddmmyy) + time (hhmmss.ss) to a Python datetime in UTC.
    """
    if not time_str:
        return None
    try:
        hour = int(time_str[0:2])
        minute = int(time_str[2:4])
        sec_float = float(time_str[4:])
        sec = int(sec_float)
        micro = int(round((sec_float - sec) * 1e6))
    except (ValueError, IndexError):
        return None

    if date_str and len(date_str) == 6:
        try:
            day = int(date_str[0:2])
            month = int(date_str[2:4])
            year = 2000 + int(date_str[4:6])
        except ValueError:
            now = datetime.utcnow()
            year, month, day = now.year, now.month, now.day
    else:
        now = datetime.utcnow()
        year, month, day = now.year, now.month, now.day

    return datetime(year, month, day, hour, minute, sec, micro)


def parse_rmc(sentence: str):
    """
    Parse an RMC sentence: position, speed, course, time, status.
    """
    s = nmea_strip_checksum(sentence)
    fields = s.split(",")
    if len(fields) < 10:
        return None

    time_str = fields[1]
    status = fields[2] or None
    lat_str = fields[3]
    lat_dir = fields[4]
    lon_str = fields[5]
    lon_dir = fields[6]
    speed_knots = fields[7]
    course_deg = fields[8]
    date_str = fields[9]

    utc_dt = parse_datetime_utc(date_str, time_str) if time_str else None
    lat = parse_coord(lat_str, lat_dir, is_lat=True)
    lon = parse_coord(lon_str, lon_dir, is_lat=False)

    try:
        speed = float(speed_knots) if speed_knots else None
    except ValueError:
        speed = None

    try:
        course = float(course_deg) if course_deg else None
    except ValueError:
        course = None

    return {
        "utc": utc_dt,
        "status": status,
        "lat": lat,
        "lon": lon,
        "speed_knots": speed,
        "course_deg": course,
    }


def parse_gga(sentence: str):
    """
    Parse a GGA sentence: position, altitude, fix quality, sats, HDOP.
    """
    s = nmea_strip_checksum(sentence)
    fields = s.split(",")
    if len(fields) < 10:
        return None

    time_str = fields[1]
    lat_str = fields[2]
    lat_dir = fields[3]
    lon_str = fields[4]
    lon_dir = fields[5]
    fix_quality = fields[6]
    num_sats = fields[7]
    hdop = fields[8]
    altitude = fields[9]

    lat = parse_coord(lat_str, lat_dir, is_lat=True)
    lon = parse_coord(lon_str, lon_dir, is_lat=False)

    try:
        fix_q = int(fix_quality) if fix_quality else 0
    except ValueError:
        fix_q = 0

    try:
        sats = int(num_sats) if num_sats else None
    except ValueError:
        sats = None

    try:
        hdop_val = float(hdop) if hdop else None
    except ValueError:
        hdop_val = None

    try:
        alt_m = float(altitude) if altitude else None
    except ValueError:
        alt_m = None

    return {
        "time_str": time_str or None,
        "lat": lat,
        "lon": lon,
        "fix_quality": fix_q,
        "num_sats": sats,
        "hdop": hdop_val,
        "alt_m": alt_m,
    }


def read_nmea_sentences(spi, chunk_size=128):
    """
    Generator yielding clean ASCII NMEA sentences from the NEO-M9N via SPI.
    """
    buffer = bytearray()
    while True:
        # clock out some bytes; we ignore returned 0xFF "idle" bytes
        rx = spi.xfer2([0x00] * chunk_size)
        buffer.extend(rx)

        # split into lines
        while b"\n" in buffer:
            line, _, buffer = buffer.partition(b"\n")

            if b"$" not in line:
                continue

            # keep only from '$'
            line = line[line.find(b"$") :]

            try:
                text = line.decode("ascii", errors="ignore").strip()
            except UnicodeDecodeError:
                continue

            if not text or not text.startswith("$"):
                continue

            yield text

        time.sleep(0.01)


def main():
    print("=== GNSS NEO-M9N continuous reader (SPI + NMEA) ===")
    try:
        spi = open_spi()
    except Exception as e:
        print(f"Failed to open SPI device /dev/spidev{SPI_BUS}.{SPI_DEV}: {e}")
        return

    # Latest nav solution assembled from RMC + GGA
    fix_state = {
        "utc": None,
        "lat": None,
        "lon": None,
        "alt_m": None,
        "speed_knots": None,
        "course_deg": None,
        "num_sats": None,
        "hdop": None,
        "fix_ok": False,
    }

    last_print = 0.0

    # --- logging setup: two files in same folder as this script (overwrite each run) ---
    script_dir = Path(__file__).resolve().parent
    raw_log_path = script_dir / "gnss_raw.log"
    parsed_log_path = script_dir / "gnss_output.log"

    try:
        with raw_log_path.open("w", encoding="utf-8") as raw_log, \
             parsed_log_path.open("w", encoding="utf-8") as parsed_log:

            try:
                for sentence in read_nmea_sentences(spi):
                    # Log raw NMEA with timestamp
                    ts_raw = datetime.utcnow().isoformat()
                    raw_log.write(f"{ts_raw} {sentence}\n")

                    if len(sentence) < 6:
                        continue

                    msg_type = sentence[3:6]  # 'RMC', 'GGA', ...

                    if msg_type == "RMC":
                        rmc = parse_rmc(sentence)
                        if rmc:
                            if rmc["utc"]:
                                fix_state["utc"] = rmc["utc"]
                            if rmc["lat"] is not None:
                                fix_state["lat"] = rmc["lat"]
                            if rmc["lon"] is not None:
                                fix_state["lon"] = rmc["lon"]
                            fix_state["speed_knots"] = rmc["speed_knots"]
                            fix_state["course_deg"] = rmc["course_deg"]
                            # 'A' = valid, 'V' = void
                            fix_state["fix_ok"] = rmc["status"] == "A"

                    elif msg_type == "GGA":
                        gga = parse_gga(sentence)
                        if gga:
                            if gga["lat"] is not None:
                                fix_state["lat"] = gga["lat"]
                            if gga["lon"] is not None:
                                fix_state["lon"] = gga["lon"]
                            fix_state["alt_m"] = gga["alt_m"]
                            fix_state["num_sats"] = gga["num_sats"]
                            fix_state["hdop"] = gga["hdop"]
                            if gga["fix_quality"] == 0:
                                fix_state["fix_ok"] = False

                    # print at ~1 Hz
                    now = time.time()
                    if now - last_print >= 1.0:
                        last_print = now

                        utc_str = (
                            fix_state["utc"].isoformat()
                            if isinstance(fix_state["utc"], datetime)
                            else "unknown"
                        )
                        lat = fix_state["lat"]
                        lon = fix_state["lon"]
                        lat_str = f"{lat:.6f}" if isinstance(lat, (int, float)) else "NA"
                        lon_str = f"{lon:.6f}" if isinstance(lon, (int, float)) else "NA"

                        sats_str = (
                            str(fix_state["num_sats"])
                            if isinstance(fix_state["num_sats"], int)
                            else "NA"
                        )
                        hdop_str = (
                            f"{fix_state['hdop']:.1f}"
                            if isinstance(fix_state["hdop"], (int, float))
                            else "NA"
                        )
                        alt_str = (
                            f"{fix_state['alt_m']:.1f}"
                            if isinstance(fix_state["alt_m"], (int, float))
                            else "NA"
                        )

                        if fix_state["fix_ok"]:
                            speed_kn = fix_state["speed_knots"]
                            speed_mps = (
                                speed_kn * 0.514444
                                if isinstance(speed_kn, (int, float))
                                else None
                            )
                            speed_kn_str = (
                                f"{speed_kn:.2f}"
                                if isinstance(speed_kn, (int, float))
                                else "NA"
                            )
                            speed_mps_str = (
                                f"{speed_mps:.2f}"
                                if isinstance(speed_mps, (int, float))
                                else "NA"
                            )
                            course = fix_state["course_deg"]
                            course_str = (
                                f"{course:.1f}"
                                if isinstance(course, (int, float))
                                else "NA"
                            )

                            message = (
                                f"[FIX] UTC={utc_str} "
                                f"lat={lat_str} lon={lon_str} "
                                f"alt={alt_str} m sats={sats_str} HDOP={hdop_str} "
                                f"v={speed_mps_str} m/s ({speed_kn_str} kn) "
                                f"course={course_str} deg"
                            )
                        else:
                            message = (
                                f"[NO FIX] UTC={utc_str} "
                                f"lat={lat_str} lon={lon_str} "
                                f"sats={sats_str} HDOP={hdop_str}"
                            )

                        # Console output
                        print(message)

                        # Log parsed/output line with timestamp
                        ts_out = datetime.utcnow().isoformat()
                        parsed_log.write(f"{ts_out} {message}\n")

                        # Make sure data hits disk regularly
                        raw_log.flush()
                        parsed_log.flush()

            except KeyboardInterrupt:
                print("\nStopping GNSS reader.")

    finally:
        try:
            spi.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
