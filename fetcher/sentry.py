"""
used by fetcher/logargparse,py and server/__init__.py
"""

import logging
import sys

# PyPI:
import sentry_sdk
from sentry_sdk.integrations.rq import RqIntegration

from fetcher import APP, VERSION
from fetcher.config import conf

logger = logging.getLogger(__name__)


def init() -> bool:
    """
    optional centralized logging to Sentry.
    If possible, call after initial logging setup
    (so info messages can be seen).
    """

    sentry_dsn = conf.SENTRY_DSN  # will log if set
    if sentry_dsn:
        # Not wiring in expected production app name here on the
        # theory that it's better to accidentally alert as production
        # than to have production errors go ignored.
        if APP.startswith('staging-'):
            env = 'staging'
        else:
            env = 'production'

        integrations = []
        if 'rq' in sys.modules:
            integrations.append(RqIntegration())

        # NOTE: Looks like environment defaults to "production"
        # unless passed, or SENTRY_ENVIRONMENT env variable set.
        sentry_sdk.init(dsn=sentry_dsn,
                        environment=env,
                        integrations=integrations,
                        release=VERSION)
        return True
    else:
        logger.info("Not logging errors to Sentry")
        return False
