"""Keep tests isolated from the player's real local Petpet profile."""

import atexit
import os
import shutil
import tempfile


_TEST_LOCAL_APP_DATA = tempfile.mkdtemp(prefix="petpet-tests-")
os.environ["LOCALAPPDATA"] = _TEST_LOCAL_APP_DATA
atexit.register(shutil.rmtree, _TEST_LOCAL_APP_DATA, ignore_errors=True)
