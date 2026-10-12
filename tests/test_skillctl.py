import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/skillctl.py'
spec = importlib.util.spec_from_file_location('skillctl', SCRIPT)
ctl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ctl)


class Helpers(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='skill-contract-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()

    def run_cli(self, *args, env=None, script=SCRIPT):
        return subprocess.run([sys.executable, str(script), *map(str, args)],
                              capture_output=True, text=True, env=env, timeout=30)

    def assert_exit(self, result, code):
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return json.loads(result.stdout) if result.stdout else None

    def synthetic_db(self):
        path = self.base / 'source.sqlite3'
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE clients(id INTEGER PRIMARY KEY, secret TEXT)')
            db.execute('INSERT INTO clients VALUES (1, ?)', ('SYNTHETIC-DO-NOT-PRINT',))
            db.execute('CREATE TABLE client_inbounds(client_id INT, inbound_id INT, flow_override TEXT)')
        return path

    def test_package_install_and_installed_entrypoint(self):
        self.assert_exit(self.run_cli('validate'), 0)
        destination = self.base / 'installed'
        result = self.assert_exit(self.run_cli('install', '--destination', destination), 0)
        self.assertFalse(result['overwritten'])
        installed = destination / 'scripts/skillctl.py'
        self.assert_exit(self.run_cli('validate', script=installed), 0)
        self.assert_exit(self.run_cli('render-pf', '--uid', '501', '--core-uid', '0',
                                      '--tun', 'utun77', '--output', self.base / 'installed.pf', script=installed), 0)
        for name in ctl.package_files(ROOT):
            self.assertEqual((ROOT / name).read_bytes(), (destination / name).read_bytes())
        self.assertEqual(destination.stat().st_mode & 0o777, 0o700)
        self.assertEqual((destination / 'SKILL.md').stat().st_mode & 0o777, 0o600)
        self.assertFalse((destination / '.git').exists())
        self.assert_exit(self.run_cli('install', '--destination', destination), 3)

    def test_existing_install_is_not_overwritten(self):
        dest = self.base / 'existing'
        dest.mkdir()
        marker = dest / 'SKILL.md'
        marker.write_text('user local changes')
        self.assert_exit(self.run_cli('install', '--destination', dest), 3)
        self.assertEqual(marker.read_text(), 'user local changes')

    def test_partial_install_is_retained_and_not_validated(self):
        dest = self.base / 'partial'
        original = ctl.exclusive
        calls = []
        def fail_third(path, data):
            calls.append(path)
            if len(calls) == 3:
                raise PermissionError('synthetic failure')
            original(path, data)
        with mock.patch.object(ctl, 'exclusive', fail_third):
            with self.assertRaises(PermissionError):
                ctl.install(ROOT, str(dest))
        self.assertTrue((dest / 'SKILL.md').is_file())
        self.assert_exit(self.run_cli('validate', '--root', dest), 3)
        self.assert_exit(self.run_cli('install', '--destination', dest), 3)

    def test_missing_dependency_does_not_install_or_switch(self):
        result = self.run_cli('preflight', '--require', 'certainly-missing-skill-test-command',
                              env={**os.environ, 'PATH': str(self.base)})
        self.assert_exit(result, 3)
        self.assertIn('missing_dependencies', result.stdout)
        self.assertEqual(list(self.base.iterdir()), [])

    def test_preflight_readonly_and_platform(self):
        source = self.base / 'input'
        source.write_text('unchanged')
        before = source.read_bytes()
        self.assert_exit(self.run_cli('preflight', '--input', source, '--platform', sys.platform), 0)
        self.assertEqual(source.read_bytes(), before)
        other = 'linux' if sys.platform == 'darwin' else 'darwin'
        self.assert_exit(self.run_cli('preflight', '--platform', other), 3)

    def test_bad_paths_no_creation(self):
        self.assert_exit(self.run_cli('snapshot', '--source', self.base / 'missing',
                                      '--output-dir', self.base / 'backup'), 3)
        self.assertFalse((self.base / 'missing').exists())
        self.assertFalse((self.base / 'backup').exists())
        self.assert_exit(self.run_cli('preflight', '--input', 'relative'), 2)
        source = self.base / 'file'
        source.write_text('content')
        link = self.base / 'link'
        link.symlink_to(source)
        self.assert_exit(self.run_cli('preflight', '--input', link), 2)

    def test_snapshot_consistency_privacy_and_no_overwrite(self):
        src = self.synthetic_db()
        before = hashlib.sha256(src.read_bytes()).hexdigest()
        out = self.base / 'backup'
        result = self.run_cli('snapshot', '--source', src, '--output-dir', out)
        value = self.assert_exit(result, 0)
        self.assertNotIn('SYNTHETIC-DO-NOT-PRINT', result.stdout + result.stderr)
        self.assertTrue(value['schema']['client_inbounds']['has_flow_override'])
        self.assertEqual(hashlib.sha256(src.read_bytes()).hexdigest(), before)
        with sqlite3.connect(out / 'snapshot.sqlite3') as db:
            self.assertEqual(db.execute('SELECT secret FROM clients').fetchone()[0], 'SYNTHETIC-DO-NOT-PRINT')
        self.assertEqual(out.stat().st_mode & 0o777, 0o700)
        self.assertEqual((out / 'snapshot.sqlite3').stat().st_mode & 0o777, 0o600)
        self.assert_exit(self.run_cli('snapshot', '--source', src, '--output-dir', out), 3)

    def test_corrupt_database_stops_before_backup_creation(self):
        src = self.base / 'corrupt'
        src.write_bytes(b'not a sqlite database')
        dest = self.base / 'backup'
        self.assert_exit(self.run_cli('snapshot', '--source', src, '--output-dir', dest), 2)
        self.assertFalse(dest.exists())

    def test_snapshot_captures_uncheckpointed_wal(self):
        src = self.synthetic_db()
        db = sqlite3.connect(src)
        self.addCleanup(db.close)
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('UPDATE clients SET secret=?', ('WAL-COMMITTED',))
        db.commit()
        out = self.base / 'wal-backup'
        self.assert_exit(self.run_cli('snapshot', '--source', src, '--output-dir', out), 0)
        with sqlite3.connect(out / 'snapshot.sqlite3') as snap:
            self.assertEqual(snap.execute('SELECT secret FROM clients').fetchone()[0], 'WAL-COMMITTED')

    @unittest.skipIf(os.geteuid() == 0, 'actual permission denial requires non-root test user')
    def test_actual_permission_denied(self):
        parent = self.base / 'readonly'
        parent.mkdir()
        parent.chmod(0o500)
        self.addCleanup(parent.chmod, 0o700)
        result = self.run_cli('install', '--destination', parent / 'install')
        self.assert_exit(result, 5)
        self.assertFalse((parent / 'install').exists())

    def test_log_evidence_and_timezones_without_secret_output(self):
        log = self.base / 'events'
        log.write_text('2026-10-12 09:00:00 [egress-proxy] pinned to fixed proxy at 127.0.0.1:7899 SYNTHETIC-SECRET\n')
        result = self.run_cli('logcheck', '--source', log, '--since', '2026-10-12T00:30:00Z',
                              '--log-timezone=+08:00', '--port', '7899')
        self.assert_exit(result, 0)
        self.assertNotIn('SYNTHETIC-SECRET', result.stdout + result.stderr)
        self.assert_exit(self.run_cli('logcheck', '--source', log, '--since', '2026-10-12T02:00:00Z',
                                      '--log-timezone=+08:00', '--port', '7899'), 4)

    def test_log_not_found_wrong_port_pac_and_corruption(self):
        log = self.base / 'events'
        args = ('logcheck', '--source', log, '--since', '2026-10-12T00:00:00Z', '--log-timezone=+00:00', '--port', '7890')
        self.assert_exit(self.run_cli(*args), 3)
        for content, code in [
            ('no proxy events', 4),
            ('2026-10-12 01:00:00 [egress-proxy] pinned to fixed proxy at 127.0.0.1:78901', 4),
            ('2026-10-12 01:00:00 [egress-proxy] PAC script', 4),
            ('[egress-proxy] no timestamp', 2),
        ]:
            log.write_text(content)
            self.assert_exit(self.run_cli(*args), code)
        log.write_bytes(b'\xff')
        self.assert_exit(self.run_cli(*args), 2)

    def test_pf_only_creates_private_file(self):
        dest = self.base / 'guard.pf'
        args = ('render-pf', '--uid', '501', '--core-uid', '0', '--tun', 'utun77', '--output', dest)
        result = self.assert_exit(self.run_cli(*args), 0)
        self.assertEqual(result['status'], 'configured')
        self.assertNotIn('REPLACE_', dest.read_text())
        self.assertIn('on utun77', dest.read_text())
        self.assertEqual(dest.stat().st_mode & 0o777, 0o600)
        self.assert_exit(self.run_cli(*args), 3)
        for uid, core, tun in [('0','0','utun77'), ('501','501','utun77'), ('501','0','en0;id')]:
            self.assert_exit(self.run_cli('render-pf', '--uid', uid, '--core-uid', core,
                                          '--tun', tun, '--output', self.base / 'bad'), 2)
        self.assertFalse((self.base / 'bad').exists())

    def test_manifest_traversal_missing_links_and_broken_json(self):
        dest = self.base / 'install'
        ctl.install(ROOT, str(dest))
        manifest = dest / 'manifest.json'
        original = manifest.read_text()
        value = json.loads(original)
        value['files'].append('../outside')
        manifest.write_text(json.dumps(value))
        self.assert_exit(self.run_cli('validate', '--root', dest), 2)
        manifest.write_text('{broken')
        self.assert_exit(self.run_cli('validate', '--root', dest), 2)
        manifest.write_text(original)
        (dest / 'references/runbook.md').unlink()
        self.assert_exit(self.run_cli('validate', '--root', dest), 3)

    def test_reference_must_be_in_install_manifest(self):
        dest = self.base / 'install'
        ctl.install(ROOT, str(dest))
        manifest = dest / 'manifest.json'
        value = json.loads(manifest.read_text())
        value['files'].remove('references/runbook.md')
        manifest.write_text(json.dumps(value))
        self.assert_exit(self.run_cli('validate', '--root', dest), 3)

    def test_offline_helpers_do_not_open_network_or_launch_targets(self):
        with mock.patch('socket.socket', side_effect=AssertionError('network forbidden')), \
             mock.patch('subprocess.Popen', side_effect=AssertionError('target launch forbidden')):
            self.assertEqual(ctl.validate(ROOT)['status'], 'passed')
            self.assertEqual(ctl.preflight([], [], 'any')['status'], 'passed')
            ctl.install(ROOT, str(self.base / 'offline-install'))
            ctl.render_pf(501, 0, 'utun77', str(self.base / 'offline.pf'))

    def test_log_later_unconfirmed_event_does_not_reuse_old_success(self):
        log = self.base / 'events'
        log.write_text('2026-10-12T00:01:00Z [egress-proxy] pinned to fixed proxy at 127.0.0.1:7890\n'
                       '2026-10-12T00:02:00Z [egress-proxy] another mode\n')
        self.assert_exit(self.run_cli('logcheck', '--source', log, '--since', '2026-10-12T00:00:00Z',
                                      '--log-timezone=+00:00', '--port', '7890'), 4)

    def test_cli_unknown_parameter_fails(self):
        result = self.run_cli('install', '--destination', self.base / 'new', '--force')
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.base / 'new').exists())

    def test_unexpected_error_is_nonzero_redacted(self):
        with mock.patch.object(sys, 'argv', ['skillctl', 'validate']), \
             mock.patch.object(ctl, 'validate', side_effect=RuntimeError('SYNTHETIC-SECRET')), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            code = ctl.main()
        self.assertEqual(code, 6)
        self.assertNotIn('SYNTHETIC-SECRET', output.getvalue())


if __name__ == '__main__':
    unittest.main()
