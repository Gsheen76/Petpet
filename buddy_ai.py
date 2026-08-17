"""Compatibility alias for the packaged chat API."""

import sys

from petpet.chat import api as _api


# Tests and integrations historically patched transport functions and runtime
# constants through ``buddy_ai``.  Preserve that behavior with a module alias.
sys.modules[__name__] = _api
