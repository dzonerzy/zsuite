"""The zsuite command.

    zsuite versions           # the suite's packages and their versions
    zsuite new NAME [DIR]     # a language project named NAME (in ./NAME)
"""

import sys


def main(argv=None):
    import zsuite

    argv = sys.argv[1:] if argv is None else argv
    if argv == ["versions"]:
        for name, v in zsuite.versions().items():
            print("%-7s %s" % (name, v or "not installed"))
        return 0 if all(zsuite.versions().values()) else 1
    if len(argv) in (2, 3) and argv[0] == "new":
        try:
            path = zsuite.new(argv[1], argv[2] if len(argv) == 3 else None)
        except (ValueError, FileExistsError) as e:
            print("zsuite: %s" % e, file=sys.stderr)
            return 1
        name = argv[1]
        print("Made %s, the tutorial's language as %s. In it:\n" % (path, name))
        commands = [
            ("python %s.py run fib.%s" % (name, name), "run it"),
            ("python %s.py check fib.%s" % (name, name), "check it"),
            ("python %s.py lsp" % name, "its language server"),
            ("python -m pytest test_%s.py" % name, "its tests"),
        ]
        width = max(len(c) for c, _ in commands)
        for c, what in commands:
            print("    %s   # %s" % (c.ljust(width), what))
        return 0
    print(__doc__.strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
