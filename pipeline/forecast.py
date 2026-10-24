"""Monthly temperature and hot-day forecasts for the HEATWISE dashboard.

Standard library only, so the weekly GitHub Actions run needs no extra packages.
Reads data/ecad_london_tx.csv (Met Office series via ECA&D) and writes
data/london_forecast.json with, for Heathrow, Wisley, Rothamsted and their average:

* the last five years of monthly mean daily maximum temperature and of hot days (>= 30 C);
* twelve-month forecasts from four methods and their ensemble:
    - seasonal naive (same month last year: the benchmark),
    - harmonic regression (linear trend + three seasonal harmonics),
    - Holt-Winters exponential smoothing (additive damped trend, additive seasonality),
    - seasonal ARIMA (1,0,0)(0,1,0)12 with drift,
    - ensemble = mean of the three fitted models;
* a backtest: each method's mean absolute error when forecasting the most recent twelve months;
* hot days per forecast month (Poisson link from monthly mean maximum, simulated with forecast
  uncertainty), and the distribution of hot days for the project summer (May-September).

The project year follows the dashboard's rule: the summer of the coming July, rolling over on 1 October.
"""
import csv
import datetime as dt
import json
import math
import os
import random

THR = 30
STATIONS = [('HEATHROW', 'Heathrow'), ('WISLEY', 'Wisley'), ('ROTHAMSTED', 'Rothamsted')]
AVG = 'London average'
FIT_FROM = (2008, 1)
SHOW = 60          # months of history to show
H = 12             # forecast horizon (months)
NSIM = 20000
ROLLOVER = (10, 1)  # month, day


def month_key(y, m):
    return y * 12 + (m - 1)


def key_ym(k):
    return k // 12, k % 12 + 1


def days_in(y, m):
    nxt = dt.date(y + (m == 12), m % 12 + 1, 1)
    return (nxt - dt.date(y, m, 1)).days


def load(path):
    daily = {lab: {} for _, lab in STATIONS}
    names = dict(STATIONS)
    last = None
    with open(path) as f:
        for r in csv.DictReader(f):
            lab = names.get(r['station'])
            if not lab:
                continue
            daily[lab][r['date']] = float(r['tx_c'])
            last = max(last or r['date'], r['date'])
    return daily, last


def monthly(series):
    """{(y, m): (mean tmax, hot days scaled to the full month)} for months with at least 20 valid days."""
    acc = {}
    for d, v in series.items():
        y, m = int(d[:4]), int(d[5:7])
        a = acc.setdefault((y, m), [0.0, 0, 0])
        a[0] += v; a[1] += 1; a[2] += v >= THR
    return {k: (a[0] / a[1], a[2] * days_in(*k) / a[1]) for k, a in acc.items() if a[1] >= 20}


# ---------------------------------------------------------------- small linear algebra
def solve(A, b):
    n = len(b); M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c])); M[c], M[p] = M[p], M[c]
        for r in range(n):
            if r != c and M[c][c]:
                f = M[r][c] / M[c][c]
                for k in range(c, n + 1):
                    M[r][k] -= f * M[c][k]
    return [M[i][n] / M[i][i] for i in range(n)]


def lstsq(X, y):
    p = len(X[0])
    A = [[sum(X[i][a] * X[i][b] for i in range(len(X))) for b in range(p)] for a in range(p)]
    v = [sum(X[i][a] * y[i] for i in range(len(X))) for a in range(p)]
    return solve(A, v)


# ---------------------------------------------------------------- forecasting methods
def seasonal_naive(y, h):
    return [y[len(y) - 12 + (i % 12)] for i in range(h)]


def harmonic(y, h, K=3, start_month=1):
    def row(t):
        r = [1.0, t / 120.0]
        mm = (start_month - 1 + t) % 12
        for k in range(1, K + 1):
            r += [math.sin(2 * math.pi * k * mm / 12), math.cos(2 * math.pi * k * mm / 12)]
        return r
    X = [row(t) for t in range(len(y))]
    b = lstsq(X, y)
    fit = [sum(bi * xi for bi, xi in zip(b, r)) for r in X]
    res = [a - f for a, f in zip(y, fit)]
    sd = math.sqrt(sum(e * e for e in res) / (len(y) - len(b)))
    return [sum(bi * xi for bi, xi in zip(b, row(t))) for t in range(len(y), len(y) + h)], sd


def _hw(y, a, bb, g, phi, h=0):
    m = 12
    l = sum(y[:m]) / m; tr = 0.0; s = [v - l for v in y[:m]]; sse = 0.0
    for i in range(m, len(y)):
        f = l + phi * tr + s[i - m]; e = y[i] - f; sse += e * e
        ln = a * (y[i] - s[i - m]) + (1 - a) * (l + phi * tr)
        tr = bb * (ln - l) + (1 - bb) * phi * tr
        s.append(g * (y[i] - ln) + (1 - g) * s[i - m]); l = ln
    if not h:
        return sse
    out = []; dsum = 0.0
    for k in range(1, h + 1):
        dsum += phi ** k
        out.append(l + dsum * tr + s[len(y) - m + (k - 1) % m])
    return out


def holt_winters(y, h):
    best = None
    for a in (0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6):
        for bb in (0.0, 0.02, 0.05, 0.1, 0.2):
            for g in (0.05, 0.1, 0.2, 0.3, 0.4, 0.5):
                for phi in (0.8, 0.9, 0.95, 0.98):
                    e = _hw(y, a, bb, g, phi)
                    if best is None or e < best[0]:
                        best = (e, a, bb, g, phi)
    return _hw(y, *best[1:], h=h)


def seasonal_arima(y, h):
    """SARIMA(1,0,0)(0,1,0)12 with drift, fitted by least squares on the seasonal differences."""
    z = [y[i] - y[i - 12] for i in range(12, len(y))]
    c, phi = lstsq([[1.0, z[i - 1]] for i in range(1, len(z))], z[1:])
    zz, yy = z[:], y[:]
    for _ in range(h):
        zn = c + phi * zz[-1]; zz.append(zn); yy.append(yy[-12] + zn)
    return yy[len(y):]


METHODS = [('Seasonal naive', seasonal_naive), ('Harmonic regression', lambda y, h: harmonic(y, h)[0]),
           ('Holt-Winters (ETS)', holt_winters), ('Seasonal ARIMA', seasonal_arima)]
ENSEMBLE_OF = ('Harmonic regression', 'Holt-Winters (ETS)', 'Seasonal ARIMA')


def poisson_fit(T, N):
    a, b = -10.0, 0.45
    for _ in range(100):
        g0 = g1 = h00 = h01 = h11 = 0.0
        for t, n in zip(T, N):
            lam = math.exp(a + b * t)
            g0 += n - lam; g1 += (n - lam) * t
            h00 += lam; h01 += lam * t; h11 += lam * t * t
        det = h00 * h11 - h01 * h01
        da = (h11 * g0 - h01 * g1) / det; db = (h00 * g1 - h01 * g0) / det
        a += da; b += db
        if abs(da) + abs(db) < 1e-9:
            break
    return a, b


def poisson(rng, lam):
    if lam <= 0:
        return 0
    if lam > 30:
        return max(0, int(round(rng.gauss(lam, math.sqrt(lam)))))
    L = math.exp(-lam); k = 0; p = 1.0
    while True:
        p *= rng.random()
        if p <= L:
            return k
        k += 1


def pct(sorted_vals, q):
    i = (len(sorted_vals) - 1) * q; lo = int(i); hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (i - lo)


def project_year(today):
    return today.year + 1 if (today.month, today.day) >= ROLLOVER else today.year


def run(out_dir, today=None):
    today = today or dt.datetime.now(dt.timezone.utc).date()
    daily, last = load(os.path.join(out_dir, 'ecad_london_tx.csv'))
    mon = {lab: monthly(daily[lab]) for lab in daily}
    # last complete month: the latest month with valid data at two or more stations
    common = sorted({k for lab in mon for k in mon[lab] if sum(k in mon[o] for o in mon) >= 2})
    end_y, end_m = common[-1]
    end = month_key(end_y, end_m); start = month_key(*FIT_FROM)
    keys = list(range(start, end + 1))
    series = {}
    for lab in mon:
        t, hd = [], []
        for k in keys:
            v = mon[lab].get(key_ym(k))
            t.append(v[0] if v else None); hd.append(v[1] if v else None)
        series[lab] = [t, hd]
    # fill gaps: same month last year plus the station's mean offset from the other stations
    for lab, (t, hd) in series.items():
        for i, v in enumerate(t):
            if v is None:
                others = [series[o][0][i] for o in series if o != lab and series[o][0][i] is not None]
                t[i] = sum(others) / len(others) if others else (t[i - 12] if i >= 12 else None)
                hd[i] = 0.0 if hd[i] is None else hd[i]
    labs = [lab for _, lab in STATIONS]
    series[AVG] = [[sum(series[l][0][i] for l in labs) / 3 for i in range(len(keys))],
                   [sum(series[l][1][i] for l in labs) / 3 for i in range(len(keys))]]
    # Poisson link over May-September months since 1991, per station; the average uses the mean of the stations' links
    links = {}
    for lab in labs:
        T, N = [], []
        for (y, m), (tm, hd) in mon[lab].items():
            if y >= 1991 and 5 <= m <= 9:
                T.append(tm); N.append(hd)
        links[lab] = poisson_fit(T, N)
    yr = project_year(today)
    fkeys = [end + i for i in range(1, H + 1)]
    out = {'generated_utc': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), 'dataEnd': '%04d-%02d' % (end_y, end_m),
           'projectYear': yr, 'fitFrom': '%04d-%02d' % FIT_FROM, 'threshold': THR, 'horizon': H,
           'methods': [m for m, _ in METHODS] + ['Ensemble'], 'ensembleOf': list(ENSEMBLE_OF), 'stations': {}}
    rng = random.Random(20270712)
    for lab in [AVG] + labs:
        y, hd = series[lab]
        fc = {name: f(y, H) for name, f in METHODS}
        fc['Ensemble'] = [sum(fc[n][i] for n in ENSEMBLE_OF) / len(ENSEMBLE_OF) for i in range(H)]
        yb, act = y[:-12], y[-12:]
        bt = {name: f(yb, 12) for name, f in METHODS}
        bt['Ensemble'] = [sum(bt[n][i] for n in ENSEMBLE_OF) / len(ENSEMBLE_OF) for i in range(12)]
        mae = {n: sum(abs(a - b) for a, b in zip(v, act)) / 12 for n, v in bt.items()}
        sd = harmonic(y, 1, start_month=FIT_FROM[1])[1]
        lk = [links[l] for l in labs] if lab == AVG else [links[lab]]
        # simulate hot days per forecast month
        per = [[] for _ in range(H)]
        summer_obs = sum(hd[keys.index(month_key(yr, m))] for m in range(5, 10) if month_key(yr, m) <= end)
        season, rem = [], []
        sm_idx = [i for i, k in enumerate(fkeys) if key_ym(k)[0] == yr and 5 <= key_ym(k)[1] <= 9]
        for _ in range(NSIM):
            r_tot = 0.0
            for i in range(H):
                mth = key_ym(fkeys[i])[1]
                if 5 <= mth <= 9:
                    tm = rng.gauss(fc['Ensemble'][i], sd)
                    c = sum(poisson(rng, math.exp(a + b * tm)) for a, b in lk) / len(lk)
                else:
                    c = 0
                per[i].append(c)
                if i in sm_idx:
                    r_tot += c
            rem.append(r_tot); season.append(summer_obs + r_tot)
        for p in per:
            p.sort()
        season.sort(); rem.sort()
        show = slice(len(keys) - SHOW, len(keys))
        q = [(i + 0.5) / 100 for i in range(100)]
        out['stations'][lab] = {
            'months': ['%04d-%02d' % key_ym(k) for k in keys[show]], 'tmax': [round(v, 2) for v in y[show]],
            'hot': [round(v, 1) for v in hd[show]], 'fmonths': ['%04d-%02d' % key_ym(k) for k in fkeys],
            'fc': {n: [round(v, 2) for v in vals] for n, vals in fc.items()}, 'sigma': round(sd, 2),
            'mae': {n: round(v, 2) for n, v in mae.items()},
            'hotF': [round(sum(p) / len(p), 2) for p in per], 'hotLo': [round(pct(p, 0.1), 1) for p in per], 'hotHi': [round(pct(p, 0.9), 1) for p in per],
            'summer': {'year': yr, 'observedHot': round(summer_obs, 1), 'observedTo': '%04d-%02d' % (end_y, end_m) if month_key(yr, 5) <= end else None,
                       'monthsForecast': len(sm_idx), 'mean': round(sum(season) / len(season), 2),
                       'p10': round(pct(season, 0.1), 1), 'p90': round(pct(season, 0.9), 1),
                       'pool': [round(pct(season, v), 2) for v in q], 'remPool': [round(pct(rem, v), 2) for v in q]}
        }
    with open(os.path.join(out_dir, 'london_forecast.json'), 'w') as f:
        json.dump(out, f, separators=(',', ':'))
    return out


if __name__ == '__main__':
    o = run(os.path.join(os.path.dirname(__file__), '..', 'data'))
    for k, v in o['stations'].items():
        print(k, 'MAE', v['mae'], 'summer', v['summer']['year'], 'mean', v['summer']['mean'], 'p10/p90', v['summer']['pool'][10], v['summer']['pool'][90])
