"""
SnowRunner Time Lock (single player / offline use only)

Locks the in-game time of day. Run it, load into a map, then:
  1. Pause the game (Esc).
  2. Choose "1", type the time the game currently shows, then the time
     you want the game to stay at.

How it stays safe: the clock's address changes every launch, so config.json
holds pointer paths. Those paths can land on unrelated memory, so the tool
only accepts an address whose value matches the time you typed, and while
locked it only writes to a float that already holds roughly your target.
If that stops being true (for example after a map change) it unlocks itself.
"""
import json
import os
import sys
import threading
import time
import traceback

import pymem
import pymem.process
from pymem.exception import ProcessNotFound

DEFAULT = {
    "process": "SnowRunner.exe",
    "module": "pros.sdk.x64.dll",
    "write_interval_ms": 50,
    "paths": [
        {"base_offset": 0xA7C788, "offsets": [0x8, 0x8, 0x20, 0x150]},
        {"base_offset": 0xA7C780, "offsets": [0x58, 0x8, 0x20, 0x150]},
        {"base_offset": 0xA7DC80, "offsets": [0x8, 0x8, 0x50, 0x150]},
        {"base_offset": 0xA7DC70, "offsets": [0x98, 0x8, 0x50, 0x150]},
        {"base_offset": 0xA7DC60, "offsets": [0x128, 0x8, 0x50, 0x150]},
    ],
}
MATCH_TOLERANCE = 0.04   # hours (about 2.4 game minutes) when confirming
DRIFT_TOLERANCE = 0.25   # hours; while locked, never write if further off


def app_dir():
    """Folder of the exe (when packaged) or of this script."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


CONFIG = os.path.join(app_dir(), "config.json")


def load_config():
    if not os.path.exists(CONFIG):
        with open(CONFIG, "w") as f:
            json.dump(DEFAULT, f, indent=2)
        return json.loads(json.dumps(DEFAULT))
    with open(CONFIG) as f:
        cfg = json.load(f)
    cfg.setdefault("write_interval_ms", 50)
    return cfg


def attach(cfg):
    """Wait for the game, then return (Pymem, module_base) or (None, None)."""
    announced = False
    module_waits = 0
    while True:
        try:
            pm = pymem.Pymem(cfg["process"])
        except ProcessNotFound:
            if not announced:
                print("Waiting for SnowRunner to start (close this window to cancel)...")
                announced = True
            time.sleep(2)
            continue
        except Exception as e:
            print(f"Could not attach to the game: {e}")
            print("Try running this as Administrator.")
            return None, None
        module = pymem.process.module_from_name(pm.process_handle, cfg["module"])
        if module is not None:
            return pm, module.lpBaseOfDll
        module_waits += 1
        if module_waits > 30:
            print(f"The game is running but {cfg['module']} was not found.")
            print("This tool may not support your game version.")
            return None, None
        time.sleep(2)


def walk(pm, module_base, path):
    try:
        addr = module_base + path["base_offset"]
        for off in path["offsets"]:
            ptr = pm.read_longlong(addr)
            if ptr == 0:
                return None
            addr = ptr + off
        return addr
    except Exception:
        return None


def walk_debug(pm, module_base, path):
    addr = module_base + path["base_offset"]
    lines = [f"    start: module+{path['base_offset']:X} = {addr:X}"]
    for n, off in enumerate(path["offsets"], 1):
        try:
            ptr = pm.read_longlong(addr)
        except Exception as e:
            lines.append(f"    step {n}: read at {addr:X} FAILED ({e})")
            return lines
        lines.append(f"    step {n}: read at {addr:X} -> {ptr:X}")
        if ptr == 0:
            lines.append("    null pointer")
            return lines
        addr = ptr + off
    lines.append(f"    final address {addr:X}")
    return lines


def resolve_all(pm, module_base, cfg):
    out = []
    for i, path in enumerate(cfg["paths"]):
        addr = walk(pm, module_base, path)
        value = None
        if addr is not None:
            try:
                value = pm.read_float(addr)
            except Exception:
                value = None
        out.append((i, addr, value))
    return out


def verify_clock(pm, module_base, cfg, shown, wait=10.0):
    """Poll the paths for up to `wait` seconds until one lands on a float
    matching the time the game is showing. Returns (address, path indexes)."""
    deadline = time.time() + wait
    while time.time() < deadline:
        found = {}
        for i, addr, value in resolve_all(pm, module_base, cfg):
            if addr is not None and value is not None and abs(value - shown) <= MATCH_TOLERANCE:
                found.setdefault(addr, []).append(i)
        if found:
            addr = max(found, key=lambda a: len(found[a]))
            return addr, found[addr]
        time.sleep(0.02)
    return None, []


def parse_time(text):
    text = text.strip()
    if ":" in text:
        h, m = text.split(":")
        hours = int(h) + int(m) / 60.0
    else:
        hours = float(text)
    if not 0.0 <= hours < 24.0:
        raise ValueError("time must be between 00:00 and 23:59")
    return hours


def fmt_time(hours):
    minutes = int(round(hours * 60)) % (24 * 60)
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def main():
    cfg = load_config()
    pm, module_base = attach(cfg)
    if pm is None:
        return

    st = {"hours": None, "addr": None, "lock": False, "lost": False}
    stop = threading.Event()

    def worker():
        while not stop.is_set():
            if st["lock"] and st["addr"] is not None:
                try:
                    v = pm.read_float(st["addr"])
                    if abs(v - st["hours"]) <= DRIFT_TOLERANCE:
                        pm.write_float(st["addr"], float(st["hours"]))
                    else:
                        st["lock"] = False
                        st["lost"] = True
                except Exception:
                    st["lock"] = False
                    st["lost"] = True
            time.sleep(cfg["write_interval_ms"] / 1000.0)

    threading.Thread(target=worker, daemon=True).start()

    while True:
        if st["lost"]:
            print("\nLost the clock (map change?). Unlocked. Use option 1 to lock again.")
            st["lost"] = False
        state = "LOCKED" if st["lock"] else "unlocked"
        target = "--" if st["hours"] is None else fmt_time(st["hours"])
        print(f"\n[{state}] target time: {target}")
        print("1) Lock time   2) Unlock   3) Diagnose   4) Quit")
        choice = input("> ").strip()
        if choice == "1":
            print("Pause the game first (Esc) so the clock stands still.")
            try:
                shown = parse_time(input("Time the game shows right now (HH:MM): "))
                target_h = parse_time(input("Time to lock at (HH:MM): "))
            except ValueError as e:
                print("Invalid time:", e)
                continue
            print("Looking for the clock...")
            addr, _ = verify_clock(pm, module_base, cfg, shown)
            if addr is None:
                print("Could not find the clock, so nothing was changed.")
                print("Check the time you typed, then try again.")
                continue
            try:
                pm.write_float(addr, float(target_h))
            except Exception as e:
                print("Write failed:", e)
                continue
            st.update(hours=target_h, addr=addr, lock=True, lost=False)
            print(f"Locked at {fmt_time(target_h)}.")
        elif choice == "2":
            st["lock"] = False
        elif choice == "3":
            print(f"{cfg['module']} base = {module_base:X}")
            for i, addr, value in resolve_all(pm, module_base, cfg):
                if addr is None:
                    print(f"path {i + 1}: could not resolve")
                    for line in walk_debug(pm, module_base, cfg["paths"][i]):
                        print(line)
                else:
                    v = "unreadable" if value is None else f"{value:.4f}"
                    print(f"path {i + 1}: address {addr:X}  value {v}")
        elif choice == "4":
            stop.set()
            break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception:
        traceback.print_exc()
        input("\nSomething went wrong. Press Enter to close...")
