# Kessil WiFi dongle – local protocol

Unofficial notes, worked out from network captures of the Kessil app (October 2026)
and verified against real hardware. Not affiliated with Kessil. Field names are as
seen on the wire; anything marked *untested* was not tried.

Tested with: Kessil WiFi dongle FW 1.5.13, two A360X Tuna Sun (FW 1.3 and 1.5) in one group.

## Transport

- TCP, port **8888**, on the dongle's IP in your LAN.
- Plain JSON, no authentication, no cloud. The app needs WiFi only because it talks to the dongle directly.
- One request per connection works fine: connect, send one JSON object, read one JSON answer, close.
- Request: `{"data": { ... }, "dtype": N}`
- Answer: JSON with `"msg": "Success", "code": 0` on success (some answers also carry `"dType": N`).
- On a kept-open connection the app sends a single byte `0xFF` before each further command. With one connection per command this is **not** needed.
- The dongle also has SSH (Dropbear, Kessil key only) and dnsmasq on port 53. Not needed for control.

Quick test from a shell:

```sh
printf '{"data":{"GID":2},"dtype":102}' | nc -w 3 <dongle-ip> 8888
```

## Message types (dtype)

| dtype | data | purpose |
|---|---|---|
| 114 | `{}` | device info (serial, firmware, SSID, time zone, lamp list) |
| 5 | `{}` | lamp list |
| 102 | `{"GID":2}` | group status: `pid`, `eid`, `pause`, `UI[5]`, `accl`, `lunar`, `name`, `hasLamps` |
| 106 | `{"PID":1,"type":2}` | read daily program (`type` 2 = Tuna Sun) |
| 107 | see below | write daily program |
| 100 | `{"GID":2,"PID":1}` | assign program to the group (`PID -1` = no program / manual) |
| 113 | `{"GID":2,"pause":0}` | pause flag (see "sequences" – never send it alone) |
| 3 | `{"GID":2,"UI1":..,"UI2":..,"UI3":0,"UI4":..,"UI5":..,"save":0}` | set values |
| 101 | `{"GID":2,"EID":..,"FREQ":..,"duration":..}` | weather effect |

`GID` is the group id. A fresh setup with one dongle had the group "Default TS" as `GID 2`.
Use dtype 114 / 5 to see your lamps and groups.

## Values

| field | meaning | range |
|---|---|---|
| UI1 | INT – intensity | 0–255 (app shows %) |
| UI2 | CLR – color | 0–255 (app shows %; low = warmer/yellowish, high = cooler/bluish) |
| UI3 | unused | always 0 |
| UI4 | red channel | 0–100 |
| UI5 | amber channel | 0–100 |

Red and amber are separate channels and also light up at INT 0.

`save` in dtype 3: `1` = store the values (manual mode), `0` = only show them live.

## Effects (dtype 101)

- `EID = FREQ * 100 + effect`, `EID -1` = effect off
- `FREQ`: 0, 1, 2. The Kessil manual calls it *Frequency – how often the effect
  occurs during the time period*. `0` gave the most visible storm in tests
  (often), `2` = rare.
- `duration`: seconds, 30–300 (the app shows minutes)
- The manual lists six effects: Storm, Cloud, Aurora, Rainbow, Moonlight Red,
  Moonlight Blue. Tested on two A360X **Tuna Sun** (white light as base, FREQ 0, 60 s):

| effect | what you see | after `duration` |
|---|---|---|
| 0 storm | dimmed with short bright flashes | **stays in the effect** (status keeps `eid`, lamp stays dimmed) – send "run program" or "effect off" |
| 1 cloud | brightness goes up and down | returns to the state before by itself |
| 2 rainbow *(name from the manual)* | red → orange → almost off → orange → red | returns by itself |
| 3 aurora | slow pulsing | returns by itself |
| 4 moonlight red *(name from the manual)* | nothing visible | returns by itself |
| 5 moonlight blue *(name from the manual)* | nothing visible | returns by itself |

The effects modulate the white channels. In a red/amber phase of the program
you hardly see anything. Moonlight is probably meant for lamps with other
channels (e.g. Tuna Blue).

## Sequences – do it like the app

Sending single commands can leave the light in an odd state (for example `pause 1`
alone turns the light off and it seems to hang). The app always uses these pairs:

| action | sequence |
|---|---|
| off | `113 pause 1` + `3` all values 0, `save 0` |
| on | `113 pause 0` + `3` with the stored values (from `102`), `save 0` |
| manual / sliders | (`100 PID -1` if a program is running) + `113 pause 0` + `3 save 1` |
| effect | `113 pause 1` + `101` |
| effect off | `101 EID -1`, then `113 pause 0` + `3` stored values, `save 0` |
| run program | (end effect) + `100 PID 1` + `113 pause 0` |

Status from dtype 102:

- `eid != -1` → effect
- `pause == 1` → off
- `pid == -1` → manual
- otherwise → program running

## Daily program

### Read (dtype 106)

Request `{"PID":1,"type":2}`. Answer (shortened):

```json
{"msg":"Success","code":0,
 "program":{"PID":1,"order":1,"type":2,"name":"Preset Tuna Sun",
  "points":[
   {"minutes":420,"UI":[2,0,0,0,65],"eid":-1,"duration":30,"freq":1},
   {"minutes":480,"UI":[51,25,0,0,16],"eid":-1,"duration":30,"freq":1},
   {"minutes":1030,"UI":[0,0,0,0,0],"eid":-1,"duration":0,"freq":1}]},
 "dType":106}
```

`minutes` = minutes after midnight. The light fades between the points.

### Write (dtype 107)

**The field names differ from the read answer:** `m`, `d`, `EID`, `f` instead of
`minutes`, `duration`, `eid`, `freq`.

```json
{"dtype":107,"data":{"PID":1,"type":2,"name":"Preset Tuna Sun",
 "points":[
  {"UI":[2,0,0,0,65],"d":30,"EID":-1,"f":1,"m":420},
  {"UI":[51,25,0,0,16],"d":30,"EID":-1,"f":1,"m":480},
  {"UI":[0,0,0,0,0],"d":0,"EID":-1,"f":1,"m":1030}]}}
```

- Always send the **complete** program in one command, including the last "off" point.
- The app uses `d 30, EID -1, f 1` for normal points and `d 0` on the last point.
- Keep the program name from dtype 106.
- After writing, the app activates it with `113 pause 0` + `100 PID 1`.
- Read it back with dtype 106 and compare to be sure.

## Effects inside the daily program

In the app every program point has an *Effect* tab (Storm, Cloud, Aurora,
Rainbow, time, frequency). That is what `EID`, `d` and `f` in each point of
dtype 107 are for (`eid`, `duration`, `freq` when reading). With these the lamp
runs effects at given times on its own. *Not tested yet.*

## Acclimation and lunar cycle

The full group status (also returned after dtype 113) contains:

```json
"accl":  {"start":20,"period":14,"enabled":0,"startDate":0,"stopDate":0},
"lunar": {"start":1200,"end":480,"high":120,"color":0,"phase":0,"enabled":0,"startDate":0,"stopDate":0}
```

- **Acclimation** (manual): lowers the program for new corals or a new lamp.
  `start` = starting intensity in % of the program, `period` = days until 100 %.
- **Lunar cycle** (manual): 30-day moon phases with "ultra low dimming" at night;
  `start`/`end` = minutes after midnight (here 20:00–08:00), moon colour blue or
  red, starting phase, or *static*.
- How to switch them on was not captured yet.

## Pitfalls

- **One connection at a time.** If a second client connects while a command is
  running (e.g. a status poll), one of them gets no answer. Serialise your calls
  and retry. Lost effect commands are nasty: the lamp is already paused and
  stays dark – restore the previous state if `101` gets no answer.
- No hard limit on program points was found (10 written and verified; the app
  also accepted extra points).

- The Kessil app saves automatically when you go back, and editing sometimes adds
  new points (changing a value at 10:00 created an extra point at 10:05). If a script
  manages the program, don't edit it in the app afterwards – even opening the
  program in the app and going back can write the app's copy over yours. Close the app.
- A lost "off" point means the light stays on with the last values – always include it.
- Give the dongle a fixed IP in your router.
