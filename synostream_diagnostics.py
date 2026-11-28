"""Anonymous, thread-safe aggregate timings; no request arguments are retained."""
import functools
import logging
import re
import threading
import time
from contextlib import contextmanager
_lock=threading.Lock()
_totals={}
@contextmanager
def measure(api, method):
    api=api if isinstance(api,str) and re.fullmatch(r"(?:SYNO\.[A-Za-z.]+|NAS|TMDB|NFO|SCAN)",api) else 'NAS'
    method=method if isinstance(method,str) and re.fullmatch(r"[A-Za-z_]{1,32}",method) else 'request'
    start=time.perf_counter()
    try:yield
    finally:
        elapsed=time.perf_counter()-start
        with _lock:
            count,total=_totals.get((api,method),(0,0.0));_totals[(api,method)]=(count+1,total+elapsed)
        logging.getLogger('SynoStream').debug('Timing api=%s method=%s seconds=%.6f',api,method,elapsed)
def snapshot(reset=False):
    with _lock:
        result=dict(_totals)
        if reset:_totals.clear()
    return result
def summary():
    for (api,method),(count,total) in sorted(snapshot().items()):
        logging.getLogger('SynoStream').info('Timing summary api=%s method=%s count=%d seconds=%.6f',api,method,count,total)
def timed(api,method):
    def decorate(function):
        @functools.wraps(function)
        def call(*args,**kwargs):
            with measure(api,method):return function(*args,**kwargs)
        return call
    return decorate

import atexit
atexit.register(summary)
