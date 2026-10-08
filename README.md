# zsuite

A toolkit for building programming languages, DSLs and data formats in Python, from syntax to running code to editor support. Each stage is its own package, usable alone; together they take a language from a grammar to a fast implementation with an editor.

| Package | Stage | What it does | PyPI |
|---|---|---|---|
| [zgram](https://github.com/dzonerzy/zgram) | Syntax | PEG grammars compiled to native parsers with LLVM: parse trees, ASTs, error messages, error recovery | `zgram-py` |
| [zrules](https://github.com/dzonerzy/zrules) | Static semantics | Rules over zgram's trees: scopes and names, context rules, types (generics, unions, subtyping), control flow, diagnostics | `zrules-py` |
| [zrun](https://github.com/dzonerzy/zrun) | Execution | Semantics written as Python functions, compiled to native code by partial evaluation; executables of a program | `zrun-py` |
| [zlsp](https://github.com/dzonerzy/zlsp) | Editors | A Language Server for any language defined with zgram and checked with zrules: diagnostics, navigation, completion, hover | `zlsp-py` |

```bash
pip install zgram-py zrules-py zrun-py zlsp-py
```

The import names are `zgram`, `zrules`, `zrun` and `zlsp`. Wheels cover CPython 3.10+ on x86_64 Linux and Windows.

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
| 0.5.1 | 0.2.0 | 0.4.0 | 0.1.3 |

## Documentation

- [docs/design.md](docs/design.md): the toolkit's design: the stages, the interfaces between them, the decisions and the roadmap.
- Each package's README is its reference.

## License

MIT
