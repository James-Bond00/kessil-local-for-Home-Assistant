# kessil-local

Local control of **Kessil** aquarium lights through the **Kessil WiFi dongle** –
no cloud, no app, just JSON over TCP in your own network.

- `docs/protocol.md` – the protocol: message types, values, effects, the command
  sequences the app uses, and how to read and **write the daily program**
- `kessil.py` – a small command line tool (Python 3, no extra packages)
- `examples/homeassistant/` – a ready-made Home Assistant package: light entity,
  status sensor, sliders, effects, and a daily program that follows the sunset

> **Unofficial.** This project is not affiliated with, endorsed or supported by Kessil.
> "Kessil" is a trademark of its owner and is used here only to describe compatibility.
> Use at your own risk – you are responsible for your livestock.

Deutsche Kurzfassung: [README.de.md](README.de.md)

## Tested hardware

| device | firmware |
|---|---|
| Kessil WiFi dongle | 1.5.13 |
| A360X Tuna Sun (2 lamps, one group) | 1.3 and 1.5 |

Other lamps on the same dongle will very likely work for on/off, values and effects.
The daily program uses a lamp `type` (2 = Tuna Sun); other types are untested –
reports welcome.

## Command line

```sh
export KESSIL_HOST=192.168.1.50      # IP of your dongle
python3 kessil.py status
python3 kessil.py off
python3 kessil.py on
python3 kessil.py manual 200 128 0 40          # INT CLR RED AMBER
python3 kessil.py effect storm --frequency often --seconds 120
python3 kessil.py effect-off
python3 kessil.py program 1                    # back to the daily program
python3 kessil.py program-read
python3 kessil.py program-write "420:2,0,0,65;480:51,25,0,16;600:255,229,0,0;780:255,178,0,0;905:102,0,100,0;965:0,0,100,28;1030:0,0,0,0"
```

Every command prints one line of JSON and exits with 0 on success.

The dongle accepts only **one connection at a time**. `kessil.py` takes a lock
file so parallel calls wait for each other, retries if there is no answer, and
puts the lamp back into its previous state if an effect command gets lost.

### Effects on a Tuna Sun (tested)

| name | number | what you see | after its time |
|---|---|---|---|
| storm | 0 | dimmed, short bright flashes | **stays** in the effect – switch back yourself |
| cloud | 1 | brightness goes up and down | returns by itself |
| rainbow | 2 | red → orange → almost off → orange → red (no blue/green on a Tuna Sun) | returns by itself |
| aurora | 3 | slow pulsing, darker and brighter | returns by itself |
| moonlight-red / -blue | 4 / 5 | nothing visible on a Tuna Sun | returns by itself |

The effects work on the white channels – during a red/amber sunset you hardly
see them. Names for 2, 4 and 5 are taken from the Kessil manual.

`program-write` writes the complete program, activates it, reads it back and
reports `"verified": true` if the lamp has exactly what was sent.

Program format: `MINUTES:INT,CLR,RED,AMBER;…` – minutes after midnight, ascending,
the last point is the "off" point. INT/CLR 0–255, RED/AMBER 0–100.

Options / environment: `--host` `KESSIL_HOST`, `--port` `KESSIL_PORT` (8888),
`--group` `KESSIL_GROUP` (2), `--pid` `KESSIL_PID` (1), `--type` `KESSIL_TYPE` (2).

## Home Assistant

See [examples/homeassistant/README.md](examples/homeassistant/README.md).
In short: copy `shell/kessil.py` and `packages/kessil.yaml`, set your dongle IP,
restart. You get:

- `light.kessil` – on/off, brightness, effects (storm, cloud, rainbow, aurora)
- `sensor.kessil_status` – Off / Manual / Program / Effect
- sliders for INT, color, red, amber; effect frequency and duration
- `script.kessil_resume_program`
- a daily program that keeps its shape and ends at **sunset + offset** (or a fixed
  time / sunrise), written to the lamp every Sunday and with a button. The lamp
  then runs on its own, even if Home Assistant is down.

## Why write the program instead of dimming live?

The dongle runs its program by itself. Writing it once a week means the light keeps
working when Home Assistant restarts or the network hiccups – nothing has to send
commands every minute.

## Contributing

Captures from other Kessil lamps (A80, A160, AP9X …) or other firmware are very welcome.
Please remove serial numbers, SSIDs and IPs before posting.

## License

MIT – see [LICENSE](LICENSE).
