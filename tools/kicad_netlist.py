#!/usr/bin/env python3
"""Minimal KiCad .kicad_sch netlister for a single flat sheet (Azura v1 helper).

Usage:  python3 tools/kicad_netlist.py hardware/<name>.kicad_sch
Import: from kicad_netlist import netlist   (used by tools/check_board_todo.py)

Rules (strict, KiCad-like):
  * wires connect to each other at shared endpoints
  * a wire endpoint on another wire's interior connects only if a junction sits there
  * a junction connects every wire passing through or ending at it
  * a pin connects to wire endpoints / other pins / labels at its exact location
    (a pin on a wire interior is only connected if a junction is there)
  * a label (local, global or hierarchical) connects to any wire it touches and to pins at its location
  * same-name labels share a net; power symbols with the same value share a net
  * symbol rotation and mirroring follow KiCad's transform matrices
Reports anything that would be dangling or suspicious.
"""
import re
import sys
from collections import defaultdict

LABEL_KINDS = ('label', 'global_label', 'hierarchical_label')


# ---------------- s-expression parser ----------------
def _tokenize(s):
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c in ' \t\r\n':
            i += 1
        elif c in '()':
            yield c
            i += 1
        elif c == '"':
            j = i + 1
            buf = []
            while j < n and s[j] != '"':
                if s[j] == '\\' and j + 1 < n:
                    buf.append(s[j + 1])
                    j += 2
                else:
                    buf.append(s[j])
                    j += 1
            yield ('STR', ''.join(buf))
            i = j + 1
        else:
            j = i
            while j < n and s[j] not in ' \t\r\n()':
                j += 1
            yield ('ATOM', s[i:j])
            i = j


def _parse(s):
    stack = [[]]
    for t in _tokenize(s):
        if t == '(':
            stack.append([])
        elif t == ')':
            x = stack.pop()
            stack[-1].append(x)
        else:
            stack[-1].append(t[1])
    return stack[0][0]


def _kids(x, name):
    return [c for c in x if isinstance(c, list) and c and c[0] == name]


def _kid(x, name):
    k = _kids(x, name)
    return k[0] if k else None


def _flag(x, name, default='?'):
    k = _kid(x, name)
    return k[1] if k and len(k) > 1 else default


def _r(v):
    return round(float(v), 3)


# ---------------- symbol transforms (KiCad TRANSFORM: X = x1*px + y1*py, Y = x2*px + y2*py) ----------------
def _compose(m, t):
    x1, y1, x2, y2 = m
    a1, b1, a2, b2 = t
    return (x1 * a1 + x2 * b1, y1 * a1 + y2 * b1, x1 * a2 + x2 * b2, y1 * a2 + y2 * b2)


_NORMAL = (1, 0, 0, -1)          # library Y-up -> schematic Y-down
_ROT_CCW = (0, 1, -1, 0)
_MIRROR_X = (1, 0, 0, -1)
_MIRROR_Y = (-1, 0, 0, 1)


def _transform(rot, mirror):
    m = _NORMAL
    for _ in range((int(float(rot)) % 360) // 90):
        m = _compose(m, _ROT_CCW)
    if mirror == 'x':
        m = _compose(m, _MIRROR_X)
    elif mirror == 'y':
        m = _compose(m, _MIRROR_Y)
    return m


def netlist(path):
    """Parse a flat .kicad_sch. Returns a dict with:
       parts:  ref -> {lib, value, fp, desc, lcsc, in_bom, dnp, in_pos, units}
       nets:   list of {names: set of label/power names, pins: set of 'REF.PIN', nc: bool}
       pinnet: 'REF.PIN' -> index into nets
       pins:   'REF.PIN' -> pin name
       issues: list of strings
    """
    root = _parse(open(path, encoding='utf-8').read())

    libpins = {}
    for sym in _kids(_kid(root, 'lib_symbols'), 'symbol'):
        lib_id = sym[1]
        base = lib_id.split(':', 1)[-1]
        units = defaultdict(list)
        for sub in _kids(sym, 'symbol'):
            m = re.match(re.escape(base) + r'_(\d+)_(\d+)$', sub[1])
            if not m:
                continue
            unit = int(m.group(1))
            for p in _kids(sub, 'pin'):
                at = _kid(p, 'at')
                hidden = any(isinstance(c, list) and c[0] == 'hide' and c[1:2] == ['yes'] for c in p)
                units[unit].append((_kid(p, 'number')[1], _kid(p, 'name')[1], p[1], _r(at[1]), _r(at[2]), hidden))
        is_power = _kid(sym, 'power') is not None or lib_id.startswith('power:')
        libpins[lib_id] = (units, is_power)

    pins = []
    parts = {}
    for s in _kids(root, 'symbol'):
        lib_id = _kid(s, 'lib_id')[1]
        at = _kid(s, 'at')
        sx, sy = _r(at[1]), _r(at[2])
        rot = at[3] if len(at) > 3 else 0
        mir = _kid(s, 'mirror')
        mat = _transform(rot, mir[1] if mir else None)
        unit = int(_kid(s, 'unit')[1]) if _kid(s, 'unit') else 1
        props = {p[1]: p[2] for p in _kids(s, 'property')}
        ref = props.get('Reference')
        val = props.get('Value')
        units, is_power = libpins[lib_id]
        part = parts.setdefault(ref, dict(
            lib=lib_id, value=val, fp=props.get('Footprint', ''), desc=props.get('Description', ''),
            lcsc=props.get('LCSC Part #', props.get('LCSC Part', props.get('LCSC', ''))),
            in_bom=_flag(s, 'in_bom'), dnp=_flag(s, 'dnp', 'no'), in_pos=_flag(s, 'in_pos_files'),
            power=is_power, units=[]))
        part['units'].append(unit)
        plist = units.get(unit, []) + (units.get(0, []) if unit != 0 else [])
        for (num, name, typ, px, py, hidden) in plist:
            x1, y1, x2, y2 = mat
            pos = (_r(sx + x1 * px + y1 * py), _r(sy + x2 * px + y2 * py))
            pins.append(dict(ref=ref, num=num, name=name, type=typ, pos=pos, power=is_power, value=val, hidden=hidden))

    wires = []
    for w in _kids(root, 'wire'):
        pts = _kid(w, 'pts')
        wires.append(((_r(pts[1][1]), _r(pts[1][2])), (_r(pts[2][1]), _r(pts[2][2])), _kid(w, 'uuid')[1]))
    labels = []
    for kind in LABEL_KINDS:
        for lab in _kids(root, kind):
            labels.append((lab[1], (_r(_kid(lab, 'at')[1]), _r(_kid(lab, 'at')[2]))))
    junctions = set((_r(_kid(j, 'at')[1]), _r(_kid(j, 'at')[2])) for j in _kids(root, 'junction'))
    ncs = set((_r(_kid(j, 'at')[1]), _r(_kid(j, 'at')[2])) for j in _kids(root, 'no_connect'))

    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        parent[find(a)] = find(b)

    def on_interior(p, a, b):
        (x, y), (xa, ya), (xb, yb) = p, a, b
        if p == a or p == b:
            return False
        if abs((xb - xa) * (y - ya) - (yb - ya) * (x - xa)) > 1e-6:
            return False
        return min(xa, xb) - 1e-6 <= x <= max(xa, xb) + 1e-6 and min(ya, yb) - 1e-6 <= y <= max(ya, yb) + 1e-6

    W = lambda i: ('W', i)  # noqa: E731
    P = lambda i: ('P', i)  # noqa: E731
    L = lambda i: ('L', i)  # noqa: E731
    for i in range(len(wires)):
        find(W(i))
    for i in range(len(pins)):
        find(P(i))
    for i in range(len(labels)):
        find(L(i))

    issues = []
    endpoint_map = defaultdict(list)
    for i, (a, b, _) in enumerate(wires):
        endpoint_map[a].append(i)
        endpoint_map[b].append(i)
    for ws in endpoint_map.values():
        for w in ws[1:]:
            union(W(ws[0]), W(w))
    for i, (a, b, uid) in enumerate(wires):
        for j, (c, d, uid2) in enumerate(wires):
            if i == j:
                continue
            for e in (c, d):
                if on_interior(e, a, b):
                    if e in junctions:
                        union(W(i), W(j))
                    else:
                        issues.append(f'T-joint without junction at {e}: wire {uid2[:8]} ends on wire {uid[:8]} '
                                      '(KiCad will not connect it)')
    for jpt in junctions:
        ws = [i for i, (a, b, _) in enumerate(wires) if jpt in (a, b) or on_interior(jpt, a, b)]
        for w in ws[1:]:
            union(W(ws[0]), W(w))
        if not ws:
            issues.append(f'junction at {jpt} touches no wire')
    pin_at = defaultdict(list)
    for i, p in enumerate(pins):
        pin_at[p['pos']].append(i)
    for pt, ps in pin_at.items():
        for q in ps[1:]:
            union(P(ps[0]), P(q))
        for w in endpoint_map.get(pt, []):
            union(P(ps[0]), W(w))
        for i, (a, b, _) in enumerate(wires):
            if on_interior(pt, a, b):
                if pt in junctions:
                    union(P(ps[0]), W(i))
                else:
                    issues.append(f'pin {pins[ps[0]]["ref"]}.{pins[ps[0]]["num"]} sits mid-wire at {pt} with no junction')
    for li, (name, pt) in enumerate(labels):
        touched = False
        for i, (a, b, _) in enumerate(wires):
            if pt in (a, b) or on_interior(pt, a, b):
                union(L(li), W(i))
                touched = True
        for q in pin_at.get(pt, []):
            union(L(li), P(q))
            touched = True
        if not touched:
            issues.append(f'label {name} at {pt} touches nothing')
    byname = defaultdict(list)
    for li, (name, _) in enumerate(labels):
        byname[name].append(li)
    for name, ls in byname.items():
        for lab in ls[1:]:
            union(L(ls[0]), L(lab))
        if len(ls) == 1:
            issues.append(f'label {name} used only once (no partner)')
    power_nets = defaultdict(list)
    for i, p in enumerate(pins):
        if p['power']:
            power_nets[p['value']].append(i)
    for ps in power_nets.values():
        for q in ps[1:]:
            union(P(ps[0]), P(q))

    for i, (a, b, uid) in enumerate(wires):
        for e in (a, b):
            others = [w for w in endpoint_map[e] if w != i]
            on_pin = e in pin_at
            on_label = any(pt == e for _, pt in labels)
            if not (others or on_pin or on_label or e in ncs or e in junctions):
                issues.append(f'dangling wire end at {e} (wire {uid[:8]})')
    for n in ncs:
        if n not in pin_at:
            on_wire = any(n in (a, b) for a, b, _ in wires)
            issues.append(f'no-connect flag at {n} is not on a pin' + (' (it sits on a wire end)' if on_wire else ''))

    groups = defaultdict(lambda: dict(names=set(), pins=set(), nc=False))
    for i, p in enumerate(pins):
        g = groups[find(P(i))]
        if p['power']:
            g['names'].add('PWR:' + p['value'])
        else:
            g['pins'].add(f"{p['ref']}.{p['num']}")
    for li, (name, _) in enumerate(labels):
        groups[find(L(li))]['names'].add(name)
    for n in ncs:
        for w in endpoint_map.get(n, []):
            groups[find(W(w))]['nc'] = True
        for q in pin_at.get(n, []):
            groups[find(P(q))]['nc'] = True

    nets, pinnet = [], {}
    for g in groups.values():
        if not g['pins'] and not g['names']:
            continue
        nets.append(g)
        for pin in g['pins']:
            pinnet[pin] = len(nets) - 1
    pin_names = {f"{p['ref']}.{p['num']}": p['name'] for p in pins if not p['power']}
    return dict(parts=parts, nets=nets, pinnet=pinnet, pins=pin_names, issues=sorted(set(issues)))


def _sort_key(pin):
    ref, num = pin.split('.', 1)
    m = re.match(r'([A-Za-z#]+)(\d*)', ref)
    return (m.group(1), int(m.group(2) or 0), num)


def main(path):
    nl = netlist(path)
    rows = []
    for net in nl['nets']:
        name = '/'.join(sorted(net['names'])) or '~unnamed'
        pins = sorted(net['pins'], key=_sort_key)
        desc = ', '.join(f"{p}({nl['pins'].get(p) or '-'})" for p in pins)
        rows.append((name, ' [NC]' if net['nc'] else '', len(pins), desc))
    for name, tag, n, desc in sorted(rows):
        print(f'{name:<22}{tag:<6} [{n}] {desc}')
    print('\n--- unconnected pins (no NC flag) ---')
    for pin in sorted(nl['pins'], key=_sort_key):
        net = nl['nets'][nl['pinnet'][pin]]
        if len(net['pins']) == 1 and not net['names'] and not net['nc']:
            print(f'  {pin} ({nl["pins"][pin]})')
    print('\n--- issues ---')
    for s in nl['issues']:
        print('  ' + s)
    print('\n--- parts ---')
    for ref in sorted((r for r, p in nl['parts'].items() if not p['power']), key=lambda r: _sort_key(r + '.0')):
        p = nl['parts'][ref]
        flags = f"bom={p['in_bom']:<3} dnp={p['dnp']:<3}"
        print(f"  {ref:<6} {p['value']:<34} {p['lcsc']:<10} {flags} {p['fp']}  | {p['desc']}")


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
