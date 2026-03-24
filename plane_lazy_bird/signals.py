"""Django signals for automatic task queuing when Plane issues change state.

This module is imported by apps.py ready() — it registers signal handlers
that react to Plane issue state changes without modifying Plane's core code.

NOTE: These signals connect to Plane's Issue model at runtime.
When running tests without Plane, the signal connection is skipped gracefully.
"""

import logging

logger = logging.getLogger(__name__)

# Signal handlers will be implemented in issue #11/#12.
# The module must exist now so apps.py can import it without error.
