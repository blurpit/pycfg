import contextlib
import os
import tempfile


@contextlib.contextmanager
def make_file(text: str):
    tmp = tempfile.NamedTemporaryFile(delete=False, mode='w+', suffix='.cfg')
    try:
        tmp.write(text)
        tmp.close()
        yield tmp.name
    finally:
        if os.path.exists(tmp.name):
            os.remove(tmp.name)
