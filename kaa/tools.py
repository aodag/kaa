import kaa
import cProfile, pstats, io, sys, contextlib, time, traceback, pprint, inspect

def _show_profile(f, *args, **kwargs):
    prof = cProfile.Profile()
    ret = prof.runcall(f, *args, **kwargs)

    out = io.StringIO()
    pstats.Stats(prof, stream=out).strip_dirs().sort_stats('cumulative').print_stats()
    _trace('\n'+out.getvalue())

    return ret


def _get_caller():
    rec = inspect.getouterframes(inspect.currentframe())[2]
    frame, fname, lno, funcname, lines, index = rec

    return "{}:{} {} - {}".format(fname, lno, funcname, lines[0])

def _get_stack(limit=None):
    out = io.StringIO()
    traceback.print_stack(sys._getframe(2), limit=limit, file=out)
    _trace(out.getvalue())

def _trace(*args):
    kaa.LOG.debug(' '.join(str(o) for o in args))

@contextlib.contextmanager
def _stime(header='---------------------------'):
    """
    with _stime('testing') as o:
        do_something()
        o.t1
        do_something()
        o.t2
    """
    _trace(_get_caller(), header)

    f = time.clock()
    class ll:
        def __init__(self):
            self.values = []
            self.start = time.clock()

        def __getattr__(self, name):
            self.L(name)

        def L(self, name):
            self.values.append((name, time.clock()))
            if len(self.values) == 1:
                _trace(' - {}: {:.6}'.format(o.values[0][0], o.values[0][1]-o.start))
            else:
                t1, t2 = o.values[-2:]
                _trace('{} - {}: {:.6}'.format(t1[0], t2[0], t2[1]-t1[1]))


    o = ll()
    yield o
    o.fin = time.clock()

    if o.values:
        _trace('{} - : {:.6}'.format(o.values[-1][0], o.fin - o.values[-1][1]))

    _trace('total: {:.6}'.format(o.fin-o.start))

def _pprint(obj):
    out = io.StringIO()
    pprint.pprint(obj, stream=out)
    _trace(out.getvalue())


import builtins
builtins._show_profile = _show_profile
builtins._get_caller = _get_caller
builtins._get_stack= _get_stack
builtins._trace = _trace
builtins._stime = _stime
builtins._pprint = _pprint
