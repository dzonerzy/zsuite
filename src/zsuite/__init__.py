"""zsuite: a toolkit for building programming languages in Python.

Installing zsuite-py installs the suite's four packages at versions that work
together; import them as usual:

    import zgram     # syntax: grammars compiled to native parsers
    import zrules    # checks: names, scopes, types, control flow
    import zrun      # execution: semantics in Python, compiled to native code
    import zlsp      # editors: a language server from the grammar and rules

`zsuite.versions()` says which are installed; `zsuite new NAME` (the
command) starts a language project.
"""

__version__ = "0.3.2"

PACKAGES = ("zgram", "zrules", "zrun", "zlsp")


def versions():
    """Each package of the suite and its installed version (None if it's
    missing or doesn't import)."""
    import importlib

    out = {"zsuite": __version__}
    for name in PACKAGES:
        try:
            out[name] = importlib.import_module(name).version()
        except Exception:
            out[name] = None
    return out


def new(name, directory=None):
    """A language project named `name`, in `directory` (default: ./name): the
    tutorial's language, ready to change. Returns its path."""
    from zsuite._new import new as make

    return make(name, directory)
