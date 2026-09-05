# Contributing

Two rules — non-negotiable:

1. **Every change ships with a test.** New extractor, new URL pattern, new
   field, bug fix — add at least one unit test (`tests/test_unit_modules.py`
   or `tests/test_router.py`). Integration tests hitting live services go in
   `tests/test_integration.py` and must skip gracefully on network failures
   / rate-limits.

2. **New or changed platform support updates the README.** Any patch that
   touches what `sharetrace` can extract — a new source, an added URL shape,
   new extracted fields, a caveat — updates the **Supported sources** table
   in `README.md` (and the `N sources` badge at the top if the source count
   changes).

Run the suite before opening a PR:

```bash
pip install -r requirements.txt pytest curl_cffi
pytest tests/ --ignore=tests/test_integration.py    # fast, no network
pytest tests/test_integration.py                     # network required
```

PRs that break either rule will be asked to fix it before review.
