#!/usr/bin/env python3
"""Minimal KiCad .kicad_sch netlister for a single flat sheet (Azura v1 helper).
Usage: python3 kicad_netlist.py Project_Az_v1_kicad.kicad_sch

Rules (strict, KiCad-like):
  * wires connect to each other at shared endpoints
  * a wire endpoint on another wire's interior connects only if a junction sits there
  * a junction connects every wire passing through or ending at it
  * a pin connects to wire endpoints / other pins / labels at its exact location
    (a pin on a wire interior is only connected if a junction is there)
  * a local label connects to any wire it touches (endpoint or interior) and to pins at its location
  * same-name labels share a net; power symbols with the same value share a net
Reports anything that would be dangling / suspicious.
"""
import sys, re, math
from collections import defaultdict

# ---------------- s-expression parser ----------------
def tokenize(s):
    i, n = 0, len(s)
    while i < n:
        c = s[i]
        if c in ' \t\r\n':
            i += 1
        elif c == '(' or c == ')':
            yield c; i += 1
        elif c == '"':
            j = i + 1; buf = []
            while j < n and s[j] != '"':
                if s[j] == '\\' and j + 1 < n:
                    buf.append(s[j + 1]); j += 2
                else:
                    buf.append(s[j]); j += 1
            yield ('STR', ''.join(buf)); i = j + 1
        else:
            j = i
            while j < n and s[j] not in ' \t\r\n()':
                j += 1
            yield ('ATOM', s[i:j]); i = j

def parse(s):
    stack = [[]]
    for t in tokenize(s):
        if t == '(':
            stack.append([])
        elif t == ')':
            x = stack.pop(); stack[-1].append(x)
        else:
            stack[-1].append(t[1])
    return stack[0][0]

def head(x): return x[0] if isinstance(x, list) and x else None
def kids(x, name): return [c for c in x if isinstance(c, list) and c and c[0] == name]
def kid(x, name):
    k = kids(x, name); return k[0] if k else None

R = lambda v: round(float(v), 3)

# ---------------- load ----------------
src = open(sys.argv[1], encoding='utf-8').read()
root = parse(src)

# library pins: lib_id -> unit -> list of (num, name, type, x, y, hidden)
libpins = {}
for sym in kids(kid(root, 'lib_symbols'), 'symbol'):
    lib_id = sym[1]
    base = lib_id.split(':', 1)[1]
    units = defaultdict(list)
    for sub in kids(sym, 'symbol'):
        m = re.match(re.escape(base) + r'_(\d+)_(\d+)$', sub[1])
        if not m:
            continue
        unit = int(m.group(1))
        for p in kids(sub, 'pin'):
            at = kid(p, 'at')
            num = kid(p, 'number')[1]
            nm = kid(p, 'name')[1]
            hidden = any(isinstance(c, list) and c[0] == 'hide' and c[1] == 'yes' for c in p)
            units[unit].append((num, nm, p[1], R(at[1]), R(at[2]), hidden))
    libpins[lib_id] = units

def xform(px, py, rot):
    # lib coords are Y-up; schematic is Y-down. KiCad rotation is CCW on screen.
    x, y = px, -py
    rot = int(float(rot)) % 360
    if rot == 0:   return (x, y)
    if rot == 90:  return (y, -x)
    if rot == 180: return (-x, -y)
    if rot == 270: return (-y, x)
    raise ValueError(rot)

# instances
pins = []   # dict(ref, num, name, type, pos)
parts = {}  # ref -> info
for s in kids(root, 'symbol'):
    lib_id = kid(s, 'lib_id')[1]
    at = kid(s, 'at'); sx, sy, rot = R(at[1]), R(at[2]), at[3] if len(at) > 3 else 0
    unit = int(kid(s, 'unit')[1]) if kid(s, 'unit') else 1
    props = {p[1]: p[2] for p in kids(s, 'property')}
    ref = props.get('Reference'); val = props.get('Value')
    inbom = kid(s, 'in_bom')[1] if kid(s, 'in_bom') else '?'
    parts.setdefault(ref, dict(lib=lib_id, value=val, fp=props.get('Footprint', ''),
                               desc=props.get('Description', ''), lcsc=props.get('LCSC Part #', props.get('LCSC Part', '')),
                               units=[], in_bom=inbom))
    parts[ref]['units'].append(unit)
    ul = libpins[lib_id]
    plist = ul.get(unit, []) + (ul.get(0, []) if unit != 0 else [])
    for (num, nm, typ, px, py, hidden) in plist:
        ox, oy = xform(px, py, rot)
        pins.append(dict(ref=ref, num=num, name=nm, type=typ, pos=(R(sx + ox), R(sy + oy)),
                         power=lib_id.startswith('power:'), value=val, hidden=hidden))

wires = []
for w in kids(root, 'wire'):
    pts = kid(w, 'pts')
    a = (R(pts[1][1]), R(pts[1][2])); b = (R(pts[2][1]), R(pts[2][2]))
    wires.append((a, b, kid(w, 'uuid')[1]))
labels = [(l[1], (R(kid(l, 'at')[1]), R(kid(l, 'at')[2]))) for l in kids(root, 'label')]
junctions = set((R(kid(j, 'at')[1]), R(kid(j, 'at')[2])) for j in kids(root, 'junction'))
ncs = set((R(kid(j, 'at')[1]), R(kid(j, 'at')[2])) for j in kids(root, 'no_connect'))

# ---------------- connectivity ----------------
parent = {}
def find(x):
    parent.setdefault(x, x)
    while parent[x] != x:
        parent[x] = parent[parent[x]]; x = parent[x]
    return x
def union(a, b): parent[find(a)] = find(b)

def on_interior(p, a, b):
    (x, y), (x1, y1), (x2, y2) = p, a, b
    if p == a or p == b: return False
    if abs((x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)) > 1e-6: return False
    return min(x1, x2) - 1e-6 <= x <= max(x1, x2) + 1e-6 and min(y1, y2) - 1e-6 <= y <= max(y1, y2) + 1e-6

W = lambda i: ('W', i)
P = lambda i: ('P', i)
L = lambda i: ('L', i)
for i, _ in enumerate(wires): find(W(i))
for i, _ in enumerate(pins): find(P(i))
for i, _ in enumerate(labels): find(L(i))

issues = []
endpoint_map = defaultdict(list)  # point -> wire idx with that endpoint
for i, (a, b, _) in enumerate(wires):
    endpoint_map[a].append(i); endpoint_map[b].append(i)
for pt, ws in endpoint_map.items():
    for w in ws[1:]: union(W(ws[0]), W(w))
# T-connections
for i, (a, b, uid) in enumerate(wires):
    for j, (c, d, uid2) in enumerate(wires):
        if i == j: continue
        for e in (c, d):
            if on_interior(e, a, b):
                if e in junctions: union(W(i), W(j))
                else: issues.append(f'T-joint WITHOUT junction at {e}: wire {uid2[:8]} ends on wire {uid[:8]} (KiCad will NOT connect)')
# junctions through wires
for jpt in junctions:
    ws = [i for i, (a, b, _) in enumerate(wires) if jpt in (a, b) or on_interior(jpt, a, b)]
    for w in ws[1:]: union(W(ws[0]), W(w))
    if len(ws) == 0: issues.append(f'junction at {jpt} touches no wire')
# pins
pin_at = defaultdict(list)
for i, p in enumerate(pins): pin_at[p['pos']].append(i)
for pt, ps in pin_at.items():
    for q in ps[1:]: union(P(ps[0]), P(q))
    for w in endpoint_map.get(pt, []): union(P(ps[0]), W(w))
    for i, (a, b, uid) in enumerate(wires):
        if on_interior(pt, a, b):
            if pt in junctions: union(P(ps[0]), W(i))
            else: issues.append(f'pin {pins[ps[0]]["ref"]}.{pins[ps[0]]["num"]} sits mid-wire at {pt} with no junction')
# labels
for li, (name, pt) in enumerate(labels):
    touched = False
    for i, (a, b, _) in enumerate(wires):
        if pt in (a, b) or on_interior(pt, a, b):
            union(L(li), W(i)); touched = True
    for q in pin_at.get(pt, []): union(L(li), P(q)); touched = True
    if not touched: issues.append(f'label {name} at {pt} touches nothing')
byname = defaultdict(list)
for li, (name, pt) in enumerate(labels): byname[name].append(li)
for name, ls in byname.items():
    for l in ls[1:]: union(L(ls[0]), L(l))
    if len(ls) == 1: issues.append(f'label {name} used only once (no partner)')
pw = defaultdict(list)
for i, p in enumerate(pins):
    if p['power']: pw[p['value']].append(i)
for v, ps in pw.items():
    for q in ps[1:]: union(P(ps[0]), P(q))

# dangling wire ends
for i, (a, b, uid) in enumerate(wires):
    for e in (a, b):
        others = [w for w in endpoint_map[e] if w != i]
        on_pin = e in pin_at
        on_lab = any(pt == e for _, pt in labels)
        on_mid = any(on_interior(e, c, d) for k, (c, d, _) in enumerate(wires) if k != i) and e in junctions
        if not (others or on_pin or on_lab or on_mid or e in ncs or e in junctions):
            issues.append(f'dangling wire end at {e} (wire {uid[:8]})')
# NC flags
for n in ncs:
    if n not in pin_at:
        w = [i for i, (a, b, _) in enumerate(wires) if n in (a, b)]
        issues.append(f'no-connect flag at {n} is not on a pin' + (' (sits on a wire end)' if w else ''))

# ---------------- nets ----------------
nets = defaultdict(lambda: dict(pins=[], labels=set()))
for i, p in enumerate(pins):
    if p['power']:
        nets[find(P(i))]['labels'].add('PWR:' + p['value'])
    else:
        nets[find(P(i))]['pins'].append(i)
for li, (name, pt) in enumerate(labels):
    nets[find(L(li))]['labels'].add(name)
# NC nets
nc_roots = set()
for n in ncs:
    for w in endpoint_map.get(n, []): nc_roots.add(find(W(w)))
    for q in pin_at.get(n, []): nc_roots.add(find(P(q)))

out = []
for r, net in nets.items():
    names = sorted(net['labels'])
    pl = sorted(net['pins'], key=lambda i: (pins[i]['ref'], pins[i]['num']))
    desc = ', '.join(f"{pins[i]['ref']}.{pins[i]['num']}({pins[i]['name'] or '-'})" for i in pl)
    tag = ' [NC]' if r in nc_roots else ''
    out.append((('/'.join(names) or '~unnamed'), desc, len(pl), tag))
for name, desc, n, tag in sorted(out):
    print(f'{name:<22}{tag:<6} [{n}] {desc}')

print('\n--- unconnected pins (no NC flag) ---')
for i, p in enumerate(pins):
    if p['power']: continue
    r = find(P(i))
    others = [q for q in nets[r]['pins'] if q != i]
    if not others and not nets[r]['labels'] and r not in nc_roots:
        print(f"  {p['ref']}.{p['num']} ({p['name']}) at {p['pos']}{' [hidden]' if p['hidden'] else ''}")
print('\n--- issues ---')
for s in sorted(set(issues)): print('  ' + s)
print('\n--- parts ---')
for ref in sorted(parts, key=lambda r: (re.sub(r'\d', '', r), int(re.sub(r'\D', '', r) or 0))):
    if ref.startswith('#'): continue
    p = parts[ref]
    print(f"  {ref:<5} {p['value']:<38} {p['lcsc']:<10} bom={p['in_bom']:<3} {p['fp']}  | {p['desc']}")
