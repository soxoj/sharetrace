"""Unit tests for the CSV/JSON output writer."""
import csv
import json

import pytest

from sharetrace.output import (
    FIELD_LABELS,
    write_csv,
    write_json,
    write_output,
)


def _read_csv(path):
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.reader(f))


class TestWriteCsv:
    def test_columns_start_with_meta_then_field_labels(self, tmp_path):
        path = tmp_path / 'out.csv'
        write_csv(
            [{'url': 'u', 'platform': 'github', 'data': {'username': 'foo'}}],
            str(path),
        )
        rows = _read_csv(path)
        header = rows[0]
        assert header[:4] == ['url', 'platform', 'status', 'error']
        # FIELD_LABELS keys appear in order, immediately after meta columns.
        for i, key in enumerate(FIELD_LABELS):
            assert header[4 + i] == key

    def test_success_row_populates_data(self, tmp_path):
        path = tmp_path / 'out.csv'
        write_csv(
            [{
                'url': 'https://github.com/foo',
                'platform': 'github',
                'data': {'username': 'foo', 'is_noreply': True},
            }],
            str(path),
        )
        rows = _read_csv(path)
        header, row = rows[0], rows[1]
        idx = {name: i for i, name in enumerate(header)}
        assert row[idx['url']] == 'https://github.com/foo'
        assert row[idx['platform']] == 'github'
        assert row[idx['status']] == 'success'
        assert row[idx['error']] == ''
        assert row[idx['username']] == 'foo'
        assert row[idx['is_noreply']] == 'true'

    def test_error_row_has_error_and_empty_data(self, tmp_path):
        path = tmp_path / 'out.csv'
        write_csv(
            [{'url': 'https://x', 'platform': None, 'error': 'bad url'}],
            str(path),
        )
        rows = _read_csv(path)
        header, row = rows[0], rows[1]
        idx = {name: i for i, name in enumerate(header)}
        assert row[idx['status']] == 'error'
        assert row[idx['error']] == 'bad url'
        assert row[idx['platform']] == ''
        assert row[idx['username']] == ''

    def test_nested_value_serialized_as_json(self, tmp_path):
        path = tmp_path / 'out.csv'
        emails = [{'name': 'A', 'email': 'a@x'}, {'name': 'B', 'email': 'b@x'}]
        write_csv(
            [{'url': 'u', 'platform': 'github', 'data': {'emails': emails}}],
            str(path),
        )
        rows = _read_csv(path)
        idx = rows[0].index('emails')
        assert json.loads(rows[1][idx]) == emails

    def test_unknown_keys_appended_after_curated_columns(self, tmp_path):
        path = tmp_path / 'out.csv'
        write_csv(
            [{
                'url': 'u', 'platform': 'demo',
                'data': {'totally_new_field': 'x', 'another_one': 1},
            }],
            str(path),
        )
        header = _read_csv(path)[0]
        # Unknown keys must appear (and after the curated FIELD_LABELS block).
        assert 'totally_new_field' in header
        assert 'another_one' in header
        last_known = max(header.index(k) for k in FIELD_LABELS if k in header)
        assert header.index('totally_new_field') > last_known
        assert header.index('another_one') > last_known

    def test_mixed_success_and_error_rows(self, tmp_path):
        path = tmp_path / 'out.csv'
        write_csv(
            [
                {'url': 'u1', 'platform': 'github', 'data': {'username': 'foo'}},
                {'url': 'u2', 'platform': None, 'error': 'Unsupported platform or invalid URL'},
            ],
            str(path),
        )
        rows = _read_csv(path)
        idx = {name: i for i, name in enumerate(rows[0])}
        assert rows[1][idx['status']] == 'success'
        assert rows[1][idx['username']] == 'foo'
        assert rows[2][idx['status']] == 'error'
        assert rows[2][idx['error']] == 'Unsupported platform or invalid URL'

    def test_none_values_become_empty_cells(self, tmp_path):
        path = tmp_path / 'out.csv'
        write_csv(
            [{'url': 'u', 'platform': 'github', 'data': {'username': None}}],
            str(path),
        )
        rows = _read_csv(path)
        idx = rows[0].index('username')
        assert rows[1][idx] == ''


class TestWriteJson:
    def test_single_record_writes_object(self, tmp_path):
        path = tmp_path / 'out.json'
        write_json([{'platform': 'github', 'data': {'username': 'foo'}}], str(path))
        with open(path, encoding='utf-8') as f:
            payload = json.load(f)
        assert isinstance(payload, dict)
        assert payload == {'platform': 'github', 'data': {'username': 'foo'}}

    def test_multiple_records_writes_array(self, tmp_path):
        path = tmp_path / 'out.json'
        write_json(
            [
                {'platform': 'github', 'data': {'username': 'a'}},
                {'platform': 'github', 'data': {'username': 'b'}},
            ],
            str(path),
        )
        with open(path, encoding='utf-8') as f:
            payload = json.load(f)
        assert isinstance(payload, list)
        assert len(payload) == 2

    def test_unicode_not_escaped(self, tmp_path):
        path = tmp_path / 'out.json'
        write_json([{'data': {'name': 'Алиса'}}], str(path))
        with open(path, encoding='utf-8') as f:
            text = f.read()
        assert 'Алиса' in text


class TestWriteOutput:
    def test_csv_extension_dispatches_to_csv(self, tmp_path):
        path = tmp_path / 'out.csv'
        write_output(
            [{'url': 'u', 'platform': 'github', 'data': {'username': 'foo'}}],
            str(path),
        )
        # Must be readable as CSV with our header.
        rows = _read_csv(path)
        assert rows[0][:4] == ['url', 'platform', 'status', 'error']

    def test_json_extension_dispatches_to_json(self, tmp_path):
        path = tmp_path / 'out.json'
        write_output([{'platform': 'github', 'data': {}}], str(path))
        with open(path, encoding='utf-8') as f:
            json.load(f)  # must parse

    def test_unknown_extension_raises(self, tmp_path):
        path = tmp_path / 'out.txt'
        with pytest.raises(ValueError):
            write_output([], str(path))

    def test_extension_match_is_case_insensitive(self, tmp_path):
        path = tmp_path / 'out.CSV'
        write_output(
            [{'url': 'u', 'platform': 'github', 'data': {}}],
            str(path),
        )
        assert path.exists()
