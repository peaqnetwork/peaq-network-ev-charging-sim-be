import threading
import sys
import traceback
import os
import signal


original_init = threading.Thread.__init__


def patchedInit(self, *args, **kwargs):
    original_init(self, *args, **kwargs)
    original_run = self.run

    def patched_run(*args, **kw):
        try:
            original_run(*args, **kw)
        except Exception:
            sys.excepthook(*sys.exc_info())
    self.run = patched_run


def install(logger):
    def sendKillSignal(etype, value, tb):
        logger.error(f'error: {traceback.format_exc()}')
        logger.error('Stop all threading and exit the program')
        os.kill(os.getpid(), signal.SIGKILL)

    sys.excepthook = sendKillSignal
    threading.Thread.__init__ = patchedInit
