# Saves a client's uploads (logo, photos, style files) from their Tally submission into this repo,
# so the Build Bay can use them on the final site.
# A job file incoming/<slug>.json holds only {"slug": "...", "form": "q5Zyxg", "submission": "<submission id>"}.
# File links are looked up with the Tally API key stored as the repository secret TALLY_API_KEY,
# so no private links or keys are ever written into this public repo.
import json, os, glob, re, urllib.request, datetime

KEY = os.environ.get('TALLY_API_KEY', '')

def get(url, auth=True):
    h = {'User-Agent': 'Mozilla/5.0'}
    if auth:
        h['Authorization'] = 'Bearer ' + KEY
    return urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=60).read()

def find_submission(form, sid):
    d = json.loads(get(f'https://api.tally.so/forms/{form}/submissions/{sid}'))
    qs = {q['id']: q for q in d.get('questions', [])}
    return qs, d.get('submission')

def kind(label):
    l = (label or '').lower()
    if 'logo' in l: return 'logo'
    if 'style' in l or 'anything else' in l: return 'style'
    if 'change' in l: return 'change'
    return 'photo'

def ext(name, mime):
    m = re.search(r'\.([A-Za-z0-9]{2,5})$', name or '')
    if m: return m.group(1).lower()
    return {'image/png': 'png', 'image/jpeg': 'jpg', 'image/webp': 'webp', 'image/svg+xml': 'svg', 'application/pdf': 'pdf'}.get(mime, 'bin')

for f in sorted(glob.glob('incoming/*.json')):
    job = json.load(open(f))
    slug = re.sub(r'[^a-z0-9-]', '', job.get('slug', ''))
    res = {'slug': slug, 'submission': job.get('submission'), 'at': datetime.datetime.utcnow().isoformat() + 'Z', 'files': []}
    try:
        if not KEY: raise RuntimeError('TALLY_API_KEY secret is missing')
        if not slug: raise RuntimeError('missing slug')
        qs, sub = find_submission(job.get('form', 'q5Zyxg'), job.get('submission'))
        if not sub: raise RuntimeError('submission not found')
        counts = {}
        for r in sub.get('responses', []):
            ans = r.get('answer')
            if not isinstance(ans, list): continue
            q = qs.get(r.get('questionId')) or {}
            label = q.get('title') or q.get('label') or ''
            for a in ans:
                if not (isinstance(a, dict) and a.get('url')): continue
                k = kind(label); counts[k] = counts.get(k, 0) + 1
                name = 'logo' if k == 'logo' and counts[k] == 1 else f'{k}-{counts[k]}'
                dest = f'{slug}/assets/{name}.{ext(a.get("name"), a.get("mimeType"))}'
                try:
                    data = get(a['url'], auth=False)
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    open(dest, 'wb').write(data)
                    res['files'].append({'kind': k, 'question': label, 'name': a.get('name'), 'path': dest, 'bytes': len(data), 'ok': True})
                except Exception as e:
                    res['files'].append({'kind': k, 'question': label, 'name': a.get('name'), 'ok': False, 'error': str(e)[:200]})
        res['ok'] = all(x['ok'] for x in res['files'])
    except Exception as e:
        res['ok'] = False; res['error'] = str(e)[:300]
    os.makedirs('incoming/done', exist_ok=True)
    json.dump(res, open('incoming/done/' + os.path.basename(f), 'w'), indent=1)
    os.remove(f)
    print(json.dumps(res))
