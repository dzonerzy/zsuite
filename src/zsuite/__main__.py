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
            print(f"{name:<7} {v or 'not installed'}")
        return 0 if all(zsuite.versions().values()) else 1
    if len(argv) in (2, 3) and argv[0] == "new":
        try:
            path = zsuite.new(argv[1], argv[2] if len(argv) == 3 else None)
        except (ValueError, FileExistsError) as e:
            print(f"zsuite: {e}", file=sys.stderr)
            return 1
        name = argv[1]
        print(f"Made {path}, the tutorial's language as {name}. In it:\n")
        commands = [
            (f"python {name}.py run fib.{name}", "run it"),
            (f"python {name}.py check fib.{name}", "check it"),
            (f"python {name}.py lsp", "its language server"),
            (f"python -m pytest test_{name}.py", "its tests"),
        ]
        width = max(len(c) for c, _ in commands)
        for c, what in commands:
            print(f"    {c:<{width}}   # {what}")
        return 0
    print(__doc__.strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
