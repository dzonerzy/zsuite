<div align="center">

<img src="https://raw.githubusercontent.com/dzonerzy/zsuite/main/docs/assets/logo.svg" alt="zsuite Logo" width="150">

# zsuite

**A toolkit for building programming languages in Python: syntax, checks, execution and editor support.**

Programming languages, DSLs and data formats, from a grammar to a fast implementation with an editor. Each stage is its own package, usable alone; together they cover the whole way.

[![GitHub Stars](https://img.shields.io/github/stars/dzonerzy/zsuite?style=flat)](https://github.com/dzonerzy/zsuite)
[![Python](https://img.shields.io/badge/python-3.10+-blue)](https://www.python.org/)
[![Zig](https://img.shields.io/badge/zig-0.16+-orange)](https://ziglang.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](https://github.com/dzonerzy/zsuite/blob/main/LICENSE)

</div>

---

| Package | Stage | What it does | PyPI |
|---|---|---|---|
| [zgram](https://github.com/dzonerzy/zgram) | Syntax | PEG grammars compiled to native parsers with LLVM: parse trees, ASTs, error messages, error recovery | `zgram-py` |
| [zrules](https://github.com/dzonerzy/zrules) | Static semantics | Rules over zgram's trees: scopes and names, context rules, types (generics, unions, subtyping), control flow, diagnostics | `zrules-py` |
| [zrun](https://github.com/dzonerzy/zrun) | Execution | Semantics written as Python functions, compiled to native code by partial evaluation; executables of a program | `zrun-py` |
| [zlsp](https://github.com/dzonerzy/zlsp) | Editors | A Language Server for any language defined with zgram and checked with zrules: diagnostics, navigation, completion, hover | `zlsp-py` |

## Installation

```bash
pip install zsuite-py              # the four packages, at versions that work together
pip install "zsuite-py[exe]"       # and what building executables needs
```

The import names are `zgram`, `zrules`, `zrun` and `zlsp` (each can also be installed alone as `<name>-py`). Wheels cover CPython 3.10+ on x86_64 Linux and Windows.

## Quick start

```bash
zsuite new calc        # a language project: grammar, rules, semantics, language server, tests
cd calc
python calc.py run fib.calc        # run a program, compiled to native code
python calc.py check fib.calc      # its errors and warnings
python calc.py lsp                 # a language server for your editor
python -m pytest test_calc.py      # its tests
```

The project is the [tutorial](docs/tutorial.md)'s language under your name: change the grammar in `syntax.py`, the rules in `checks.py`, what each construct does in `semantics.py`, and the editor's view in `server.py`.

## How they fit

```
source ──zgram──▶ parse tree ──zrules──▶ checked tree + symbols + types ──zrun──▶ running program
                                   │
                                   └──zlsp──▶ editor (diagnostics, go to definition, hover, ...)
```

- **zgram** turns text into a tree: a grammar in, a parser out (`zgram.compile(grammar)`), its nodes labelled with what the grammar names them.
- **zrules** checks the tree: rules written as selectors over node kinds (`"break_stmt"` inside a loop, each name defined once in its scope, the types of expressions), reported as diagnostics with source positions.
- **zrun** runs it: a semantic per node kind, plain Python taking the node and the runtime; zrun compiles the semantics for the program's tree to native code, so the language runs at a fraction of a hand-written interpreter's speed.
- **zlsp** serves it to editors: the grammar and the rules are all it needs.

## Versions

Each package is released on its own; these are the current ones, which work together:

| zgram | zrules | zrun | zlsp |
|---|---|---|---|
| 0.5.3 | 0.2.0 | 0.6.0 | 0.1.3 |

## Documentation

- [Tutorial](docs/tutorial.md): building a language through all four stages, from grammar to editor and executable.
- [Best practices](docs/best-practices.md): grammars that recover well, rules, semantics that compile fast, testing, shipping.
- [Design](docs/design.md): how the suite fits together, its decisions and its roadmap.
- Each package's README is its reference.

## Project Structure

```
src/zsuite/          # the zsuite package: versions(), `zsuite new`
examples/tiny/       # the tutorial's language: one file per stage, and its tests
                     # (also `zsuite new`'s template)
docs/                # the tutorial, best practices, the design
tests/               # the package's tests
```

## License

MIT
