"""End-to-end tests for the sharetrace CLI (no network)."""
import csv
import json

import pytest

from sharetrace import __main__ as cli


@pytest.fixture
def fake_process(monkeypatch):
    """Replace _process_url with a deterministic mapping of url -> record."""
    canned: dict = {}

    def fake(url, verbose):
        rec = canned.get(url)
        if rec is None:
            return {
                'url': url,
                'platform': None,
                'error': 'Unsupported platform or invalid URL',
            }
        # Always echo url so the harness controls only platform/data/error.
        out = {'url': url, **rec}
        return out

    monkeypatch.setattr(cli, '_process_url', fake)
    return canned


def _run(monkeypatch, *argv):
    monkeypatch.setattr('sys.argv', ['sharetrace', *argv])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    return exc.value.code


def _read_csv(path):
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.reader(f))


class TestSingleUrl:
    def test_writes_csv_for_single_url(self, monkeypatch, tmp_path, fake_process):
        out = tmp_path / 'r.csv'
        fake_process['https://github.com/foo'] = {
            'platform': 'github',
            'data': {'username': 'foo'},
        }
        code = _run(monkeypatch, 'https://github.com/foo', '-o', str(out), '-q')
        assert code == 0
        rows = _read_csv(out)
        idx = {n: i for i, n in enumerate(rows[0])}
        assert len(rows) == 2
        assert rows[1][idx['url']] == 'https://github.com/foo'
        assert rows[1][idx['platform']] == 'github'
        assert rows[1][idx['status']] == 'success'
        assert rows[1][idx['username']] == 'foo'

    def test_writes_json_object_for_single_url(self, monkeypatch, tmp_path, fake_process):
        out = tmp_path / 'r.json'
        fake_process['https://github.com/foo'] = {
            'platform': 'github',
            'data': {'username': 'foo'},
        }
        _run(monkeypatch, 'https://github.com/foo', '-o', str(out), '-q')
        with open(out, encoding='utf-8') as f:
            payload = json.load(f)
        assert isinstance(payload, dict)
        assert payload == {'platform': 'github', 'data': {'username': 'foo'}}

    def test_error_url_exits_nonzero(self, monkeypatch, tmp_path, fake_process):
        # No mapping → fake returns error record.
        out = tmp_path / 'r.csv'
        code = _run(monkeypatch, 'https://example.com/unknown', '-o', str(out), '-q')
        assert code == 1
        rows = _read_csv(out)
        idx = {n: i for i, n in enumerate(rows[0])}
        assert rows[1][idx['status']] == 'error'

    def test_unsupported_output_extension(self, monkeypatch, tmp_path, fake_process):
        out = tmp_path / 'r.txt'
        code = _run(
            monkeypatch, 'https://github.com/foo', '-o', str(out), '-q',
        )
        assert code == 2
        assert not out.exists()


class TestBatch:
    def _write_input(self, tmp_path, urls):
        path = tmp_path / 'urls.txt'
        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(urls) + '\n')
        return path

    def test_batch_csv_contains_one_row_per_url(self, monkeypatch, tmp_path, fake_process):
        fake_process['https://github.com/foo'] = {
            'platform': 'github', 'data': {'username': 'foo'},
        }
        fake_process['https://github.com/bar'] = {
            'platform': 'github', 'data': {'username': 'bar'},
        }
        inp = self._write_input(tmp_path, [
            'https://github.com/foo',
            '# this is a comment, must be skipped',
            '',
            'https://github.com/bar',
        ])
        out = tmp_path / 'r.csv'
        code = _run(monkeypatch, '-i', str(inp), '-o', str(out), '-q')
        assert code == 0
        rows = _read_csv(out)
        idx = {n: i for i, n in enumerate(rows[0])}
        assert len(rows) == 3  # header + 2 data rows
        assert {rows[1][idx['username']], rows[2][idx['username']]} == {'foo', 'bar'}

    def test_batch_mixed_success_and_error(self, monkeypatch, tmp_path, fake_process):
        fake_process['https://github.com/foo'] = {
            'platform': 'github', 'data': {'username': 'foo'},
        }
        # Second URL has no mapping → error record from fake.
        inp = self._write_input(tmp_path, [
            'https://github.com/foo',
            'https://example.com/unknown',
        ])
        out = tmp_path / 'r.csv'
        code = _run(monkeypatch, '-i', str(inp), '-o', str(out), '-q')
        # Batch always exits 0 — the file carries the per-URL status.
        assert code == 0
        rows = _read_csv(out)
        idx = {n: i for i, n in enumerate(rows[0])}
        statuses = [rows[1][idx['status']], rows[2][idx['status']]]
        assert sorted(statuses) == ['error', 'success']

    def test_batch_json_writes_array_with_url_field(self, monkeypatch, tmp_path, fake_process):
        fake_process['https://github.com/foo'] = {
            'platform': 'github', 'data': {'username': 'foo'},
        }
        fake_process['https://github.com/bar'] = {
            'platform': 'github', 'data': {'username': 'bar'},
        }
        inp = self._write_input(tmp_path, [
            'https://github.com/foo',
            'https://github.com/bar',
        ])
        out = tmp_path / 'r.json'
        _run(monkeypatch, '-i', str(inp), '-o', str(out), '-q')
        with open(out, encoding='utf-8') as f:
            payload = json.load(f)
        assert isinstance(payload, list)
        assert {p['url'] for p in payload} == {
            'https://github.com/foo', 'https://github.com/bar',
        }

    def test_empty_input_file(self, monkeypatch, tmp_path, fake_process):
        inp = self._write_input(tmp_path, ['# only comments', ''])
        code = _run(monkeypatch, '-i', str(inp), '-q')
        assert code == 1

    def test_missing_input_file(self, monkeypatch, tmp_path, fake_process):
        code = _run(monkeypatch, '-i', str(tmp_path / 'does_not_exist.txt'), '-q')
        assert code == 2


class TestArgumentValidation:
    def test_url_and_input_are_mutually_exclusive(self, monkeypatch, tmp_path, fake_process):
        inp = tmp_path / 'urls.txt'
        inp.write_text('https://github.com/foo\n', encoding='utf-8')
        code = _run(monkeypatch, 'https://github.com/foo', '-i', str(inp), '-q')
        assert code == 2

    def test_no_url_no_input_shows_help_and_exits(self, monkeypatch, fake_process):
        code = _run(monkeypatch, '-q')
        assert code == 1

    def test_list_flag_exits_zero(self, monkeypatch, capsys, fake_process):
        code = _run(monkeypatch, '-l', '-q')
        assert code == 0
        out = capsys.readouterr().out
        assert 'GitHub' in out


class TestStdoutModes:
    def test_single_url_json_to_stdout(self, monkeypatch, capsys, fake_process):
        fake_process['https://github.com/foo'] = {
            'platform': 'github', 'data': {'username': 'foo'},
        }
        _run(monkeypatch, 'https://github.com/foo', '-j', '-q')
        out = capsys.readouterr().out
        payload = json.loads(out)
        assert payload == {'platform': 'github', 'data': {'username': 'foo'}}

    def test_batch_json_to_stdout_includes_url(self, monkeypatch, capsys, tmp_path, fake_process):
        fake_process['https://github.com/foo'] = {
            'platform': 'github', 'data': {'username': 'foo'},
        }
        inp = tmp_path / 'urls.txt'
        inp.write_text('https://github.com/foo\n', encoding='utf-8')
        _run(monkeypatch, '-i', str(inp), '-j', '-q')
        payload = json.loads(capsys.readouterr().out)
        assert isinstance(payload, list)
        assert payload[0]['url'] == 'https://github.com/foo'
