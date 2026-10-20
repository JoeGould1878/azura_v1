# Board to-do: KiCad changes, step by step

> Snapshot of the "Board to-do" tab of the design doc, 20 Oct 2026. Row numbers (#) refer to the
> Schematic review table in [design.md](design.md).

Work top to bottom. Each step names the parts, nets and values, with the Schematic review row (#) it comes from. When the schematic is done, send the `.kicad_sch` for a netlist re-check before starting layout. Reference designators for new parts are suggestions; KiCad's annotation may number them differently.

## 1. Parts to add

| Ref | Part | LCSC | KiCad symbol | Footprint |
| --- | --- | --- | --- | --- |
| U3 | SY6280AAC load switch | C55136 (extended) | Import with `easyeda2kicad --full --lcsc_id=C55136` | SOT-23-5, from the import |
| D3 | B5819W Schottky, 40 V 1 A | C8598 | `Device:D_Schottky` | `Diode_SMD:D_SOD-123` |
| R19 | R_SET: 4.3 kΩ 1 % 0603, or 3.3 kΩ for a 1.5 A lamp | C23159 (3.3 kΩ: C22978, basic) | `Device:R_Small_US` | `Resistor_SMD:R_0603_1608Metric` |
| R20 | 47 Ω 0603, unfitted | | `Device:R_Small_US` | `Resistor_SMD:R_0603_1608Metric` |
| C10 | 10 µF 0603, unfitted | C19702 (same as C4) | `Device:C_Small` | `Capacitor_SMD:C_0603_1608Metric` |
| C11 | 560 pF 0603, unfitted | | `Device:C_Small` | `Capacitor_SMD:C_0603_1608Metric` |
| JP1 | Solder jumper, bridged (copper only) | | `Jumper:SolderJumper_2_Bridged` | `Jumper:SolderJumper-2_P1.3mm_Bridged_RoundedPad1.0x1.5mm` |
| JP2 | Solder jumper, open (copper only) | | `Jumper:SolderJumper_2_Open` | `Jumper:SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm` |
| SW1 | 6 × 6 mm tact switch, unfitted | | `Switch:SW_Push` | Any 6 × 6 mm tact switch footprint |
| TP1–TP8 | Test pads (copper only) | | `Connector:TestPoint` | `TestPoint:TestPoint_Pad_D1.5mm` |

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

- [ ] Place U3. IN (pin 5) to `USB_VBUS`, GND (pin 2) to GND, EN (pin 4) to `DIG_OUT` (J3 pin 5, GPIO3), ISET (pin 3) through R19 to GND, OUT (pin 1) to a new label `LAMP_VBUS`. Check the imported symbol's pin numbers against the datasheet.
- [ ] R10 (10 kΩ) now runs from `DIG_OUT` to GND: it is EN's pull-down.
- [ ] `LAMP_VBUS` goes to J4's VBUS pins (A4/A9/B4/B9), J5 pin 1 and D2's cathode.
- [ ] J4's GND pins (A1/A12/B1/B12), J5 pin 4 and D2's anode go to GND. This is the #2 fix.
- [ ] C2 (100 nF) stays on `USB_VBUS`; in layout it goes at U3's IN pin.
- [ ] R11 and R12 (22 kΩ) stay from J4 CC1/CC2 to `USB_VBUS`.

## 5. Module power (#3)

- [ ] Break the wire from `USB_VBUS` to J3 pin 1. Add D3 with its anode on `USB_VBUS` and its cathode on a new label `MOD_5V`, which goes to J3 pin 1.

## 6. Analogue (#9, #10, #11, #20)

- [ ] With R15 gone, `ADC_IN` keeps R8, C9 and J3 pin 8.
- [ ] C9: 1 nF → 3.3 nF, X7R 0603. C1613 was out of stock on 20 Oct; any in-stock 3.3 nF part is fine.
- [ ] Label U1's output net `AMP_OUT` (U1 pin 1, R5, R14, R8).
- [ ] U1 supply: break `USB_VBUS` at U1 pin 8. Put JP1 (bridged) and R20 (47 Ω) in parallel between `USB_VBUS` and a new label `U1_VCC` on U1 pin 8. Move C7 onto `U1_VCC`, and add C10 (10 µF) from `U1_VCC` to GND.
- [ ] C11 (560 pF) across R5.
- [ ] R4 and R7 stay at 200 kΩ and 100 kΩ (1.1 V bias). R14 stays.

## 7. Optional footprints (#14, #16)

- [ ] SW1 from J2 pin 6 to GND. That is GPIO10 on the common pinout; check your module's silkscreen. Remove the pin's NC flag. No pull-up resistor: firmware turns on the internal one.
- [ ] JP2 between J5 pin 3 (D+) and pin 2 (D−). Remove their NC flags.

## 8. Test pads (#12)

- [ ] TP1 `USB_VBUS`, TP2 `LAMP_VBUS`, TP3 `MOD_5V`, TP4 `3v3`, TP5 `AMP_OUT`, TP6 `ADC_IN`, TP7 `DIG_OUT`, TP8 GND

## 9. Unfitted parts and BOM

- [ ] D2, R20, C10, C11, SW1 and the TPs: in Symbol Properties tick "Do not populate", "Exclude from bill of materials" and "Exclude from position files". JP1 and JP2 have no part either, so exclude them too.
- [ ] Once the lamp is chosen, mark the unused connector the same way, plus R11/R12 if that is J4 (#23).
- [ ] J2/J3: add an LCSC 1 × 8 2.54 mm female header if JLC is to fit them, otherwise exclude them from position files and hand-solder.
- [ ] J5, if you keep it (#4): run `easyeda2kicad --footprint --lcsc_id=C428472` and assign that footprint, so footprint and part match.
- [ ] U2 (#5): open its footprint and add the sound hole. That is an NPTH mechanical pad with a 0.6 mm drill, centred on the acoustic port from the datasheet's package drawing, inside the ground ring, with no paste.

## 10. Check and hand over

- [ ] Fix the label typos and move the NC flags onto the J1 D+/D− pins (#19)
- [ ] Annotate; ERC clean
- [ ] Send the `.kicad_sch` for a check against this list and the netlist

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
