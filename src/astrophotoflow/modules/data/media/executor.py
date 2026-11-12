import logging
from concurrent.futures import Executor, Future
from heapq import heapify, heappop, heappush
from itertools import count
from threading import Condition, Thread

logger = logging.getLogger(__name__)


class PreviewExecutor(Executor):
    def __init__(self, max_workers):
        self._condition = Condition()
        self._queue = []
        self._sequence = count()
        self._shutdown = False
        self._threads = [Thread(target=self._work, name=f"asset-preview-{index}", daemon=True) for index in range(max_workers)]
        for thread in self._threads:
            thread.start()

    def _enqueue(self, priority, key, fn, args, kwargs):
        with self._condition:
            if self._shutdown:
                raise RuntimeError("cannot schedule new futures after shutdown")
            future = Future()
            heappush(self._queue, (priority, next(self._sequence), future, fn, args, kwargs, key))
            self._condition.notify()
            return future

    def submit(self, fn, /, *args, **kwargs):
        return self._enqueue(0, None, fn, args, kwargs)

    def submit_background(self, key, fn, /, *args, priority=10, **kwargs):
        return self._enqueue(priority, key, fn, args, kwargs)

    def prioritize(self, keys):
        with self._condition:
            self._queue = [
                (min(priority, 1) if key in keys else priority, sequence, future, fn, args, kwargs, key)
                for priority, sequence, future, fn, args, kwargs, key in self._queue
            ]
            heapify(self._queue)

    def _work(self):
        while True:
            with self._condition:
                self._condition.wait_for(lambda: self._queue or self._shutdown)
                if not self._queue:
                    return
                _, _, future, fn, args, kwargs, _ = heappop(self._queue)
            if not future.set_running_or_notify_cancel():
                continue
            try:
                future.set_result(fn(*args, **kwargs))
            except BaseException as exc:
                logger.exception("Preview worker failed")
                future.set_exception(exc)

    def shutdown(self, wait=True, *, cancel_futures=False):
        with self._condition:
            self._shutdown = True
            if cancel_futures:
                for _, _, future, *_ in self._queue:
                    future.cancel()
                self._queue.clear()
            self._condition.notify_all()
        if wait:
            for thread in self._threads:
                thread.join()
