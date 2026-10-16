#!/usr/bin/env python3
"""Daily CelesTrak orbital-catalog snapshots. NOT cumulative launches."""
import json, os, sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
PATH = ROOT / 'data' / 'satellite-history.json'
GROUPS = {'starlink':'STARLINK', 'amazon':'KUIPER', 'oneweb':'ONEWEB'}
BASE = 'https://celestrak.org/NORAD/elements/gp.php?GROUP={}&FORMAT=JSON'

def load():
    if not PATH.exists():
        return {'schema_version':1, 'metric':'gp_catalog_records', 'records':[], 'last_checked':None, 'source':'https://celestrak.org/NORAD/documentation/gp-data-formats.php'}
    d=json.loads(PATH.read_text(encoding='utf-8'))
    if d.get('metric') != 'gp_catalog_records' or not isinstance(d.get('records'),list):
        raise ValueError('Unexpected history schema')
    return d

def retrieve(url):
    req=Request(url,headers={'User-Agent':'OrbitWatchResearchPrototype/0.1 (daily snapshot)'})
    with urlopen(req, timeout=25) as resp:
        if resp.status != 200: raise ValueError('HTTP status '+str(resp.status))
        obj=json.load(resp)
    if not isinstance(obj,list) or not obj: raise ValueError('Empty/invalid source')
    valid={str(x['NORAD_CAT_ID']) for x in obj if isinstance(x,dict) and x.get('NORAD_CAT_ID') is not None and x.get('OBJECT_NAME')}
    if not valid: raise ValueError('No valid catalog entries')
    return len(valid)

def run():
    doc=load()
    today=datetime.now(timezone.utc).strftime('%Y-%m-%d')
    doc['last_checked']=datetime.now(timezone.utc).isoformat(timespec='seconds')
    last=next((r for r in reversed(doc['records']) if r.get('date') == today),None)
    record=dict(last) if last else {'date':today,'counts':{},'sources':{},'errors':{}}
    good=0
    for key,group in GROUPS.items():
        url=BASE.format(group)
        try:
            count=retrieve(url)
            record['counts'][key]=count
            record['sources'][key]=url
            record['errors'].pop(key,None)
            good+=1
        except Exception as e:
            record['errors'][key]=str(e)[:180]
            print(f'{key}: {e}',file=sys.stderr)
    # Persist successful partial results; failures do not replace last known values.
    if good:
        if last: doc['records']=[r if r.get('date')!=today else record for r in doc['records']]
        else: doc['records'].append(record)
        doc['records']=sorted(doc['records'],key=lambda r:r['date'])[-730:]
        PATH.parent.mkdir(parents=True,exist_ok=True)
        PATH.write_text(json.dumps(doc,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Date={today} successful_groups={good}; history_records={len(doc["records"])}')
    if not good: sys.exit(1)

if __name__=='__main__':run()
