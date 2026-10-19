"""Fetch open London weather data for the HEATWISE dashboard.

Runs on GitHub Actions (see .github/workflows/fetch-weather.yml) and writes
processed files to data/. Sources:

1. Met Office historic station data (monthly, Heathrow), Crown Copyright,
   Open Government Licence. Updated monthly, so includes the current year.
2. Met Office UK regional climate series, England SE & central S (monthly
   mean maximum temperature). Open Government Licence.
3. Meteostat daily station data (CC BY 4.0) for London stations. These are
   redistributed observations (SYNOP via DWD, NOAA ISD/GHCN-D, METAR); rows
   filled from forecast models are discarded.
4. Optional: Met Office MIDAS Open daily temperature (CEDA, OGL) for Greater
   London stations, if CEDA_USERNAME and CEDA_PASSWORD secrets are set.
"""
import csv
import datetime as dt
import gzip
import io
import json
import os
import re
import sys
import time

import requests

OUT = os.path.join(os.path.dirname(__file__), '..', 'data')
os.makedirs(OUT, exist_ok=True)
NOW = dt.datetime.now(dt.timezone.utc)
UA = {'User-Agent': 'heatwise-teaching-pipeline (github.com/SBegUCL/heatwise)'}
REPORT = {'generated_utc': NOW.isoformat(timespec='seconds'), 'sources': {}, 'notes': []}

STATIONS = {
    '03772': 'London Heathrow',
    '03672': 'Northolt',
    '03781': 'Kenley',
    'EGLC0': 'London City Airport',
    'EGKB0': 'Biggin Hill',
}
FIRST_YEAR = 1979
MODEL_SOURCES = {'dwd_mosmix', 'metno_forecast', 'model', 'gfs', 'ecmwf', 'icon'}


def get(url, **kw):
    for attempt in range(3):
        try:
            r = requests.get(url, headers=UA, timeout=60, **kw)
            return r
        except requests.RequestException as e:  # network hiccup
            if attempt == 2:
                raise
            time.sleep(3)


# ---------------------------------------------------------------- Met Office monthly station data
def metoffice_station(name='heathrow'):
    url = 'https://www.metoffice.gov.uk/pub/data/weather/uk/climate/stationdata/%sdata.txt' % name
    r = get(url)
    info = {'url': url, 'status': r.status_code}
    if r.status_code != 200:
        REPORT['sources']['metoffice_station_' + name] = info
        return
    raw = r.text
    open(os.path.join(OUT, 'metoffice_%s_monthly.txt' % name), 'w').write(raw)
    rows = []
    for line in raw.splitlines():
        m = re.match(r'\s*(\d{4})\s+(\d{1,2})\s+(.*)$', line)
        if not m:
            continue
        vals = m.group(3).split()
        def num(i):
            if i >= len(vals):
                return ''
            v = vals[i].replace('*', '').replace('#', '')
            return '' if v in ('---', '') else v
        prov = 'Provisional' in line
        rows.append([m.group(1), m.group(2), num(0), num(1), num(2), num(3), num(4), 'Y' if prov else 'N'])
    with open(os.path.join(OUT, 'metoffice_%s_monthly.csv' % name), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['year', 'month', 'tmax_mean_c', 'tmin_mean_c', 'air_frost_days', 'rain_mm', 'sun_hours', 'provisional'])
        w.writerows(rows)
    info.update(rows=len(rows), first='%s-%s' % tuple(rows[0][:2]) if rows else None, last='%s-%s' % tuple(rows[-1][:2]) if rows else None)
    REPORT['sources']['metoffice_station_' + name] = info


# ---------------------------------------------------------------- Met Office regional series
def metoffice_region():
    base = 'https://www.metoffice.gov.uk/pub/data/weather/uk/climate/datasets/Tmax/date/'
    urls = [base + n + '.txt' for n in ('England_SE_and_central_S', 'England_SE_and_Central_S', 'England_SE_and_central_south',
                                        'England_SE_and_Central_South', 'England_SE')]
    tried = []
    for url in urls:
        r = get(url)
        tried.append([url, r.status_code])
        if r.status_code == 200 and 'jan' in r.text.lower():
            open(os.path.join(OUT, 'metoffice_region_SE_tmax.txt'), 'w').write(r.text)
            rows = []
            for line in r.text.splitlines():
                p = line.split()
                if p and re.fullmatch(r'\d{4}', p[0]):
                    rows.append(p[:13])
            with open(os.path.join(OUT, 'metoffice_region_SE_tmax_monthly.csv'), 'w', newline='') as f:
                w = csv.writer(f)
                w.writerow(['year', 'jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'])
                w.writerows(rows)
            REPORT['sources']['metoffice_region_SE_tmax'] = {'url': url, 'status': 200, 'rows': len(rows), 'last_year': rows[-1][0] if rows else None}
            return
    REPORT['sources']['metoffice_region_SE_tmax'] = {'status': 'not found', 'tried': tried}


# ---------------------------------------------------------------- Meteostat daily
def meteostat():
    out_rows = []
    per = {}
    for sid, sname in STATIONS.items():
        st = {'name': sname, 'years': 0, 'rows': 0, 'model_rows_dropped': 0, 'sources': {}, 'columns': None, 'http': {}}
        for y in range(FIRST_YEAR, NOW.year + 1):
            url = 'https://data.meteostat.net/daily/%d/%s.csv.gz' % (y, sid)
            r = get(url)
            st['http'][str(r.status_code)] = st['http'].get(str(r.status_code), 0) + 1
            if r.status_code != 200:
                continue
            try:
                text = gzip.decompress(r.content).decode('utf-8')
            except OSError:
                text = r.content.decode('utf-8', 'replace')
            rd = csv.DictReader(io.StringIO(text))
            if st['columns'] is None:
                st['columns'] = rd.fieldnames
            got = 0
            for row in rd:
                date = row.get('date') or row.get('time') or ''
                if not date and 'year' in row:
                    date = '%s-%02d-%02d' % (row['year'], int(row['month']), int(row['day']))
                tmax = row.get('tmax', '')
                src = row.get('tmax_source', '') or row.get('source', '')
                if tmax in ('', None):
                    continue
                if src and any(t in MODEL_SOURCES for t in src.lower().split()):
                    st['model_rows_dropped'] += 1
                    continue
                st['sources'][src or 'unspecified'] = st['sources'].get(src or 'unspecified', 0) + 1
                out_rows.append([sid, sname, date[:10], tmax, row.get('tmin', ''), src])
                got += 1
            if got:
                st['years'] += 1
                st['rows'] += got
            time.sleep(0.2)
        dates = [r[2] for r in out_rows if r[0] == sid]
        st['first'] = min(dates) if dates else None
        st['last'] = max(dates) if dates else None
        per[sid] = st
    out_rows.sort(key=lambda r: (r[0], r[2]))
    with open(os.path.join(OUT, 'london_daily_tmax.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['station_id', 'station', 'date', 'tmax_c', 'tmin_c', 'tmax_source'])
        w.writerows(out_rows)
    REPORT['sources']['meteostat_daily'] = {'url_pattern': 'https://data.meteostat.net/daily/{year}/{station}.csv.gz', 'licence': 'CC BY 4.0', 'stations': per}
    return out_rows


# ---------------------------------------------------------------- Optional MIDAS Open (CEDA)
def midas_open():
    user, pw = os.environ.get('CEDA_USERNAME'), os.environ.get('CEDA_PASSWORD')
    if not (user and pw):
        REPORT['sources']['midas_open'] = {'status': 'skipped: add CEDA_USERNAME and CEDA_PASSWORD repository secrets to enable'}
        return
    info = {}
    try:
        t = requests.post('https://services-beta.ceda.ac.uk/api/token/create/', auth=(user, pw), headers=UA, timeout=60)
        info['token_status'] = t.status_code
        token = t.json().get('access_token') if t.ok else None
        if not token:
            raise RuntimeError('no token returned')
        H = dict(UA, Authorization='Bearer ' + token)
        base = 'https://dap.ceda.ac.uk/badc/ukmo-midas-open/data/uk-daily-temperature-obs/'
        idx = requests.get(base, headers=H, timeout=60).text
        vers = sorted(set(re.findall(r'dataset-version-(\d{6})', idx)))
        ver = vers[-1]
        info['version'] = ver
        county = base + 'dataset-version-%s/greater-london/' % ver
        sites = sorted(set(re.findall(r'(\d{5}_[a-z0-9-]+)/', requests.get(county, headers=H, timeout=60).text)))
        info['sites'] = sites
        rows = []
        for site in sites:
            qc = county + site + '/qc-version-1/'
            files = sorted(set(re.findall(r'(midas-open_[^"\'<>]+?_(\d{4})\.csv)', requests.get(qc, headers=H, timeout=60).text)))
            for fname, year in files:
                if int(year) < FIRST_YEAR:
                    continue
                txt = requests.get(qc + fname, headers=H, timeout=120).text
                lines = txt.splitlines()
                try:
                    start = lines.index('data') + 1
                except ValueError:
                    continue
                rd = csv.DictReader(lines[start:])
                for row in rd:
                    if not row.get('ob_end_time') or row.get('ob_end_time') == 'end data':
                        continue
                    if row.get('ob_end_time', '').endswith('09:00:00') and row.get('max_air_temp'):
                        rows.append([site, row['ob_end_time'][:10], row.get('max_air_temp', ''), row.get('min_air_temp', ''), row.get('max_air_temp_q', '')])
        with open(os.path.join(OUT, 'midas_open_london_daily_temp.csv'), 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['site', 'ob_end_date', 'max_air_temp_c', 'min_air_temp_c', 'max_air_temp_q'])
            w.writerows(rows)
        info['rows'] = len(rows)
        info['status'] = 'ok'
    except Exception as e:  # keep the rest of the pipeline running
        info['status'] = 'failed: %s' % e
    REPORT['sources']['midas_open'] = info


# ---------------------------------------------------------------- ECA&D blended daily maximum temperature (Met Office-supplied UK series)
def ecad():
    import math, zipfile, tempfile
    urls = ['https://knmi-ecad-assets-prd.s3.amazonaws.com/download/ECA_blend_tx.zip',
            'https://www.ecad.eu/download/ECA_blend_tx.zip']
    info = {'tried': []}
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
    ok = False
    for url in urls:
        try:
            with requests.get(url, headers=UA, timeout=600, stream=True) as r:
                info['tried'].append([url, r.status_code])
                if r.status_code != 200:
                    continue
                size = 0
                for chunk in r.iter_content(1 << 20):
                    tmp.write(chunk); size += len(chunk)
                tmp.close()
                info['bytes'] = size; info['url'] = url; ok = True
                break
        except Exception as e:
            info['tried'].append([url, str(e)])
    if not ok:
        REPORT['sources']['ecad_blend_tx'] = info
        return
    z = zipfile.ZipFile(tmp.name)
    names = z.namelist()
    st_txt = z.read('stations.txt').decode('latin-1')
    def dms(v):
        sgn = -1 if v.strip().startswith('-') else 1
        d, m, s_ = [abs(float(x)) for x in v.strip().lstrip('+-').split(':')]
        return sgn * (d + m / 60 + s_ / 3600)
    near = []
    for line in st_txt.splitlines():
        parts = [x.strip() for x in line.split(',')]
        if len(parts) < 6 or not parts[0].isdigit():
            continue
        staid, name, cn, lat, lon, hght = parts[:6]
        if cn != 'GB':
            continue
        la, lo = dms(lat), dms(lon)
        dkm = 6371 * 2 * math.asin(math.sqrt(math.sin(math.radians(la - 51.5074) / 2) ** 2 + math.cos(math.radians(51.5074)) * math.cos(math.radians(la)) * math.sin(math.radians(lo + 0.1278) / 2) ** 2))
        if dkm <= 40:
            near.append({'staid': int(staid), 'name': name, 'lat': round(la, 4), 'lon': round(lo, 4), 'km': round(dkm, 1)})
    rows = []
    for st in near:
        fn = 'TX_STAID%06d.txt' % st['staid']
        if fn not in names:
            st['file'] = 'missing'; continue
        txt = z.read(fn).decode('latin-1')
        n = 0; last = None
        for line in txt.splitlines():
            p = [x.strip() for x in line.split(',')]
            if len(p) < 5 or not p[2].isdigit() or len(p[2]) != 8:
                continue
            date = p[2]
            if int(date[:4]) < FIRST_YEAR or p[4] != '0':
                continue
            rows.append([st['staid'], st['name'], '%s-%s-%s' % (date[:4], date[4:6], date[6:]), int(p[3]) / 10])
            n += 1; last = date
        st['rows'] = n; st['last'] = last
    with open(os.path.join(OUT, 'ecad_london_tx.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['staid', 'station', 'date', 'tx_c'])
        w.writerows(rows)
    try:
        src = z.read('sources.txt').decode('latin-1')
        keep = [l for l in src.splitlines() if any(('%d,' % st['staid']) in l[:12] for st in near)]
        open(os.path.join(OUT, 'ecad_london_sources.txt'), 'w').write('\n'.join(keep))
    except KeyError:
        pass
    info['stations'] = near
    REPORT['sources']['ecad_blend_tx'] = info
    os.unlink(tmp.name)


# ---------------------------------------------------------------- Summaries used by the dashboard
def summarise(rows):
    thr = (28, 30, 32)
    years = range(FIRST_YEAR, NOW.year + 1)
    summ = {}
    for sid, sname in STATIONS.items():
        d = {}
        for s_id, _, date, tmax, tmin, src in rows:
            if s_id != sid:
                continue
            y, m = int(date[:4]), int(date[5:7])
            if 5 <= m <= 9:
                d.setdefault(y, []).append((date, float(tmax), src))
        ann = []
        for y in years:
            vals = d.get(y, [])
            ann.append({'year': y, 'days': len(vals), 'maxTx': round(max(v[1] for v in vals), 1) if vals else None,
                        'hot': {str(t): sum(1 for v in vals if v[1] >= t) for t in thr}})
        latest = max(d) if d else None
        summer = sorted(d.get(latest, [])) if latest else []
        summ[sid] = {'name': sname, 'annual': ann, 'latestYear': latest,
                     'latestSummer': [[v[0], v[1]] for v in summer]}
    # Cross-check: Heathrow daily-derived monthly mean maximum against the Met Office's official monthly value.
    check = []
    try:
        mo = {(int(r['year']), int(r['month'])): r for r in csv.DictReader(open(os.path.join(OUT, 'metoffice_heathrow_monthly.csv')))}
        hd = {}
        for s_id, _, date, tmax, tmin, src in rows:
            if s_id == '03772':
                hd.setdefault((int(date[:4]), int(date[5:7])), []).append(float(tmax))
        for (y, m), vals in sorted(hd.items()):
            if 5 <= m <= 9 and (y, m) in mo and mo[(y, m)]['tmax_mean_c'] and len(vals) >= 25:
                check.append([y, m, float(mo[(y, m)]['tmax_mean_c']), round(sum(vals) / len(vals), 2), len(vals)])
    except Exception as e:
        REPORT['notes'].append('cross-check failed: %s' % e)
    with open(os.path.join(OUT, 'london_summary.json'), 'w') as f:
        json.dump({'generated_utc': REPORT['generated_utc'], 'thresholds': thr, 'stations': summ,
                   'heathrowCheck': {'columns': ['year', 'month', 'metoffice_tmax_mean', 'daily_derived_mean', 'days'], 'rows': check}},
                  f, separators=(',', ':'))


if __name__ == '__main__':
    for step in (metoffice_station, metoffice_region, midas_open, ecad):
        try:
            step()
        except Exception as e:
            REPORT['notes'].append('%s failed: %s' % (step.__name__, e))
    rows = []
    try:
        rows = meteostat()
        summarise(rows)
    except Exception as e:
        REPORT['notes'].append('meteostat failed: %s' % e)
    with open(os.path.join(OUT, 'fetch_report.json'), 'w') as f:
        json.dump(REPORT, f, indent=1)
    print(json.dumps(REPORT, indent=1)[:6000])
