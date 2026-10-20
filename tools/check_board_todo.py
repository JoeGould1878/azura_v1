#!/usr/bin/env python3
"""Check an Azura v1 schematic against the board to-do (docs/board-todo.md).

Usage: python3 tools/check_board_todo.py hardware/<name>.kicad_sch

Every connection in the to-do is checked by reference designator and pin number, so use the
references the to-do gives. Prints one line per check and a summary; exits 1 if anything fails.
Two-pin passives may be placed either way round. Diodes, the LED and C1 are polarity-checked.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kicad_netlist import netlist  # noqa: E402

GND = 'GND'

# Pins that must sit on each named net (polarised or multi-pin parts). A net with no entry here is
# pinned down by the two-terminal parts below.
ANCHORS = {
    GND: ['J1.A1', 'J1.A12', 'J1.B1', 'J1.B12', 'J1.SH', 'J4.A1', 'J4.A12', 'J4.B1', 'J4.B12', 'J4.SH',
          'J5.4', 'J5.SH', 'J3.2', 'D1.2', 'C1.2', 'U3.2', 'U1.4', 'U1.5', 'U2.3', 'D2.2', 'D4.1', 'TP8.1'],
    'USB_VBUS': ['J1.A4', 'J1.A9', 'J1.B4', 'J1.B9', 'D1.1', 'C1.1', 'U3.5', 'D3.2', 'TP1.1'],
    'MOD_5V': ['D3.1', 'J3.1', 'TP3.1'],
    'LAMP_VBUS': ['U3.1', 'D2.1', 'J4.A4', 'J4.A9', 'J4.B4', 'J4.B9', 'J5.1', 'TP2.1'],
    'DIG_OUT': ['J3.5', 'U3.4', 'TP7.1'],
    'ISET': ['U3.3'],
    '3v3_RAW': ['J3.3'],
    '3v3': ['U2.1', 'TP4.1'],
    'AMP_IN': ['U2.2'],
    'U1_IN+': ['U1.3'],
    'U1_IN-': ['U1.2'],
    'AMP_OUT': ['U1.1', 'TP5.1'],
    'ADC_IN': ['J3.8', 'TP6.1'],
    'U1_VCC': ['U1.8'],
    'U1B': ['U1.6', 'U1.7'],
    'J1_CC1': ['J1.A5'],
    'J1_CC2': ['J1.B5'],
    'J4_CC1': ['J4.A5'],
    'J4_CC2': ['J4.B5'],
    'J5_D+': ['J5.3'],
    'J5_D-': ['J5.2'],
    'GPIO10': ['J2.6'],
    'GPIO7': ['J2.3'],
    'LED_A': ['D4.2'],
    'GAIN_LEG': [],
}

# Two-terminal parts: (ref, net, net), either orientation.
BETWEEN = [
    ('R1', 'J1_CC1', GND), ('R2', 'J1_CC2', GND),
    ('R11', 'J4_CC1', 'USB_VBUS'), ('R12', 'J4_CC2', 'USB_VBUS'),
    ('C2', 'USB_VBUS', GND),
    ('R19', 'ISET', GND), ('R10', 'DIG_OUT', GND), ('C12', 'LAMP_VBUS', GND),
    ('R3', '3v3_RAW', '3v3'), ('C4', '3v3', GND), ('C5', '3v3', GND),
    ('R4', '3v3', 'U1_IN+'), ('R7', 'U1_IN+', GND), ('C3', 'AMP_IN', 'U1_IN+'),
    ('R5', 'AMP_OUT', 'U1_IN-'), ('C11', 'AMP_OUT', 'U1_IN-'),
    ('R6', 'U1_IN-', 'GAIN_LEG'), ('C8', 'GAIN_LEG', GND),
    ('R14', 'AMP_OUT', GND), ('R8', 'AMP_OUT', 'ADC_IN'), ('C9', 'ADC_IN', GND),
    ('JP1', 'USB_VBUS', 'U1_VCC'), ('R20', 'USB_VBUS', 'U1_VCC'),
    ('C7', 'U1_VCC', GND), ('C10', 'U1_VCC', GND),
    ('SW1', 'GPIO10', GND), ('R21', 'GPIO7', 'LED_A'),
    ('JP2', 'J5_D+', 'J5_D-'),
]

DELETED = ['Q1', 'Q2', 'Q3', 'Q4', 'R9', 'R13', 'R15', 'R16', 'R17', 'R18', 'C6']
UNFITTED = ['D2', 'R20', 'C10', 'C11', 'D4', 'R21', 'SW1', 'JP1', 'JP2'] + [f'TP{i}' for i in range(1, 9)]
FITTED = ['U1', 'U2', 'U3', 'D1', 'D3', 'J1', 'C2', 'C3', 'C4', 'C5', 'C7', 'C8', 'C9', 'C12',
          'R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7', 'R8', 'R10', 'R14', 'R19']

# (ref, allowed values in ohms/farads, allowed LCSC codes or None)
VALUES = [
    ('R8', [22e3], ['C31850']),
    ('R19', [4.7e3, 4.3e3], ['C23162', 'C23159']),
    ('C9', [1e-9], ['C1588']),
    ('C12', [10e-6], ['C19702']),
    ('R10', [10e3], None), ('R4', [200e3], None), ('R7', [100e3], None), ('R14', [4.7e3], None),
]
LCSC = [('U3', 'C55136'), ('D3', 'C8598'), ('D1', 'C2925443')]

_MULT = {'p': 1e-12, 'n': 1e-9, 'u': 1e-6, 'µ': 1e-6, 'μ': 1e-6, 'm': 1e-3, 'k': 1e3, 'K': 1e3, 'M': 1e6,
         'R': 1.0, 'r': 1.0, 'Ω': 1.0, 'F': 1.0}


def parse_value(text):
    """'4k7' -> 4700, '22k' -> 22000, '1nF' -> 1e-9, '0R5' -> 0.5, '10uF 10V' -> 1e-5."""
    t = (text or '').strip().split()[0] if text and text.strip() else ''
    m = re.match(r'^(\d+)([pnuµμmkKMRr])(\d+)', t)          # 4k7 style
    if m:
        return float(f'{m.group(1)}.{m.group(3)}') * _MULT[m.group(2)]
    m = re.match(r'^(\d+(?:\.\d+)?)\s*([pnuµμmkKMRrΩ]?)', t)
    if not m:
        return None
    return float(m.group(1)) * _MULT.get(m.group(2), 1.0)


class Report:
    def __init__(self):
        self.fails = 0
        self.oks = 0

    def check(self, ok, what, detail=''):
        if ok:
            self.oks += 1
            print(f'  ok    {what}')
        else:
            self.fails += 1
            print(f'  FAIL  {what}' + (f': {detail}' if detail else ''))


def main(path):
    print(f'Checking {path} against docs/board-todo.md\n')
    return check(netlist(path))


def check(nl):
    """Run every check on a netlist from kicad_netlist.netlist(). Returns 0 if all pass, else 1."""
    parts, nets, pinnet = nl['parts'], nl['nets'], nl['pinnet']
    r = Report()

    def net_of(pin):
        return pinnet.get(pin)

    def describe(idx):
        if idx is None:
            return 'not connected'
        n = nets[idx]
        name = '/'.join(sorted(n['names'])) or 'unnamed net'
        pins = sorted(n['pins'])
        return f"{name} [{', '.join(pins[:8])}{', ...' if len(pins) > 8 else ''}]"

    print('Parts removed')
    for ref in DELETED:
        r.check(ref not in parts, f'{ref} deleted', 'still on the schematic')

    print('\nParts present')
    for ref in sorted(set(r_ for r_, _, _ in BETWEEN) | {p.split('.')[0] for v in ANCHORS.values() for p in v}):
        r.check(ref in parts, f'{ref} present', 'missing (or annotated with a different reference)')

    # Resolve each named net from its anchor pins.
    resolved = {}
    print('\nNets')
    for name, anchor in ANCHORS.items():
        if not anchor:
            continue
        idxs = {net_of(p) for p in anchor if p.split('.')[0] in parts}
        found = [i for i in idxs if i is not None]
        if not found:
            r.check(False, f'{name}', 'none of its pins found')
            continue
        # Pick the net most of the anchors are on.
        best = max(found, key=lambda i: sum(1 for p in anchor if net_of(p) == i))
        resolved[name] = best
        stray = [p for p in anchor if p.split('.')[0] in parts and net_of(p) != best]
        r.check(not stray, f'{name}: {", ".join(anchor)}',
                '; '.join(f'{p} is on {describe(net_of(p))}' for p in stray))
    if GND in resolved:
        r.check('PWR:GND' in nets[resolved[GND]]['names'], 'GND net carries the GND power symbol')

    # Two-terminal parts, binding nets that have no anchors (GAIN_LEG) on first use.
    print('\nTwo-pin parts')
    for ref, a, b in BETWEEN:
        if ref not in parts:
            continue
        n1, n2 = net_of(f'{ref}.1'), net_of(f'{ref}.2')
        ra, rb = resolved.get(a), resolved.get(b)
        if ra is None and rb is not None:
            ra = n1 if n2 == rb else n2
            resolved[a] = ra
        if rb is None and ra is not None:
            rb = n1 if n2 == ra else n2
            resolved[b] = rb
        ok = {n1, n2} == {ra, rb} and n1 != n2
        r.check(ok, f'{ref} between {a} and {b}',
                f'pin 1 on {describe(n1)}; pin 2 on {describe(n2)}')

    print('\nNo two named nets shorted together')
    seen = {}
    for name, idx in resolved.items():
        if idx in seen:
            r.check(False, f'{name} is separate from {seen[idx]}', 'they are the same net')
        else:
            seen[idx] = name
    r.check(len(seen) == len(resolved), f'{len(resolved)} named nets are all distinct')

    print('\nPolarity and symbols')
    if 'D1' in parts:
        r.check(parts['D1']['lib'] != 'Device:D_TVS',
                'D1 uses a unidirectional symbol (cathode pin 1 on USB_VBUS)', f"still {parts['D1']['lib']}")

    print('\nValues and LCSC numbers')
    for ref, vals, codes in VALUES:
        if ref not in parts:
            continue
        v = parse_value(parts[ref]['value'])
        r.check(v is not None and any(abs(v - x) <= 0.011 * x for x in vals),
                f'{ref} = {parts[ref]["value"]}', f'expected {", ".join(map(_fmt, vals))}')
        if codes:
            r.check(parts[ref]['lcsc'] in codes, f'{ref} LCSC {parts[ref]["lcsc"] or "(none)"}',
                    f'expected {" or ".join(codes)}')
    for ref, code in LCSC:
        if ref in parts:
            r.check(parts[ref]['lcsc'] == code, f'{ref} LCSC {parts[ref]["lcsc"] or "(none)"}', f'expected {code}')

    print('\nFitted / unfitted')
    for ref in UNFITTED:
        if ref in parts:
            p = parts[ref]
            r.check(p['dnp'] == 'yes' and p['in_bom'] == 'no', f'{ref} unfitted (DNP, out of the BOM)',
                    f"dnp={p['dnp']} in_bom={p['in_bom']}")
    for ref in FITTED:
        if ref in parts:
            p = parts[ref]
            r.check(p['dnp'] != 'yes' and p['in_bom'] != 'no', f'{ref} fitted',
                    f"dnp={p['dnp']} in_bom={p['in_bom']}")

    if nl['issues']:
        print('\nConnectivity warnings (fix these too)')
        for s in nl['issues']:
            print(f'  warn  {s}')

    print(f'\n{r.oks} ok, {r.fails} to fix' + ('' if r.fails else ' - matches the board to-do'))
    return 1 if r.fails else 0


def _fmt(x):
    for unit, mult in (('µF', 1e-6), ('nF', 1e-9), ('pF', 1e-12)):
        if x < 1e-3 and x >= mult:
            return f'{x / mult:g} {unit}'
    return f'{x / 1e3:g} kΩ' if x >= 1e3 else f'{x:g} Ω'


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
