#!/usr/bin/env python3
"""Azura v1 double-clap detector: integer reference model (design stage).

This is the golden model described in the design doc ("Double-clap DSP"). The C port in
components/clap_dsp must reproduce its event log exactly for the same input samples.

Input: 12-bit ADC codes at 16 kHz (as the ESP32-C3 delivers them, bias ~1200 codes).
Pipeline (integer only):
  per sample : DC tracker (k=10) -> band split lo = LP(k=2), hi = x - lo
  per 1 ms   : E_hi = sum|hi|, E_lo = sum|lo| over 16 samples
               fast envelope (instant attack, release k=2), jump reference (k=5),
               noise floor (up k=11, down k=4, frozen during events / until re-armed)
               onset -> event features -> clap test -> double-clap state machine
Usage:
  python3 clap_model_reference.py            # synthetic sanity suite (10 seeds)
  python3 clap_model_reference.py file.wav   # run on a 16 kHz mono WAV (int16 or ADC codes)
Synthetic results at time of writing: 165/170 scenario runs behave as intended.
"""
import sys
import numpy as np

FS = 16000

P = dict(k_dc=10, k_hp=2, blk=16, k_rel=2, k_med=5, k_floor_up=11, k_floor_dn=4,
         on_shift=5,            # onset: env > 8 x floor   (floor_q is Q8, so floor_q >> 5)
         jump=4,                # onset: E_hi > 4 x 32 ms average
         clap_ratio_shift=4,    # clap / impulsive: peak > 16 x floor
         e_min=48,              # absolute minimum block sum (16 samples x ~3 LSB)
         rise_max=3,            # ms from onset to peak
         decay6_max=15,         # ms from peak to -6 dB
         ev_max=80,             # ms, longest event
         refractory=60,         # ms after a clap onset
         hilo_min=1.0, feat_blocks=5,
         gap_min=150, gap_max=700, match_lo=0.35, match_hi=2.8,
         quiet_mul=1.5, quiet_min=400, quiet_max=800,
         lockout=1500, cooldown=1000, holdoff=2000)


def run(x, p=P):
    """Run the detector on an int array of ADC codes. Returns a list of (kind, t_ms, info)."""
    x = np.asarray(x, dtype=np.int64)
    dc_q = int(x[:256].mean()) << p['k_dc']
    lp_q = 0
    env = 0
    med_q = 0
    floor_q = None
    armed = True
    st = 'IDLE'
    out = []
    ev = None
    last_clap_onset = -10**9
    clap1 = None
    t_state = 0
    quiet_until = 0
    gap = 0
    imp_flag = [False]

    def finish(ev):
        rise = ev['t_peak'] - ev['t0']
        d6 = ev['d6'] if ev['d6'] is not None else 999
        hilo = ev['hi'] / max(ev['lo'], 1)
        strong = ev['peak'] > (ev['floor'] << p['clap_ratio_shift'])
        is_clap = rise <= p['rise_max'] and d6 <= p['decay6_max'] and hilo >= p['hilo_min'] and strong
        impulsive = rise <= p['rise_max'] and strong
        out.append(('event', ev['t0'], dict(peak=ev['peak'], floor=ev['floor'], rise=rise, d6=d6,
                                            hilo=round(hilo, 2), clap=is_clap, imp=impulsive)))
        imp_flag[0] = imp_flag[0] or impulsive
        return (ev['t0'], ev['peak']) if is_clap else None

    for b in range(len(x) // p['blk']):
        e_hi = 0
        e_lo = 0
        for v in x[b * p['blk']:(b + 1) * p['blk']]:
            v = int(v)
            dc_q += v - (dc_q >> p['k_dc'])
            xa = v - (dc_q >> p['k_dc'])
            lp_q += xa - (lp_q >> p['k_hp'])
            lo = lp_q >> p['k_hp']
            e_hi += abs(xa - lo)
            e_lo += abs(lo)
        t = b                                   # one block = 1 ms
        cand = None
        onset_evt = False
        imp_flag[0] = False
        env = e_hi if e_hi > env else env - ((env - e_hi) >> p['k_rel'])
        if floor_q is None:
            floor_q = max(env, 1) << 8
        floor = max(floor_q >> 8, 1)
        med = med_q >> p['k_med']
        if not armed and env < (floor_q >> p['on_shift']):
            armed = True                        # re-arm hysteresis
        onset_ok = (t >= p['holdoff'] and e_hi > p['e_min'] and env > (floor_q >> p['on_shift'])
                    and e_hi > p['jump'] * max(med, 1) and (t - last_clap_onset) >= p['refractory'])
        slow_event = ev is not None and t - ev['t0'] > p['rise_max'] and ev['t_peak'] - ev['t0'] > p['rise_max']
        if onset_ok and ((ev is None and armed) or slow_event):
            if ev is not None:
                cand = finish(ev)               # pre-empt a slow (non-clap) event
            ev = dict(t0=t, peak=e_hi, t_peak=t, floor=floor, d6=None, hi=0, lo=0, n=0)
            armed = False
            onset_evt = True
        if ev is not None:
            if ev['n'] < p['feat_blocks']:
                ev['hi'] += e_hi
                ev['lo'] += e_lo
                ev['n'] += 1
            if env > ev['peak']:
                ev['peak'] = env
                ev['t_peak'] = t
                ev['d6'] = None
            if ev['d6'] is None and env < (ev['peak'] >> 1):
                ev['d6'] = t - ev['t_peak']
            if env < (ev['peak'] >> 2) or t - ev['t0'] > p['ev_max']:
                c = finish(ev)
                cand = cand or c
                if c:
                    last_clap_onset = ev['t0']
                ev = None
        med_q += e_hi - (med_q >> p['k_med'])
        if ev is None and armed:                # floor frozen during events and until re-armed
            if (env << 8) < floor_q:
                floor_q -= (floor_q - (env << 8)) >> p['k_floor_dn']
            else:
                floor_q += ((env << 8) - floor_q) >> p['k_floor_up']
        # ---------------- double-clap state machine ----------------
        if st == 'IDLE':
            if cand:
                clap1 = cand
                st = 'WAIT2'
        elif st == 'WAIT2':
            if cand:
                g = cand[0] - clap1[0]
                r = cand[1] / clap1[1]
                if p['gap_min'] <= g <= p['gap_max'] and p['match_lo'] <= r <= p['match_hi']:
                    gap = g
                    st = 'QUIET'
                    quiet_until = cand[0] + int(min(max(p['quiet_mul'] * g, p['quiet_min']), p['quiet_max']))
                else:
                    clap1 = cand                # too late or mismatched: becomes the new clap 1
            elif t - clap1[0] > p['gap_max']:
                st = 'IDLE'
        elif st == 'QUIET':
            if cand or imp_flag[0]:
                st = 'LOCKOUT'
                t_state = t
                out.append(('reject', t, 'third impulsive event'))
            elif t >= quiet_until:
                out.append(('TOGGLE', t, dict(gap=gap)))
                st = 'COOLDOWN'
                t_state = t
        elif st == 'LOCKOUT':
            if cand or imp_flag[0]:
                t_state = t
            elif t - t_state >= p['lockout']:
                st = 'IDLE'
        elif st == 'COOLDOWN':
            if t - t_state >= p['cooldown']:
                st = 'IDLE'
    return out


# ---------------- synthetic scenes (sanity check only, not real audio) ----------------
BIAS = 1201
rng = np.random.default_rng(1)


def _band(n, lo, hi):
    from scipy.signal import butter, lfilter
    b, a = butter(2, [lo / (FS / 2), hi / (FS / 2)], btype='band')
    return lfilter(b, a, rng.standard_normal(n))


def clap(peak, rt60=0.5, reverb_db=-18):
    n = int(0.6 * FS)
    t = np.arange(n) / FS
    direct = _band(n, 700, 5000) * np.exp(-t / 0.003) * np.minimum(1, t / 0.0005)
    tail = _band(n, 300, 6000) * np.exp(-t * 6.91 / rt60) * 10 ** (reverb_db / 20) * np.minimum(1, t / 0.004)
    return (direct + tail) / np.max(np.abs(direct)) * peak


def knock(peak, f=350):
    n = int(0.3 * FS)
    t = np.arange(n) / FS
    s = np.sin(2 * np.pi * f * t) * np.exp(-t / 0.015) + 0.15 * _band(n, 500, 3000) * np.exp(-t / 0.004)
    return s / np.max(np.abs(s)) * peak


def slam(peak):
    n = int(0.8 * FS)
    t = np.arange(n) / FS
    s = _band(n, 40, 250) * np.exp(-t / 0.06) + 0.25 * _band(n, 800, 5000) * np.exp(-t / 0.01)
    return s / np.max(np.abs(s)) * peak


def snare(peak):
    n = int(0.25 * FS)
    t = np.arange(n) / FS
    s = 0.7 * np.sin(2 * np.pi * 190 * t) * np.exp(-t / 0.03) + _band(n, 1500, 7000) * np.exp(-t / 0.04)
    return s / np.max(np.abs(s)) * peak


def speech(dur, level):
    n = int(dur * FS)
    t = np.arange(n) / FS
    carrier = _band(n, 150, 3500)
    am = np.clip(np.sin(2 * np.pi * 4.3 * t + rng.uniform(0, 6)) + 0.3 * np.sin(2 * np.pi * 7.1 * t), 0, None) ** 1.5
    return carrier / np.std(carrier) * am * level


def scene(dur, events, bg_rms=4.0, extra=None):
    n = int(dur * FS)
    x = rng.standard_normal(n) * bg_rms
    if extra is not None:
        x[:len(extra)] += extra[:n]
    for t0, sig in events:
        i = int(t0 * FS)
        m = min(len(sig), n - i)
        x[i:i + m] += sig[:m]
    return np.clip(np.round(x + BIAS), 0, 4095).astype(np.int32)


def suite(seed):
    global rng
    rng = np.random.default_rng(seed)
    amp = {'0.5 m (clipped)': 2800, '1 m (clipped)': 1400, '2 m': 700, '4 m': 350}
    cases = []
    for lab, a in amp.items():
        cases.append((f'double clap {lab}, gap 300 ms', lambda a=a: scene(6, [(3.0, clap(a)), (3.3, clap(a * 0.8))]), 1))
    cases += [
        ('double clap 4 m, gap 180 ms', lambda: scene(6, [(3.0, clap(350)), (3.18, clap(320))]), 1),
        ('double clap 2 m, gap 650 ms', lambda: scene(6, [(3.0, clap(700)), (3.65, clap(600))]), 1),
        ('double clap 4 m, reverberant (RT60 1.0 s)', lambda: scene(6, [(3.0, clap(350, 1.0, -12)), (3.3, clap(330, 1.0, -12))]), 1),
        ('double clap 2 m over loud speech', lambda: scene(8, [(4.0, clap(700)), (4.35, clap(650))], extra=speech(8, 60)), 1),
        ('double clap 4 m over loud speech', lambda: scene(8, [(4.0, clap(350)), (4.35, clap(330))], extra=speech(8, 60)), 1),
        ('single clap 1 m', lambda: scene(6, [(3.0, clap(1400))]), 0),
        ('triple clap 2 m, 300 ms spacing', lambda: scene(6, [(3.0, clap(700)), (3.3, clap(680)), (3.6, clap(650))]), 0),
        ('applause-ish: 8 claps, 150-250 ms spacing', lambda: scene(7, [(3.0 + 0.2 * i + rng.uniform(-0.05, 0.05), clap(rng.uniform(300, 900))) for i in range(8)]), 0),
        ('mismatched loudness (1 m then 4 m level)', lambda: scene(6, [(3.0, clap(1400)), (3.3, clap(300))]), 0),
        ('knock-knock on wood, 220 ms apart', lambda: scene(6, [(3.0, knock(900)), (3.22, knock(850))]), 0),
        ('door slam', lambda: scene(6, [(3.0, slam(2000))]), 0),
        ('drum beat: snare every 500 ms for 4 s', lambda: scene(9, [(3.0 + 0.5 * i, snare(900)) for i in range(8)]), 0),
        ('speech only, 8 s', lambda: scene(8, [], extra=speech(8, 120)), 0),
    ]
    results = []
    for name, make, want in cases:
        got = sum(1 for o in run(make()) if o[0] == 'TOGGLE')
        results.append((name, got == want))
    return results


def run_wav(path):
    from scipy.io import wavfile
    fs, x = wavfile.read(path)
    if fs != FS:
        raise SystemExit(f'{path}: expected {FS} Hz, got {fs}')
    if x.ndim > 1:
        x = x[:, 0]
    if np.issubdtype(x.dtype, np.floating):                  # float WAV in [-1, 1]
        codes = np.clip(np.round(x * 2047) + 2048, 0, 4095).astype(np.int64)
    elif x.min() >= 0 and x.max() <= 4095:                   # capture-mode file: raw ADC codes
        codes = x.astype(np.int64)
    else:                                                    # ordinary int16 audio
        codes = np.clip((x.astype(np.int64) >> 4) + 2048, 0, 4095)
    for o in run(codes):
        if o[0] != 'event' or o[2]['clap']:
            print(o)


if __name__ == '__main__':
    if len(sys.argv) > 1:
        run_wav(sys.argv[1])
    else:
        total = []
        for seed in range(1, 11):
            total += suite(seed)
        fails = {}
        for name, ok in total:
            if not ok:
                fails[name] = fails.get(name, 0) + 1
        print(f'{sum(ok for _, ok in total)}/{len(total)} scenario runs behave as intended')
        for name, n in fails.items():
            print(f'  {n} x {name}')
