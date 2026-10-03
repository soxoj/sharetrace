"""Extractor modules, one per platform.

Deliberately empty of re-exports. `from .telegram import telegram` bound the
function to the package attribute `sharetrace.modules.telegram`, shadowing the
submodule of the same name. On Python 3.10 that makes
`mock.patch("sharetrace.modules.telegram.requests")` resolve the function
instead of the module and raise AttributeError — 31 tests failed there for this
reason alone.

Nothing imported these names: `router.py` reaches modules through
`import_module("sharetrace.modules.<platform>")`, and the list had drifted out
of date anyway (github, gitlab, gdoc, linkedin, huggingface, claude and notion
were never in it).
"""
