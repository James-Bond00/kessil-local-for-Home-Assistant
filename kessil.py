#!/usr/bin/env python3
"""kessil.py - local control of Kessil lights through the Kessil WiFi dongle.

Unofficial. Not affiliated with, endorsed or supported by Kessil.
The dongle speaks plain JSON over TCP port 8888 in your own network,
no cloud and no password. See docs/protocol.md for the details.

Tested with: Kessil WiFi dongle (FW 1.5.13) and two A360X Tuna Sun
(FW 1.3 and 1.5) in one group.

Host, port, group and program can be set by option or environment:
  --host  / KESSIL_HOST    IP of the dongle (required)
  --port  / KESSIL_PORT    default 8888
  --group / KESSIL_GROUP   group id (GID), default 2
  --pid   / KESSIL_PID     program id for program-read/-write, default 1
  --type  / KESSIL_TYPE    lamp type for program-read/-write, default 2 (Tuna Sun)

Commands (output is always one line of JSON, exit code 0 = success):
  info                         device info (dtype 114)
  lamps                        lamp list (dtype 5)
  status                       group status (dtype 102)
  on                           back on with the stored values
  off                          off
  manual INT CLR RED AMBER     manual mode: INT/CLR 0-255, RED/AMBER 0-100
  effect NAME [--speed S] [--seconds N]
                               NAME: storm, cloud, aurora (or 0-9)
                               S: fast, medium, slow; N: 30-300
  effect-off                   end the effect, back to the stored values
  program PID                  run program PID (-1 = no program)
  program-read                 read the daily program (dtype 106)
  program-write "M:INT,CLR,RED,AMBER;..."
                               write the complete daily program (dtype 107),
                               activate it and verify by reading it back.
                               M = minutes after midnight, ascending,
                               the last point is the "off" point.
  raw DTYPE [JSON]             send any dtype with a JSON data object
"""
import argparse
import json
import os
import socket
import sys
import time

TIMEOUT = 4.0
EFFECTS = {"storm": 0, "cloud": 1, "aurora": 3}
SPEEDS = {"fast": 0, "medium": 1, "slow": 2}
MINUTE_KEYS = ("minutes", "m", "M", "min", "minute", "time", "t")
UI_KEYS = ("UI", "ui")


class Dongle:
    def __init__(self, host, port, group):
        self.host = host
        self.port = port
        self.group = group

    def send(self, dtype, data):
        message = json.dumps({"data": data, "dtype": dtype}, separators=(",", ":"))
        with socket.create_connection((self.host, self.port), timeout=TIMEOUT) as s:
            s.sendall(message.encode())
            buffer = b""
            while True:
                try:
                    part = s.recv(4096)
                except socket.timeout:
                    break
                if not part:
                    break
                buffer += part
                try:
                    return json.loads(buffer.decode("utf-8", "replace"))
                except ValueError:
                    continue  # answer not complete yet
        if not buffer:
            raise RuntimeError("no answer from the dongle")
        return json.loads(buffer.decode("utf-8", "replace"))

    # --- building blocks -------------------------------------------------
    def status(self):
        return self.send(102, {"GID": self.group}).get("group", {})

    def values(self, ui1, ui2, ui4, ui5, save):
        return self.send(3, {"GID": self.group, "UI1": ui1, "UI2": ui2, "UI3": 0,
                             "UI4": ui4, "UI5": ui5, "save": save})

    def pause(self, value):
        return self.send(113, {"GID": self.group, "pause": value})

    def assign_program(self, pid):
        return self.send(100, {"GID": self.group, "PID": pid})

    def end_effect(self, group_status):
        if group_status.get("eid", -1) != -1:
            self.send(101, {"GID": self.group, "EID": -1, "FREQ": 1, "duration": 30})

    # --- the sequences the Kessil app uses --------------------------------
    def on(self):
        g = self.status()
        self.end_effect(g)
        ui = g.get("UI", [255, 255, 0, 100, 100])
        self.pause(0)
        return self.values(ui[0], ui[1], ui[3], ui[4], 0)

    def off(self):
        g = self.status()
        self.end_effect(g)
        self.pause(1)
        return self.values(0, 0, 0, 0, 0)

    def manual(self, ui1, ui2, ui4, ui5):
        g = self.status()
        self.end_effect(g)
        if g.get("pid", -1) != -1:
            self.assign_program(-1)
        self.pause(0)
        return self.values(ui1, ui2, ui4, ui5, 1)

    def effect(self, number, speed, seconds):
        self.pause(1)
        return self.send(101, {"GID": self.group, "EID": speed * 100 + number,
                               "FREQ": speed, "duration": seconds})

    def effect_off(self):
        return self.on()

    def program(self, pid):
        g = self.status()
        self.end_effect(g)
        self.assign_program(pid)
        return self.pause(0)

    # --- daily program ----------------------------------------------------
    def program_raw(self, pid, lamp_type):
        return self.send(106, {"PID": pid, "type": lamp_type})

    def program_write(self, pid, lamp_type, points):
        old = self.program_raw(pid, lamp_type)
        name = (old.get("program") or {}).get("name") or "Program %d" % pid
        payload = []
        for nr, p in enumerate(points):
            last = nr == len(points) - 1
            payload.append({"UI": p["UI"], "d": 0 if last else 30, "EID": -1, "f": 1, "m": p["m"]})
        answer = self.send(107, {"PID": pid, "type": lamp_type, "name": name, "points": payload})
        if answer.get("code", 1) != 0:
            return {"code": 1, "msg": "write rejected", "answer": answer}
        g = self.status()
        self.end_effect(g)
        self.pause(0)
        self.assign_program(pid)
        time.sleep(1)
        raw = self.program_raw(pid, lamp_type)
        read_back = parse_program(raw)
        wanted = [(p["m"], list(p["UI"])) for p in payload]
        if read_back is None:
            return {"code": 1, "verified": False, "msg": "written, read-back not understood", "raw": raw}
        same = wanted == read_back
        return {"code": 0 if same else 1, "verified": same, "points": len(payload), "name": name,
                "msg": "program written and verified" if same else "read-back differs",
                "read_back": None if same else read_back}


def clamp(value, low, high):
    return max(low, min(high, int(round(float(value)))))


def find_points(obj):
    if isinstance(obj, dict):
        if isinstance(obj.get("points"), list):
            return obj["points"]
        for value in obj.values():
            found = find_points(value)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for value in obj:
            found = find_points(value)
            if found is not None:
                return found
    return None


def parse_point(p):
    if not isinstance(p, dict):
        return None
    m = next((p[k] for k in MINUTE_KEYS if k in p), None)
    ui = next((p[k] for k in UI_KEYS if k in p), None)
    if m is None or not isinstance(ui, list) or len(ui) < 5:
        return None
    return int(m), [int(x) for x in ui[:5]]


def parse_program(raw):
    """Answer of dtype 106 -> [(minutes, [INT, CLR, 0, RED, AMBER]), ...] or None."""
    points = find_points(raw)
    if not points:
        return None
    parsed = [parse_point(p) for p in points]
    if any(p is None for p in parsed):
        return None
    return parsed


def program_text(points):
    return ";".join("%d:%d,%d,%d,%d" % (m, ui[0], ui[1], ui[3], ui[4]) for m, ui in points)


def parse_program_text(text):
    points = []
    for part in text.strip().strip(";").split(";"):
        m, _, w = part.partition(":")
        i, c, r, a = [int(x) for x in w.split(",")]
        points.append({"m": clamp(m, 0, 1439),
                       "UI": [clamp(i, 0, 255), clamp(c, 0, 255), 0, clamp(r, 0, 100), clamp(a, 0, 100)]})
    if len(points) < 2:
        raise ValueError("at least 2 points needed")
    for before, after in zip(points, points[1:]):
        if after["m"] <= before["m"]:
            raise ValueError("times must be ascending")
    return points


def build_parser():
    env = os.environ.get
    p = argparse.ArgumentParser(description="Local control of Kessil lights via the WiFi dongle (unofficial).")
    p.add_argument("--host", default=env("KESSIL_HOST"), help="IP of the dongle (or KESSIL_HOST)")
    p.add_argument("--port", type=int, default=int(env("KESSIL_PORT", "8888")))
    p.add_argument("--group", type=int, default=int(env("KESSIL_GROUP", "2")), help="group id GID")
    p.add_argument("--pid", type=int, default=int(env("KESSIL_PID", "1")), help="program id")
    p.add_argument("--type", dest="lamp_type", type=int, default=int(env("KESSIL_TYPE", "2")),
                   help="lamp type for programs (2 = Tuna Sun)")
    sub = p.add_subparsers(dest="command", required=True)
    for name in ("info", "lamps", "status", "on", "off", "effect-off", "program-read"):
        sub.add_parser(name)
    m = sub.add_parser("manual")
    for field in ("int", "clr", "red", "amber"):
        m.add_argument(field, type=float)
    e = sub.add_parser("effect")
    e.add_argument("name")
    e.add_argument("--speed", choices=SPEEDS, default="medium")
    e.add_argument("--seconds", type=int, default=60)
    pr = sub.add_parser("program")
    pr.add_argument("pid", type=int)
    pw = sub.add_parser("program-write")
    pw.add_argument("points")
    r = sub.add_parser("raw")
    r.add_argument("dtype", type=int)
    r.add_argument("data", nargs="?", default="{}")
    return p


def run(args):
    if not args.host:
        raise ValueError("no host: use --host or KESSIL_HOST")
    d = Dongle(args.host, args.port, args.group)
    c = args.command
    if c == "info":
        return d.send(114, {})
    if c == "lamps":
        return d.send(5, {})
    if c == "status":
        return d.send(102, {"GID": args.group})
    if c == "on":
        return d.on()
    if c == "off":
        return d.off()
    if c == "manual":
        return d.manual(clamp(args.int, 0, 255), clamp(args.clr, 0, 255),
                        clamp(args.red, 0, 100), clamp(args.amber, 0, 100))
    if c == "effect":
        number = EFFECTS.get(args.name.lower())
        if number is None:
            number = clamp(args.name, 0, 9)
        return d.effect(number, SPEEDS[args.speed], clamp(args.seconds, 30, 300))
    if c == "effect-off":
        return d.effect_off()
    if c == "program":
        return d.program(args.pid)
    if c == "program-read":
        raw = d.program_raw(args.pid, args.lamp_type)
        points = parse_program(raw)
        if points is None:
            return {"code": 1, "msg": "answer not understood", "raw": raw}
        return {"code": 0, "points": len(points), "text": program_text(points), "raw": raw}
    if c == "program-write":
        return d.program_write(args.pid, args.lamp_type, parse_program_text(args.points))
    if c == "raw":
        return d.send(args.dtype, json.loads(args.data))
    raise ValueError("unknown command")


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        answer = run(args)
    except Exception as error:  # noqa: BLE001
        answer = {"code": -1, "msg": str(error)}
    print(json.dumps(answer, separators=(",", ":")))
    return 0 if answer.get("code", 1) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
