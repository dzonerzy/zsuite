"""tiny: a small language, built with zsuite.

    python tiny.py run fib.tiny            # run it, compiled to native code
    python tiny.py run fib.tiny --python   # run it as Python (the reference)
    python tiny.py check fib.tiny          # its errors and warnings, nothing run
    python tiny.py lsp                     # a language server on stdin/stdout
    python tiny.py build fib.tiny fib      # one executable running fib.tiny

syntax.py is the grammar (zgram), checks.py the rules (zrules), semantics.py
what each kind of node does (zrun), server.py the editor support (zlsp).
"""

import sys

import zgram
import zrun

from checks import RULES


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def run(path, mode):
    from semantics import lang

    try:
        lang.load(read(path), path).run(mode=mode)
    except (zrun.LoadError, zrun.Error) as e:
        print(e, file=sys.stderr)
        return 1
    return 0


def check(path):
    source = read(path)
    try:
        diagnostics = RULES.check(source)
    except zgram.ParseError as e:
        print(e.diagnostic.render(source, path), file=sys.stderr)
        return 1
    for d in diagnostics:
        print(d.render(source, path), file=sys.stderr)
    return 1 if any(d.severity == "error" for d in diagnostics) else 0


def lsp():
    from server import make_server

    return make_server().start_io()


def build(path, output):
    print(zrun.build_executable("semantics:lang", path, output))
    return 0


def main(argv):
    if len(argv) >= 2 and argv[0] == "run":
        return run(argv[1], "python" if "--python" in argv else "compiled")
    if len(argv) == 2 and argv[0] == "check":
        return check(argv[1])
    if argv == ["lsp"]:
        return lsp()
    if len(argv) == 3 and argv[0] == "build":
        return build(argv[1], argv[2])
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
