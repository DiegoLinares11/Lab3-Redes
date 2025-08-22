import threading, time

class Repeater:
    def __init__(self, interval_sec, fn):
        self.interval = interval_sec
        self.fn = fn
        self._stop = threading.Event()
        self.th = threading.Thread(target=self._run, daemon=True)
    def start(self): self.th.start()
    def _run(self):
        while not self._stop.is_set():
            t0 = time.time()
            self.fn()
            dt = time.time() - t0
            time.sleep(max(0.0, self.interval - dt))
    def stop(self): self._stop.set()