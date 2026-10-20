# Board to-do: KiCad changes, step by step

> Snapshot of the "Board to-do" tab of the design doc, 20 Oct 2026. Row numbers (#) refer to the
> Schematic review table in [design.md](design.md). Check your schematic against it with
> `python3 tools/check_board_todo.py hardware/<name>.kicad_sch`.

Work top to bottom. Each step names the parts, nets and values, with the Schematic review row (#) it comes from. Use the reference designators given here, setting them by hand in Symbol Properties: the check script finds parts by name. When the schematic is done, commit it to the repo (step 0) and I'll check it against this list before you start layout. The fitted board comes to 32 parts, against 40 as drawn.

## 0. Before you start

- [ ] Copy the KiCad project into the repo at `hardware/`: the `.kicad_pro` and `.kicad_sch` now, the `.kicad_pcb` later. The repo's `.gitignore` already leaves out backups, `fp-info-cache` and lock files.
- [ ] Make the imported parts a project-local library, so the repo opens on any machine. Copy your `easyeda2kicad.kicad_sym` and `easyeda2kicad.pretty` (and `.3dshapes`) into `hardware/lib/`. Add them under Preferences → Manage Symbol Libraries and Manage Footprint Libraries → Project Specific Libraries, keeping the nickname `easyeda2kicad` so U2 still resolves.
- [ ] Import the SY6280 into that same library: `easyeda2kicad --full --lcsc_id=C55136 --output hardware/lib/easyeda2kicad`

## 1. Parts to add

| Ref | Part | LCSC | KiCad symbol | Footprint |
| --- | --- | --- | --- | --- |
| U3 | SY6280AAC load switch | C55136 (extended part) | `easyeda2kicad:SY6280AAC`, from the import in step 0 | SOT-23-5, from the import |
| D3 | B5819W Schottky, 40 V 1 A | C8598 | `Device:D_Schottky` | `Diode_SMD:D_SOD-123` |
| R19 | R_SET, 4.7 kΩ 1 % 0603 (see the note below) | C23162 (same as R14) | `Device:R_Small_US` | `Resistor_SMD:R_0603_1608Metric` |
| C12 | 10 µF 0603, lamp-port capacitor, fitted | C19702 (same as C4) | `Device:C_Small` | `Capacitor_SMD:C_0603_1608Metric` |
| R20 | 47 Ω 0603, unfitted | | `Device:R_Small_US` | `Resistor_SMD:R_0603_1608Metric` |
| C10 | 10 µF 0603, unfitted | C19702 (same as C4) | `Device:C_Small` | `Capacitor_SMD:C_0603_1608Metric` |
| C11 | 560 pF 0603, unfitted | | `Device:C_Small` | `Capacitor_SMD:C_0603_1608Metric` |
| D4 | Red LED 0603, unfitted (status LED) | C2286 | `Device:LED` | `LED_SMD:LED_0603_1608Metric` |
| R21 | 1 kΩ 0603, unfitted | C21190 (same as R6) | `Device:R_Small_US` | `Resistor_SMD:R_0603_1608Metric` |
| JP1 | Solder jumper, bridged (copper only) | | `Jumper:SolderJumper_2_Bridged` | `Jumper:SolderJumper-2_P1.3mm_Bridged_RoundedPad1.0x1.5mm` |
| JP2 | Solder jumper, open (copper only) | | `Jumper:SolderJumper_2_Open` | `Jumper:SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm` |
| SW1 | 6 × 6 mm tact switch, unfitted (fallback button) | | `Switch:SW_Push` | `Button_Switch_THT:SW_PUSH_6mm` |
| TP1–TP8 | Test pads (copper only) | | `Connector:TestPoint` | `TestPoint:TestPoint_Pad_D1.5mm` |

**R19 sets the lamp's current limit:** 6800 ÷ R19, ±25 %. 4.7 kΩ gives 1.1–1.8 A, which suits any lamp up to 1 A (5 W), and it is the same part as R14, so it adds no BOM line. For a 5–6 W lamp use 4.3 kΩ (C23159; 1.2–2.0 A). Don't go below about 3.6 kΩ, or the limit can exceed the SY6280's 2 A rating. A lamp drawing more than about 1.1 A needs a different switch, so check the lamp before ordering.

## 2. Delete

- [ ] Q1, Q2, R16, R17, R18: the input current limiter (#6)
- [ ] Q3, Q4, R9, R13: the old output switch (#6)
- [ ] C6 (#21) and R15 (#20)
- [ ] The dangling wire stub above C5 (#19)

## 3. Power in (#1, #6, #7)

- [ ] Wire J1's VBUS pins (A4/A9/B4/B9) straight to `USB_VBUS`. With the limiter gone they are one net.
- [ ] D1: swap the bidirectional `Device:D_TVS` for a unidirectional symbol, such as `Device:D_Zener` with footprint `Diode_SMD:D_SMA`. Cathode (pin 1) to `USB_VBUS`, anode (pin 2) to GND. Keep LCSC C2925443.
- [ ] C1 stays on `USB_VBUS`; in layout it goes right beside J1.

## 4. Lamp output (#2, #6, #22)

- [ ] Place U3. IN (pin 5) to `USB_VBUS`, GND (pin 2) to GND, EN (pin 4) to `DIG_OUT` (J3 pin 5, GPIO3), ISET (pin 3) through R19 to GND, OUT (pin 1) to a new label `LAMP_VBUS`. Check the imported symbol's pin numbers against the datasheet: 1 OUT, 2 GND, 3 ISET, 4 EN, 5 IN.
- [ ] R10 (10 kΩ) now runs from `DIG_OUT` to GND. It is EN's pull-down, so the lamp stays off through reset.
- [ ] C12 (10 µF) from `LAMP_VBUS` to GND; in layout it sits right at U3's OUT pin. The SY6280 is rated to only 6 V on every pin, and this capacitor is what soaks up ESD and plug-in spikes on the lamp port.
- [ ] `LAMP_VBUS` goes to J4's VBUS pins (A4/A9/B4/B9), J5 pin 1 and D2's cathode.
- [ ] J4's GND pins (A1/A12/B1/B12), J5 pin 4 and D2's anode go to GND. This is the #2 fix.
- [ ] C2 (100 nF) stays on `USB_VBUS`; in layout it goes at U3's IN pin.
- [ ] R11 and R12 (22 kΩ) stay from J4 CC1/CC2 to `USB_VBUS`.

## 5. Module power (#3)

- [ ] Break the wire from `USB_VBUS` to J3 pin 1. Add D3 with its anode on `USB_VBUS` and its cathode on a new label `MOD_5V`, which goes to J3 pin 1.

## 6. Analogue (#9, #10, #11, #20)

- [ ] With R15 gone, `ADC_IN` keeps R8, C9 and J3 pin 8.
- [ ] R8: 10 kΩ → 22 kΩ (C31850, the same part as R11/R12). C9 stays 1 nF. That moves the anti-alias pole from 15.9 kHz to 7.2 kHz without a new part (#10). In the detector model it scores the same as a 3.3 nF C9 would.
- [ ] Label U1's output net `AMP_OUT` (U1 pin 1, R5, R14, R8).
- [ ] U1 supply (#11): break `USB_VBUS` at U1 pin 8. Put JP1 (bridged) and R20 (47 Ω) in parallel between `USB_VBUS` and a new label `U1_VCC` on U1 pin 8. Move C7 onto `U1_VCC`, and add C10 (10 µF) from `U1_VCC` to GND.
- [ ] C11 (560 pF) across R5, from U1 pin 1 to pin 2.
- [ ] R4 and R7 stay at 200 kΩ and 100 kΩ (1.1 V bias). R14 stays.

## 7. Optional footprints (#14, #16)

- [ ] SW1 (fallback button) from J2 pin 6 to GND. That is GPIO10 on the common pinout; check your module's silkscreen. Remove the pin's NC flag. No pull-up resistor: firmware turns on the internal one.
- [ ] Status LED: J2 pin 3 (GPIO7) → R21 (1 kΩ) → D4 anode; D4 cathode to GND. Remove the pin's NC flag. Fit both if the module's own LED ends up hidden in the enclosure; the firmware drives GPIO7 alongside the module LED.
- [ ] JP2 between J5 pin 3 (D+) and pin 2 (D−). Remove their NC flags.

## 8. Test pads (#12)

- [ ] TP1 `USB_VBUS`, TP2 `LAMP_VBUS`, TP3 `MOD_5V`, TP4 `3v3`, TP5 `AMP_OUT`, TP6 `ADC_IN`, TP7 `DIG_OUT`, TP8 GND

## 9. Unfitted parts and BOM

- [ ] D2, R20, C10, C11, D4, R21, SW1 and the TPs: in Symbol Properties tick "Do not populate", "Exclude from bill of materials" and "Exclude from position files". JP1 and JP2 have no part either, so exclude them too.
- [ ] Once the lamp is chosen, mark the unused connector the same way, plus R11/R12 if that is J4 (#23). If J4 goes, R8 still uses the 22 kΩ part.
- [ ] J2/J3: add an LCSC 1 × 8 2.54 mm female header if JLC is to fit them, otherwise exclude them from position files and hand-solder.
- [ ] J5, if you keep it (#4): run `easyeda2kicad --footprint --lcsc_id=C428472 --output hardware/lib/easyeda2kicad` and assign that footprint, so footprint and part match.
- [ ] U2 (#5): open its footprint and add the sound hole. That is an NPTH mechanical pad with a 0.6 mm drill, centred on the acoustic port from the datasheet's package drawing, inside the ground ring, with no paste.

## 10. Check and hand over

- [ ] Fix the label typos and move the NC flags onto the J1 D+/D− pins (#19)
- [ ] Annotate, keeping the references above; ERC clean
- [ ] Run `python3 tools/check_board_todo.py hardware/<your file>.kicad_sch` from the repo root. It checks every connection in this list and prints what is still missing.
- [ ] Commit `hardware/` on a branch and tell me, or upload the `.kicad_sch` here, and I'll go over it before layout

## Layout settings to enter first

Then follow the PCB layout guide in [design.md](design.md).

| Setting | Value |
| --- | --- |
| Board Setup → Constraints: minimum track, clearance | 0.2 mm, 0.2 mm |
| Minimum via diameter, drill | 0.6 mm, 0.3 mm |
| Copper to board edge | 0.3 mm |
| Net class `Default` | 0.25 mm track, 0.2 mm clearance |
| Net class `LAMP_5V`: `USB_VBUS`, `LAMP_VBUS` | 1.0 mm track, 0.25 mm clearance, 0.8 / 0.4 mm via |
| Net class `PWR`: `MOD_5V`, `3v3`, `U1_VCC` | 0.4 mm track |
| Board outline (Edge.Cuts) | Start around 55 × 35 mm and shrink once everything fits |
| Zones | GND on B.Cu over the whole board; GND pour on F.Cu in free areas; a copper keep-out rule area on both layers under the module's antenna end |
| Fabrication outputs | The Fabrication Toolkit plugin exports JLC Gerbers, BOM and CPL, and reads your `LCSC Part #` field |
| Mounting holes | 2–4 × M2.5 (MountingHole_2.7mm_M2.5), placed once the enclosure is known; no copper within 1 mm |
