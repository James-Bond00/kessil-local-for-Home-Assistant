# Home Assistant example

A YAML package that turns the Kessil dongle into Home Assistant entities.
Uses only built-in integrations (`shell_command`, `command_line`, `template`).

## Install

1. Enable packages in `configuration.yaml` if you have not yet:
   ```yaml
   homeassistant:
     packages: !include_dir_named packages
   ```
2. Copy `kessil.py` from the repository root to `/config/shell/kessil.py`.
3. Copy `packages/kessil.yaml` to `/config/packages/kessil.yaml`.
4. Replace `192.168.1.50` with the IP of your dongle (all occurrences).
   Give the dongle a fixed IP in your router.
5. Check the configuration and restart Home Assistant.

## Entities

| entity | what it does |
|---|---|
| `light.kessil` | on/off (like the app), brightness = manual mode, effects None/Storm/Cloud/Rainbow/Aurora (switched back after its time if the lamp stays in the effect – Storm always, Cloud when started from the program; plus a 10-min watchdog) |
| `sensor.kessil_status` | Off / Manual / Program / Effect, attributes `pid`, `eid`, `pause`, `UI`, `name`, `hasLamps` |
| `input_number.kessil_intensity`, `_color`, `_red`, `_amber` | sliders for manual mode (applied while the light is on) |
| `input_select.kessil_effect`, `_effect_speed` (frequency: often/medium/rare), `input_number.kessil_effect_minutes` | effects |
| `script.kessil_resume_program` | back to the daily program |
| `sensor.kessil_program_plan` | the planned daily program (state "start–end", attribute `points`) |
| `script.kessil_write_program` | writes the plan to the lamp and verifies it |
| `input_boolean.kessil_program_weekly` | write the plan every Sunday 04:00 |

## Daily program

`input_text.kessil_program_shape` holds the **shape** of the day, with times relative
to the start:

```
0:2,0,0,65;60:51,25,0,16;180:255,229,0,0;360:255,178,0,0;485:102,0,100,0;545:0,0,100,28;610:0,0,0,0
```

`minutes after start:INT,CLR,RED,AMBER` – INT/CLR 0–255, RED/AMBER 0–100, the last
point is "off". Leave it empty to use this example (amber sunrise, 6 h full light,
red/amber sunset, 10 h 10 min in total).

The shape is moved as a whole, its length never changes:

| anchor | result |
|---|---|
| End at sunset | ends at sunset + offset |
| Start at sunrise | starts at sunrise + offset |
| End at fixed time | ends at the fixed time + offset |

The start is kept between "earliest start" and "latest start".

Run `script.kessil_write_program` once by hand and check
`input_text.kessil_program_message`. Then turn on
`input_boolean.kessil_program_weekly`.

Tip: if you edit the program in the Kessil app afterwards, the next write from
Home Assistant will overwrite it.

## Ideas

The same plan can drive other things: switch a CO₂ valve on with the first point
and off an hour before the light goes out, or let an LED strip follow the curve.
The times are in the attribute `points` of `sensor.kessil_program_plan`.
