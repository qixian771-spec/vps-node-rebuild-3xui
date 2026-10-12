#!/usr/bin/env python3
"""Offline helpers. Never configure a running proxy, firewall, browser or server."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sqlite3
import sys
import time
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parent.parent


class Stop(Exception):
    def __init__(self, code, reason):
        self.code, self.reason = code, reason


def emit(value):
    print(json.dumps(value, ensure_ascii=False, sort_keys=True))


def absolute(value, exists=True, directory=False):
    p = Path(value)
    if not p.is_absolute():
        raise Stop(2, 'absolute_path_required')
    if any(x.is_symlink() for x in (p, *p.parents)):
        raise Stop(2, 'symlink_not_allowed')
    if exists and not (p.is_dir() if directory else p.is_file()):
        raise Stop(3, 'required_path_missing_or_wrong_type')
    return p


def read_json(path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (ValueError, UnicodeError):
        raise Stop(2, 'invalid_json_or_encoding')


def exclusive(path, data):
    absolute(str(path), exists=False)
    if path.exists():
        raise Stop(3, 'destination_exists')
    with path.open('xb') as stream:
        stream.write(data)
    path.chmod(0o600)


def package_files(root):
    root = absolute(str(root), directory=True)
    manifest = read_json(root / 'manifest.json')
    if not isinstance(manifest, dict) or set(manifest) != {'format', 'files'} or manifest['format'] != 1:
        raise Stop(2, 'invalid_manifest')
    files = manifest['files']
    if not isinstance(files, list) or not files or not all(isinstance(x, str) for x in files):
        raise Stop(2, 'invalid_manifest_files')
    if len(set(files)) != len(files) or not {'SKILL.md', 'manifest.json', 'scripts/skillctl.py'} <= set(files):
        raise Stop(2, 'incomplete_or_duplicate_manifest')
    for name in files:
        p = PurePosixPath(name)
        if p.is_absolute() or '..' in p.parts or '\\' in name or str(p) != name:
            raise Stop(2, 'unsafe_manifest_path')
        absolute(str(root / name))
    return files


def validate(root):
    root = absolute(str(root), directory=True)
    files = package_files(root)
    entry = (root / 'SKILL.md').read_text(encoding='utf-8')
    if not entry.startswith('---\n') or '\n---\n' not in entry[4:]:
        raise Stop(2, 'invalid_skill_frontmatter')
    front = entry.split('---', 2)[1]
    if not re.search(r'^name: vps-node-rebuild-3xui$', front, re.M) or not re.search(r'^description: .+', front, re.M):
        raise Stop(2, 'invalid_skill_identity')
    links = 0
    for name in files:
        if not name.endswith('.md'):
            continue
        body = (root / name).read_text(encoding='utf-8')
        # Fenced examples are not installation dependencies. Prose local links are.
        body = re.sub(r'```.*?```', '', body, flags=re.S)
        for href in re.findall(r'\[[^\]]*\]\(([^)]+)\)', body):
            href = href.strip('<>')
            if urlsplit(href).scheme or href.startswith('#'):
                continue
            dest = ((root / name).parent / unquote(href.split('#', 1)[0])).resolve()
            try:
                relative = dest.relative_to(root).as_posix()
            except ValueError:
                raise Stop(2, 'reference_outside_package')
            if relative not in files or not dest.is_file():
                raise Stop(3, 'reference_missing_from_package')
            links += 1
    # The probe's executable resource must also be included in a portable install.
    html = (root / 'assets/webrtc-probe.html').read_text(encoding='utf-8')
    for src in re.findall(r'<script\s+src="([^"]+)"', html):
        if 'assets/' + src not in files:
            raise Stop(3, 'probe_script_missing_from_package')
    return {'status': 'passed', 'files': len(files), 'local_links': links,
            'scope': 'package_structure_only'}


def install(source, destination):
    validate(source)
    dest = absolute(destination, exists=False)
    absolute(str(dest.parent), directory=True)
    if dest.exists():
        raise Stop(3, 'destination_exists_no_overwrite')
    files = package_files(source)
    dest.mkdir(mode=0o700)
    # Keep incomplete output on error. No automatic retry, rollback or deletion.
    for name in files:
        out = dest / name
        out.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        exclusive(out, (source / name).read_bytes())
    result = validate(dest)
    return {**result, 'operation': 'installed', 'overwritten': False}


def preflight(required, inputs, platform_name):
    if platform_name != 'any' and sys.platform != platform_name:
        raise Stop(3, 'unsupported_platform')
    missing = []
    for name in required:
        if not re.fullmatch(r'[A-Za-z0-9_.+-]+', name):
            raise Stop(2, 'require_accepts_command_names_only')
        if shutil.which(name) is None:
            missing.append(name)
    for value in inputs:
        absolute(value)
    if missing:
        raise Stop(3, 'missing_dependencies:' + ','.join(missing))
    return {'status': 'passed', 'scope': 'presence_only_not_version_or_authorization',
            'python': '.'.join(map(str, sys.version_info[:3])), 'platform': sys.platform,
            'dependencies': required, 'input_count': len(inputs), 'euid': os.geteuid()}


def snapshot(source, out_dir):
    src = absolute(source)
    out = absolute(out_dir, exists=False)
    absolute(str(out.parent), directory=True)
    if out.exists():
        raise Stop(3, 'destination_exists_no_overwrite')
    deadline = time.monotonic() + 20
    def progress(status, remaining, total):
        if time.monotonic() > deadline:
            raise Stop(4, 'snapshot_deadline_exceeded_partial_output_retained')
    with sqlite3.connect(src.as_uri() + '?mode=ro', uri=True, timeout=2) as db:
        if db.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
            raise Stop(2, 'database_integrity_failed')
        out.mkdir(mode=0o700)
        target = out / 'snapshot.sqlite3'
        exclusive(target, b'')
        with sqlite3.connect(target) as copy:
            db.backup(copy, pages=64, progress=progress, sleep=0.05)
            if copy.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
                raise Stop(4, 'snapshot_integrity_failed_partial_output_retained')
            schema = {}
            for table in ('inbounds', 'clients', 'client_inbounds', 'client_traffics', 'settings'):
                cols = [r[1] for r in copy.execute('PRAGMA table_info(' + table + ')')]
                schema[table] = {'present': bool(cols), 'column_count': len(cols)}
                if table == 'client_inbounds':
                    schema[table]['has_flow_override'] = 'flow_override' in cols
    return {'status': 'passed', 'scope': 'snapshot_not_runtime_validation', 'schema': schema,
            'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}


def logcheck(source, since, log_timezone, port):
    src = absolute(source)
    try:
        start = dt.datetime.fromisoformat(since.replace('Z', '+00:00'))
        zone = dt.datetime.fromisoformat('2000-01-01T00:00:00' + log_timezone).tzinfo
    except ValueError:
        raise Stop(2, 'invalid_timestamp_or_timezone')
    if start.tzinfo is None or zone is None or not re.fullmatch(r'[+-]\d\d:\d\d', log_timezone):
        raise Stop(2, 'timezone_required')
    if not 1 <= port <= 65535:
        raise Stop(2, 'invalid_port')
    with src.open('rb') as stream:
        stream.seek(0, 2)
        size = stream.tell()
        stream.seek(max(0, size - 1024 * 1024))
        if size > 1024 * 1024:
            stream.readline()  # bounded tail begins at the next full line
        body = stream.read().decode('utf-8')
    events = []
    for line in body.splitlines():
        if '[egress-proxy]' not in line:
            continue
        stamp = re.search(r'\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)?', line)
        if not stamp:
            raise Stop(2, 'proxy_event_timestamp_missing')
        when = dt.datetime.fromisoformat(stamp.group().replace('Z', '+00:00'))
        if when.tzinfo is None:
            when = when.replace(tzinfo=zone)
        if when < start:
            continue
        events.append({'time': when.isoformat(),
                       'fixed_local_proxy': bool(re.search(
                           r'pinned to fixed proxy at 127\.0\.0\.1:' + str(port) + r'(?!\d)', line)),
                       'pac_detected': 'PAC script' in line})
    # A later unexpected proxy message is not masked by an earlier successful one.
    if not events:
        raise Stop(4, 'no_matching_startup_evidence_in_bounded_tail')
    if not events[-1]['fixed_local_proxy'] or any(x['pac_detected'] for x in events):
        raise Stop(4, 'fixed_proxy_not_confirmed')
    return {'status': 'passed', 'scope': 'log_evidence_not_business_or_network_validation',
            'bounded_tail_bytes': min(size, 1024 * 1024), 'events': events}


def render_pf(uid, core_uid, interface, output):
    if uid <= 0 or core_uid != 0 or uid == core_uid:
        raise Stop(2, 'template_requires_nonroot_user_and_verified_root_core')
    if not re.fullmatch(r'utun\d+', interface):
        raise Stop(2, 'verified_utun_name_required')
    out = absolute(output, exists=False)
    absolute(str(out.parent), directory=True)
    text = (ROOT / 'assets/macos-leak-guard.pf.in').read_text(encoding='utf-8')
    text = text.replace('REPLACE_UID', str(uid)).replace('REPLACE_TUN_INTERFACE', interface)
    if 'REPLACE_' in text:
        raise Stop(2, 'unresolved_template_token')
    exclusive(out, text.encode())
    return {'status': 'configured', 'scope': 'file_only_not_loaded_or_persistent'}


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    v = sub.add_parser('validate', help='validate local package links and manifest; offline')
    v.add_argument('--root', default=str(ROOT))
    i = sub.add_parser('install', help='copy complete package into a NEW absolute directory; offline')
    i.add_argument('--source', default=str(ROOT))
    i.add_argument('--destination', required=True)
    f = sub.add_parser('preflight', help='check explicit tool/file presence; no installs, no network')
    f.add_argument('--require', action='append', default=[])
    f.add_argument('--input', action='append', default=[])
    f.add_argument('--platform', choices=['any', 'darwin', 'linux'], default='any')
    b = sub.add_parser('snapshot', help='read-only SQLite source; create a private consistent snapshot')
    b.add_argument('--source', required=True)
    b.add_argument('--output-dir', required=True)
    l = sub.add_parser('logcheck', help='bounded single-file Claude startup evidence; no raw log output')
    l.add_argument('--source', required=True)
    l.add_argument('--since', required=True)
    l.add_argument('--log-timezone', required=True)
    l.add_argument('--port', type=int, required=True)
    r = sub.add_parser('render-pf', help='render optional template only; NEVER load PF')
    r.add_argument('--uid', type=int, required=True)
    r.add_argument('--core-uid', type=int, required=True)
    r.add_argument('--tun', required=True)
    r.add_argument('--output', required=True)
    return p


def main():
    os.umask(0o077)
    if sys.version_info < (3, 10):
        emit({'status': 'stopped', 'reason': 'python_3_10_required', 'exit': 3})
        return 3
    args = parser().parse_args()
    try:
        if args.command == 'validate':
            result = validate(Path(args.root))
        elif args.command == 'install':
            result = install(absolute(args.source, directory=True), args.destination)
        elif args.command == 'preflight':
            result = preflight(args.require, args.input, args.platform)
        elif args.command == 'snapshot':
            result = snapshot(args.source, args.output_dir)
        elif args.command == 'logcheck':
            result = logcheck(args.source, args.since, args.log_timezone, args.port)
        elif args.command == 'render-pf':
            result = render_pf(args.uid, args.core_uid, args.tun, args.output)
        emit(result)
        return 0
    except Stop as exc:
        emit({'status': 'stopped', 'exit': exc.code, 'reason': exc.reason})
        return exc.code
    except PermissionError:
        emit({'status': 'stopped', 'exit': 5, 'reason': 'permission_denied_partial_output_may_remain'})
        return 5
    except (ValueError, UnicodeError, sqlite3.DatabaseError):
        emit({'status': 'stopped', 'exit': 2, 'reason': 'invalid_input_partial_output_may_remain'})
        return 2
    except OSError:
        emit({'status': 'stopped', 'exit': 3, 'reason': 'filesystem_error_partial_output_may_remain'})
        return 3
    except Exception:
        # Report unexpected failure without disclosing input or credentials.
        emit({'status': 'stopped', 'exit': 6, 'reason': 'unexpected_internal_error_no_retry'})
        return 6


if __name__ == '__main__':
    sys.exit(main())
