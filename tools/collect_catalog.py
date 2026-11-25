"""Read-only public catalog builder; shared pagination, Hub-specific publication evidence."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from devflow_mapped_read import MappedReadError
from devflow_mapped_read.github_pages import read_linked_rows
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
OWNER = 'kinoko34077'
API = 'https://api.github.com'
PAGES = 'https://kinoko34077.github.io'
WORKER = 'https://standby-display.kinotch.workers.dev'
PER_PAGE = 100
MAX_PAGES = 10
MAX_BODY = 2 * 1024 * 1024
TTL = timedelta(days=3)
REPO = re.compile(r'[A-Za-z0-9._-]+\Z')
KEY = re.compile(r'[a-z0-9][a-z0-9-]*\Z')
SAFE_PATH = re.compile(r'/[A-Za-z0-9._/-]*\Z')


class CatalogError(ValueError):
    """Fixed diagnostics, never echo upstream bodies or untrusted strings."""


class ProbeUnavailable(CatalogError):
    """Transient network/HTTP failure, distinct from invalid local definitions."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request(url, accept, *, missing_codes=(404, 410), api_auth=False):
    # Only callers with fixed API paths or validated publication URLs enter.
    headers = {'User-Agent': 'kinotch-hub-public-catalog', 'Accept': accept}
    if api_auth:
        if not re.fullmatch(re.escape(API) + r'/users/kinoko34077/repos\?[A-Za-z0-9=&_-]+', url):
            raise CatalogError('INVALID_AUTH_DESTINATION')
        token = os.environ.get('GITHUB_TOKEN')
        if token:
            headers['Authorization'] = 'Bearer ' + token
    try:
        with build_opener(NoRedirect()).open(
            Request(url, headers=headers), timeout=12
        ) as response:
            if response.status != 200:
                raise ProbeUnavailable('UNEXPECTED_HTTP_STATUS')
            body = response.read(MAX_BODY + 1)
            if len(body) > MAX_BODY:
                raise ProbeUnavailable('RESPONSE_LIMIT')
            return body, response.headers.get_content_type(), response.headers.get('Link', '')
    except HTTPError as error:
        if error.code in missing_codes:
            error.close()
            return None
        error.close()
        raise ProbeUnavailable('UPSTREAM_HTTP_' + str(error.code)) from None
    except (URLError, TimeoutError, OSError):
        raise ProbeUnavailable('UPSTREAM_TRANSPORT_FAILURE') from None


def get_api_page(path):
    if not re.fullmatch(r'/users/kinoko34077/repos\?[A-Za-z0-9=&_-]+', path):
        raise CatalogError('INVALID_API_PATH')
    result = request(API + path, 'application/vnd.github+json', api_auth=True)
    if result is None:
        raise CatalogError('PUBLIC_LIST_UNAVAILABLE')
    body, _, link = result
    try:
        return json.loads(body), link
    except (ValueError, UnicodeError):
        raise CatalogError('INVALID_API_JSON') from None


def repository_path(page):
    return '/users/' + OWNER + '/repos?' + urlencode(
        {'type': 'owner', 'sort': 'full_name', 'direction': 'asc',
         'per_page': PER_PAGE, 'page': page})


def stamp(value):
    return value.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def normalize_repositories(rows, observed):
    result, seen_ids, seen_names = [], set(), set()
    for row in rows:
        if not isinstance(row, dict) or row.get('private') is not False or row.get('visibility') != 'public':
            raise CatalogError('NON_PUBLIC_REPOSITORY')
        owner = row.get('owner')
        name = row.get('name')
        ident = row.get('id')
        if (not isinstance(owner, dict) or owner.get('login') != OWNER
                or not isinstance(name, str) or not REPO.fullmatch(name)
                or name in ('.', '..') or row.get('full_name') != OWNER + '/' + name
                or type(ident) is not int or ident <= 0
                or type(row.get('archived')) is not bool
                or type(row.get('has_pages')) is not bool):
            raise CatalogError('INVALID_REPOSITORY')
        ident = str(ident)
        if ident in seen_ids or name.casefold() in seen_names:
            raise CatalogError('DUPLICATE_REPOSITORY')
        seen_ids.add(ident)
        seen_names.add(name.casefold())
        # Do not carry API descriptions, arbitrary homepage values or raw records
        # into the distributed snapshot. They are not publication authority.
        result.append(({'id': ident, 'fullName': OWNER + '/' + name,
                        'visibility': 'public', 'archived': row['archived'],
                        'observedAt': observed}, row['has_pages']))
    return sorted(result, key=lambda item: item[0]['fullName'].casefold())


def safe_url(value, base, relative_to=None):
    """Restrict network and output URLs to the exact approved origin/path prefix.
    No query, fragment, credentials, escaped path, or redirect traversal.
    """
    if not isinstance(value, str) or not value or len(value) > 1024 or re.search(r'[\s\\%]', value):
        return None
    try:
        target = urljoin(relative_to or base, value)
        p, b = urlsplit(target), urlsplit(base)
        if (p.scheme != 'https' or p.netloc != b.netloc or p.query or p.fragment
                or not SAFE_PATH.fullmatch(p.path) or '//' in p.path
                or any(x in ('.', '..') for x in p.path.split('/'))
                or not p.path.startswith(b.path)):
            return None
    except ValueError:
        return None
    return target


def probe(url, kind):
    result = request(url, {'html': 'text/html', 'manifest': 'application/manifest+json, application/json',
                           'image': 'image/*'}[kind], missing_codes=(410,))
    if result is None:
        return None
    body, media_type, _ = result
    if kind == 'html' and media_type not in ('text/html', 'application/xhtml+xml'):
        raise ProbeUnavailable('UNEXPECTED_HTML_MEDIA_TYPE')
    if kind == 'manifest' and media_type not in ('application/manifest+json', 'application/json'):
        return None
    if kind == 'image' and media_type not in ('image/png', 'image/svg+xml', 'image/jpeg', 'image/webp', 'image/x-icon', 'image/vnd.microsoft.icon'):
        return None
    return body


class PublicationMetadata(HTMLParser):
    def __init__(self):
        super().__init__()
        self.href = None
        self.app_name = None
        self.icons = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'meta' and (a.get('name') or '').lower() == 'application-name' and self.app_name is None:
            self.app_name = a.get('content')
        if tag == 'link':
            rel = (a.get('rel') or '').lower().split()
            if 'manifest' in rel and self.href is None:
                self.href = a.get('href')
            if ('icon' in rel or 'apple-touch-icon' in rel) and a.get('href') and len(self.icons) < 8:
                self.icons.append(a['href'])


def title_text(value):
    return (value.strip() if isinstance(value, str) and 0 < len(value.strip()) <= 100
            and not any(ord(c) < 32 for c in value) else None)


def icon_available(url, get):
    # Optional artwork failures must not invalidate otherwise confirmed apps.
    try:
        return get(url, 'image') is not None
    except CatalogError:
        return False


def html_metadata(html):
    parser = PublicationMetadata()
    try:
        parser.feed(html.decode('utf-8', errors='replace'))
    except ValueError:
        return PublicationMetadata()
    return parser


def html_icon(base, metadata, get, page_url=None):
    for ref in metadata.icons:
        url = safe_url(ref, base, relative_to=page_url)
        if url and icon_available(url, get):
            return url
    return None


def manifest_app(base, html, get):
    """Positive publication metadata; installability/display mode is not an app condition."""
    metadata = html_metadata(html)
    link = safe_url(metadata.href, base)
    title = title_text(metadata.app_name)
    icons = []
    if link:
        try:
            raw = get(link, 'manifest')
        except ProbeUnavailable:
            if not title:
                raise
            raw = None
        try:
            manifest = json.loads(raw) if raw is not None else None
        except (ValueError, UnicodeError):
            manifest = None
        if isinstance(manifest, dict):
            manifest_title = title_text(manifest.get('short_name')) or title_text(manifest.get('name'))
            start = safe_url(manifest.get('start_url'), base, relative_to=link)
            if manifest_title and start:
                title = manifest_title
                icons = manifest.get('icons', [])
    if not title:
        return None
    app = {'title': title, 'canonicalUrl': base, 'kind': 'application'}
    if isinstance(icons, list):
        for icon in icons[:8]:
            if not isinstance(icon, dict) or not isinstance(icon.get('src'), str):
                continue
            url = safe_url(icon['src'], base, relative_to=link)
            if url and icon_available(url, get):
                app['iconUrl'] = url
                break
    if 'iconUrl' not in app:
        icon = html_icon(base, metadata, get)
        if icon:
            app['iconUrl'] = icon
    return app


def curated_url(definition, base, has_pages):
    target = definition.get('target')
    if target == 'pages':
        if not has_pages:
            return None
        url = safe_url(definition.get('path') or base, base)
    elif target == 'worker' and definition.get('url') == WORKER + '/':
        url = WORKER + '/'
    else:
        raise CatalogError('INVALID_CURATED_TARGET')
    if not url:
        raise CatalogError('INVALID_CURATED_TARGET')
    return url


def curated_app(definition, base, url, get):
    title, kind = title_text(definition.get('title')), definition.get('kind')
    if not url or not title or kind not in ('application', 'demo', 'preview', 'documentation'):
        raise CatalogError('INVALID_CURATED_APP')
    html = get(url, 'html')
    if html is None:
        return None
    app = {'title': title, 'canonicalUrl': url, 'kind': kind}
    icon = definition.get('icon')
    if icon:
        icon = safe_url(icon, base)
        if icon is None:
            raise CatalogError('INVALID_CURATED_ICON')
        if icon_available(icon, get):
            app['iconUrl'] = icon
    if 'iconUrl' not in app:
        icon = html_icon(base, html_metadata(html), get, page_url=url)
        if icon:
            app['iconUrl'] = icon
    return app


def discover(repos, definitions, observed, get, previous=None):
    # The complete current public repository list controls eligibility.
    # A transient probe error must not revoke a previously confirmed URL.
    old_by_id = {a['id']: a for a in (previous or {}).get('applications', [])}
    retained = 0

    def retain(ident, repo, url, basis):
        nonlocal retained
        old = old_by_id.get(ident)
        if (old is not None and old['repositoryId'] == repo['id']
                and old['canonicalUrl'] == url and old['publication']['basis'] == basis):
            retained += 1
            # Preserve the original observation, never claim a new confirmation.
            return old
        return None

    def confirmed(app, ident, repo, basis):
        return dict(app, id=ident, repositoryId=repo['id'],
                    publication={'basis': basis, 'observedAt': observed})

    by_id, seen_keys = {}, set()
    for entry in definitions:
        if not isinstance(entry, dict) or not isinstance(entry.get('repositoryId'), str):
            raise CatalogError('INVALID_CURATED_DEFINITION')
        ident, key = entry['repositoryId'], entry.get('key')
        if not isinstance(key, str) or not KEY.fullmatch(key) or (ident, key) in seen_keys:
            raise CatalogError('DUPLICATE_OR_INVALID_APP_KEY')
        seen_keys.add((ident, key))
        by_id.setdefault(ident, []).append(entry)
    apps = []
    for repo, has_pages in repos:
        name = repo['fullName'].split('/')[1]
        if name.casefold() == 'kinotch-hub':
            continue
        base = PAGES + '/' + name + '/'
        entries = by_id.get(repo['id'], [])
        if entries:
            for entry in entries:
                url = curated_url(entry, base, has_pages)
                if url is None:
                    continue
                ident = 'repo:' + repo['id'] + ':' + entry['key']
                basis = 'github-pages' if entry['target'] == 'pages' else 'public-deployment'
                try:
                    app = curated_app(entry, base, url, get)
                    app = confirmed(app, ident, repo, basis) if app else None
                except ProbeUnavailable:
                    app = retain(ident, repo, url, basis)
                if app:
                    apps.append(app)
        elif has_pages:
            ident, basis = 'repo:' + repo['id'] + ':main', 'github-pages'
            try:
                html = get(base, 'html')
                app = manifest_app(base, html, get) if html is not None else None
                if app:
                    app = confirmed(app, ident, repo, basis)
                elif html is not None:
                    # A reachable HTML page losing manifest evidence is not
                    # positive evidence of withdrawal of its former app.
                    app = retain(ident, repo, base, basis)
            except ProbeUnavailable:
                app = retain(ident, repo, base, basis)
            if app:
                apps.append(app)
    if retained:
        print('Retained last confirmed applications=' + str(retained))
    return apps


def validate_snapshot(data):
    schema = json.loads((ROOT / 'schemas/catalog-snapshot.v1.schema.json').read_text(encoding='utf-8'))
    if not Draft202012Validator(schema, format_checker=FormatChecker()).is_valid(data):
        raise CatalogError('INVALID_SNAPSHOT_SHAPE')
    repos = {r['id']: r for r in data['repositories']}
    if len(repos) != len(data['repositories']):
        raise CatalogError('DUPLICATE_REPOSITORY')
    if len({r['fullName'].casefold() for r in repos.values()}) != len(repos):
        raise CatalogError('DUPLICATE_REPOSITORY_NAME')
    generated = datetime.fromisoformat(data['generatedAt'])
    expires = datetime.fromisoformat(data['validUntil'])
    if expires <= generated or expires - generated > TTL:
        raise CatalogError('INVALID_SNAPSHOT_TIME')
    ids, urls = set(), set()
    for repo in repos.values():
        if datetime.fromisoformat(repo['observedAt']) > generated:
            raise CatalogError('FUTURE_OBSERVATION')
    for app in data['applications']:
        repo = repos.get(app['repositoryId'])
        if (repo is None or not app['id'].startswith('repo:' + repo['id'] + ':')
                or repo['fullName'].casefold() == OWNER + '/kinotch-hub'):
            raise CatalogError('INVALID_APP_REFERENCE')
        base = PAGES + '/' + repo['fullName'].split('/')[1] + '/'
        url = app['canonicalUrl']
        if safe_url(url, base) != url and not (url == WORKER + '/' and repo['id'] == '969335914'):
            raise CatalogError('UNAPPROVED_URL')
        if app.get('iconUrl') and safe_url(app['iconUrl'], base) != app['iconUrl']:
            raise CatalogError('UNAPPROVED_ICON')
        if app['id'] in ids or url in urls:
            raise CatalogError('DUPLICATE_APPLICATION')
        if datetime.fromisoformat(app['publication']['observedAt']) > generated:
            raise CatalogError('FUTURE_OBSERVATION')
        ids.add(app['id'])
        urls.add(url)


def collect(definitions, get_page=get_api_page, get=probe, now=None, previous=None):
    if previous is not None:
        validate_snapshot(previous)
    now = now or datetime.now(timezone.utc)
    observed = stamp(now)
    rows = read_linked_rows(repository_path, get_page, per_page=PER_PAGE, max_pages=MAX_PAGES)
    repos = normalize_repositories(rows, observed)
    apps = discover(repos, definitions, observed, get, previous)
    # The generation clock is after observations in live mode.
    generated = max(now, datetime.now(timezone.utc)) if get_page is get_api_page else now
    data = {'schemaVersion': 1, 'generatedAt': stamp(generated),
            'validUntil': stamp(generated + TTL), 'repositories': [r for r, _ in repos],
            'applications': sorted(apps, key=lambda app: app['id'])}
    validate_snapshot(data)
    return data


def write_atomic(path, data):
    validate_snapshot(data)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', dir=path.parent, encoding='utf-8', delete=False) as f:
        temporary = Path(f.name)
        try:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write('\n')
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_previous():
    # The existing public deployment is the last-good source; no new store,
    # credentials, arbitrary fetch or write-back mechanism.
    result = request(PAGES + '/kinotch-hub/catalog.json', 'application/json')
    if result is None:
        return None
    body, media_type, _ = result
    if media_type != 'application/json':
        raise CatalogError('INVALID_PREVIOUS_MEDIA_TYPE')
    try:
        previous = json.loads(body)
    except (ValueError, UnicodeError):
        raise CatalogError('INVALID_PREVIOUS_JSON') from None
    validate_snapshot(previous)
    return previous


def collect_with_recovery(definitions, previous, allow_last_good, get_page=get_api_page, get=probe, now=None):
    try:
        return collect(definitions, get_page, get, now, previous), False
    except (ProbeUnavailable, MappedReadError):
        # Network/pagination failure is not an empty public list. Do not
        # fallback on integrity or explicit non-public repository errors.
        if not allow_last_good or previous is None:
            raise
        validate_snapshot(previous)
        return previous, True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--allow-last-good', action='store_true')
    args = parser.parse_args()
    try:
        definitions = json.loads((ROOT / 'catalog/public-apps.json').read_text(encoding='utf-8'))
        previous = read_previous()
        data, fallback = collect_with_recovery(definitions, previous, args.allow_last_good)
        write_atomic(args.output, data)
    except CatalogError as error:
        parser.exit(1, 'Public catalog collection incomplete or invalid (' + str(error) + '); no new snapshot written.\n')
    except MappedReadError:
        parser.exit(1, 'Public catalog pagination incomplete; no new snapshot written.\n')
    if fallback:
        print('WARNING: public list unavailable; using unchanged last-good snapshot (not a new observation).')
    print(('Last-good catalog validated: repositories=' if fallback else 'Public catalog validated: repositories=') + str(len(data['repositories'])) +
          ' applications=' + str(len(data['applications'])))


if __name__ == '__main__':
    main()
