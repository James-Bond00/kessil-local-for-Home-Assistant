# kessil-local (Kurzfassung)

Lokale Steuerung von **Kessil**-Aquarienlampen über den **Kessil-WiFi-Dongle** –
ohne Cloud und ohne App, nur JSON über TCP im eigenen Netz.

> **Inoffiziell.** Kein Projekt von Kessil, nicht von Kessil unterstützt.
> Nutzung auf eigene Gefahr – die Verantwortung für die Tiere liegt bei dir.

## Was drin ist

- `docs/protocol.md` – das Protokoll (englisch): Nachrichtentypen, Werte, Effekte,
  die Befehlsfolgen der App und das **Lesen und Schreiben des Tagesprogramms**
- `kessil.py` – Kommandozeilen-Werkzeug (Python 3, keine Zusatzpakete)
- `examples/homeassistant/` – fertiges Home-Assistant-Package: Licht, Status,
  Regler, Effekte und ein Tagesprogramm, das sich am Sonnenuntergang ausrichtet

## Getestet

Kessil-WiFi-Dongle FW 1.5.13 mit zwei A360X Tuna Sun (FW 1.3 und 1.5) in einer Gruppe.

## Das Wichtigste in drei Sätzen

Der Dongle hört auf TCP-Port 8888 und nimmt Klartext-JSON ohne Passwort an.
Ein- und Ausschalten, manuelle Werte und Effekte funktionieren nur zuverlässig,
wenn man die Befehlspaare der App nachbaut (z. B. aus = `pause 1` **und** Werte 0).
Das Tagesprogramm schreibt man komplett mit dtype 107 – die Felder heißen dort
`m/d/EID/f`, beim Lesen (dtype 106) aber `minutes/duration/eid/freq`.

## Schnellstart

```sh
export KESSIL_HOST=192.168.1.50
python3 kessil.py status
python3 kessil.py program-read
```

Home Assistant: siehe [examples/homeassistant/README.md](examples/homeassistant/README.md).

## Gut zu wissen

- **Effekte:** Gewitter bleibt nach Ablauf immer auf der Lampe stehen, Wolken
  auch dann, wenn es aus dem laufenden Tagesprogramm gestartet wurde. Nach
  Ablauf den Status lesen und bei `eid` ≠ −1 selbst zurückschalten – das
  Home-Assistant-Beispiel macht das für jeden Effekt und hat einen Wächter
  für Effekte, die länger als 10 min hängen.
- **Verbrauch** (zwei A360X Tuna Sun, am Hauszähler gemessen): 30 % ~36 W,
  50 % ~57 W, 70 % ~88 W, 100 % ~140 W. Faustformel
  P ≈ 140 W × (INT/255)^1,2 × Farbfaktor (CLR 0 % 0,70 · 80 % 1,00 · 100 % 0,89).
  Details in `docs/protocol.md`.

Lizenz: MIT.
