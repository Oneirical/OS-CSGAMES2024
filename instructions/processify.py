# mypy: ignore-errors

"""
https://gist.github.com/schlamar/2311116
with Python 3 adaptations and some code formatting.

Modifications:
- Make test functions local to the main block
- Whitspace and formatting
"""

import os
import sys
import traceback
from functools import wraps
from multiprocessing import Process, Queue


def processify(func):
    """
    Decorator to run a function as a process.
    Be sure that every argument and the return value
    is *pickable*.
    The created process is joined, so the code does not
    run in parallel.
    """

    def process_func(q, *args, **kwargs):
        try:
            ret = func(*args, **kwargs)
        except Exception:
            ex_type, ex_value, tb = sys.exc_info()
            error = ex_type, ex_value, ''.join(traceback.format_tb(tb))
            ret = None
        else:
            error = None

        q.put((ret, error))

    # register original function with different name
    # in sys.modules so it is pickable
    process_func.__name__ = func.__name__ + 'processify_func'
    setattr(sys.modules[__name__], process_func.__name__, process_func)

    @wraps(func)
    def wrapper(*args, **kwargs):
        q = Queue()
        p = Process(target=process_func, args=(q,) + args, kwargs=kwargs)
        p.start()
        ret, error = q.get()
        p.join()

        if error:
            ex_type, ex_value, tb_str = error
            message = '%s (in subprocess)\n%s' % (str(ex_value), tb_str)
            raise ex_type(message)

        return ret

    return wrapper


if __name__ == '__main__':

    @processify
    def test_function():
        return os.getpid()

    @processify
    def test_deadlock():
        return range(30000)

    @processify
    def test_exception():
        raise RuntimeError('xyz')

    def test():
        print(os.getpid())
        print(test_function())
        print(len(test_deadlock()))
        test_exception()

    test()