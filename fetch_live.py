"""Stáhne stanici ČHMÚ Cheb a METAR/TAF LKKV a uloží je do live.json (spouští GitHub Actions)."""
import json, urllib.request, datetime as dt

WSI = '0-20000-0-11406'
BASE = 'https://opendata.chmi.cz/meteorology/climate/now/data/'
UA = {'User-Agent': 'meteo-vfr-live/1.0 (osobni pouziti)'}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read().decode('utf-8')


def find_table(o):
    if isinstance(o, dict):
        if isinstance(o.get('header'), str) and isinstance(o.get('values'), list):
            return o
        o = list(o.values())
    if isinstance(o, list):
        for v in o:
            t = find_table(v)
            if t:
                return t
    return None


def latest(url):
    j = json.loads(get(url))
    t = find_table(j)
    if not t:
        raise ValueError('neznámý formát souboru, klíče: ' + str(list(j)[:6] if isinstance(j, dict) else type(j)))
    H = [h.strip() for h in t['header'].split(',')]
    try:
        iE, iT, iV = H.index('EG_EL_ABBREVIATION'), H.index('DT'), H.index('VAL')
    except ValueError:
        raise ValueError('neočekávaná hlavička: ' + t['header'])
    out = {}
    for r in t['values']:
        e, d = r[iE], r[iT]
        if e not in out or d > out[e][0]:
            out[e] = (d, r[iV])
    return out


now = dt.datetime.now(dt.timezone.utc)
out = {'updated': now.isoformat(timespec='seconds')}

o, err, day = None, '', None
for delta in (0, 1):  # těsně po půlnoci UTC může být dnešní soubor ještě prázdný
    day = (now - dt.timedelta(days=delta)).strftime('%Y%m%d')
    try:
        o = latest(f'{BASE}10m-{WSI}-{day}.json')
        break
    except Exception as e:
        err = f'{type(e).__name__}: {e}'
if o:
    g = lambda k: o[k][1] if k in o else None
    out['chmi'] = {'dt': (o.get('F') or o.get('D') or (None,))[0],
                   'dir': g('D'), 'spd': g('F'), 'gust': g('Fmax'), 'temp': g('T')}
    try:
        c = latest(f'{BASE}1h-{WSI}-{day}.json')
        if 'C-H1Av' in c:
            out['chmi']['ceil'] = {'h': c['C-H1Av'][1], 'c': c.get('C-C1Co', (None, None))[1], 'dt': c['C-H1Av'][0]}
    except Exception:
        pass
else:
    out['chmi_error'] = err

for key, url in (('metar', 'https://aviationweather.gov/api/data/metar?ids=LKKV&format=raw&hours=3'),
                 ('taf', 'https://aviationweather.gov/api/data/taf?ids=LKKV&format=raw')):
    try:
        txt = get(url).strip()
        if txt:
            out[key] = txt
        else:
            out[key + '_error'] = 'prázdná odpověď'
    except Exception as e:
        out[key + '_error'] = f'{type(e).__name__}: {e}'

with open('live.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False)[:600])
