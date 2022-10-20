import datetime as dt
from enum import Enum
from functools import wraps
from itertools import chain
import logging
import time
from typing import Any, Callable, Dict, List, Optional, TypedDict, Union

from fetcher import VERSION


class Status(Enum):
    OK = 'ok'
    ERROR = 'error'


TimeSeriesData = List[Dict[str, object]]

logger = logging.getLogger(__name__)


class ApiResultBase(TypedDict):
    status: Status
    duration: int               # ms
    version: str


class ApiResultOK(ApiResultBase):  # when status == Status.OK
    results: Dict


class ApiResultERROR(ApiResultBase):  # when status == Status.ERROR
    statusCode: int
    message: str


ApiResults = Union[ApiResultOK, ApiResultERROR]


def _error_results(message: str, start_time: float,
                   status_code: int = 400) -> ApiResultERROR:
    """
    Central handler for returning error messages.
    :param message:
    :param start_time:
    :param status_code:
    :return:
    """
    return {
        'status': Status.ERROR,
        'statusCode': status_code,
        'duration': _duration(start_time),
        'message': message,
        'version': VERSION,
    }


def _duration(start_time: float) -> int:
    return int(round((time.time() - start_time) * 1000)) if start_time else 0


# Phil: only working type signature I've found requires mypy to be installed for normal execution:
# from fastapi.types import DecoratedCallable
# from mypy_extensions import VarArg, KwArg
# def api_method(func: DecoratedCallable) -> Callable[[VarArg(Any),
# KwArg(Any)], ApiResults]:
def api_method(func: Any) -> Any:
    """
    Helper to wrap API method responses and add metadata.
    Use this in server.py and it will add stuff like the
    version to the response.

    Plus it handles errors in one place, and supresses ones we don't care to log to Sentry.
    """
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> ApiResults:
        start_time = time.time()
        try:
            results = func(*args, **kwargs)
            return {            # update ApiResultOK if adding items!
                'version': VERSION,
                'status': Status.OK,
                'duration': _duration(start_time),
                'results': results,
            }
        except Exception as e:
            # log other, unexpected, exceptions to Sentry
            logger.exception(e)
            return _error_results(str(e), start_time)
    return wrapper


def as_timeseries_data(counts: List[List[Dict]],
                       names: List[str]) -> TimeSeriesData:
    cleaned_data = [
        {
            r['day'].strftime("%Y-%m-%d"): r['stories']
            for r in series
        }
        for series in counts
    ]
    dates = set(chain(*[series.keys() for series in cleaned_data]))
    stories_by_day_data = []
    for d in dates:  # need to make sure there is a pair of entries for each date
        for idx, series in enumerate(cleaned_data):
            stories_by_day_data.append(dict(
                date=d,
                type=names[idx],
                count=series[d] if d in series else 0
            ))
    return stories_by_day_data
