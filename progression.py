"""Compatibility alias for the packaged progression domain."""

import sys

from petpet.progression import core as _core


# Runtime tuning historically assigned module-level balance constants through
# ``progression``.  Alias the module object itself so those assignments keep
# updating the globals used by the packaged rule functions.
sys.modules[__name__] = _core
