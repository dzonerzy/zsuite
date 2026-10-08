# zsuite design

zsuite is a set of Python libraries for building programming languages, DSLs
and data formats, from syntax to running code to editor support. Each stage is
its own package and repository, usable alone:

| Package | Stage | Answers |
|---|---|---|
| **zgram** | Syntax | Is this text well-formed? What is its structure? Build my AST. |
| **zrules** | Static semantics | Is this program valid? Names, scopes, context rules, types, control flow. |
| **zrun** | Execution | What does this program do? Semantics in Python, compiled to native code. |
| **zlsp** | Editors | Diagnostics, navigation, completion, hover for any language of the suite. |

This document describes how the suite fits together and why each part is
built the way it is. Each package's README is its reference: every option and
method is there.

## Principles

1. **Layered API: easy by default, open underneath.** Every package has a
   declarative top layer (a grammar, one-line rules, one function per kind of
   node) so a language gets working quickly, and a public low-level layer (the
   node array, rule callbacks, native capsules) for implementers who need it.
   High-level features are built only from the public low-level ones.
2. **Dynamic core, optional types.** Scopes, name resolution and context rules
   work for every language. Types are a layer of zrules that a dynamic language
   simply doesn't use, and that zrun turns into faster code when it's there.
3. **One source of truth per stage.** Syntax and tree shape live in the
   grammar, validity in the rules, meaning in the semantics. Every stage sees
   the same nodes under the same names: the grammar's rules and labels.
4. **Native by construction.** zgram's flat node array is the shared data
   structure. zrules, zrun and zlsp read it in place, natively, through
   versioned capsules: no Python object per node, so later stages run at close
   to parse speed.
5. **Designed by building languages.** Every API is exercised by real
   languages: tiny (the tutorial language), a typed language with structs and
   generics, Lua 5.4 (checked over 830 real-world files, run against Lua's own
   test programs), and a YARA-like rule engine.

## Packages and how they fit

Every package is named `<name>-py` on PyPI and imported as `<name>`
(`pip install zrules-py`, `import zrules`). This repository builds `zsuite-py`,
which installs the four at versions that work together.

```
zlsp ──► zrules ──► zgram
  │                   ▲
  └──► zrun ──────────┘
       (zrun uses zrules' analysis too)
```

| Repository | PyPI | Depends on |
|---|---|---|
| [zgram](https://github.com/dzonerzy/zgram) | `zgram-py` | nothing (bundles LLVM) |
| [zrules](https://github.com/dzonerzy/zrules) | `zrules-py` | zgram |
| [zrun](https://github.com/dzonerzy/zrun) | `zrun-py` | zgram, zrules |
| [zlsp](https://github.com/dzonerzy/zlsp) | `zlsp-py` | zgram, zrules |

Each package is one native extension module written in Zig, built with PyOZ
against Python's stable ABI: one wheel per platform covers CPython 3.10 and
later. Platforms: x86_64 Linux and Windows.

### Interfaces between the packages

The packages talk to each other natively, through `PyCapsule`s holding C
structs. Each capsule's name carries its version (`.v1`, `.v2`), and the
struct starts with an ABI number checked when it's opened: a mismatch is a
clear import-time error, never a misread.

| Capsule | From | Holds | Used by |
|---|---|---|---|
| `zgram.tree.v1` | `tree.capsule` | the node array, the input bytes, rule and label names (`zgram.TREE_ABI`) | zrules, zrun, zlsp |
| `zgram.llvm.v1` | `zgram.llvm_capsule()` | LLVM's C API, zgram's JIT, object files and bitcode (`zgram.LLVM_ABI`) | zrun |
| `zrules.analysis.v2` | `analysis.capsule` | the symbol table, scopes, uses, imports, types | zrun, zlsp |
| `zrules.selector.v1` | `Selector` | a compiled selector, run over a tree | zlsp |
| `zrun.native.v1` | a native library | a function compiled code calls directly | zrun's native host functions |

### One kind of diagnostic

Every stage reports the same type, zgram's native `Diagnostic`: a severity
(`error`, `warning`, `note`), a code (`syntax`, `undefined-name`,
`type-mismatch`, ...), a message, a byte span, notes ("first defined here"),
and `render(source, filename)`. A language's errors look the same whichever
stage finds them:

```
program.tiny:3:9: error: 'break' outside loop [break-outside-loop]
    3 |         break;
      |         ^^^^^^
```

Positions are byte offsets into the UTF-8 text throughout; zlsp converts to
the editor's encoding (UTF-16, or UTF-8 when offered) at the protocol edge.

## zgram: syntax

A PEG grammar in, a native parser out: `zgram.compile(grammar)` turns the
grammar into LLVM IR, compiles it in the process with LLVM's ORC JIT for the
CPU it runs on, and returns a parser.

### The grammar

```
if_stmt  = 'if' kw ws cond:expr ws then:block (ws 'else' kw ws else_:block)?   -> If
@left sum = left:term (ws op:addop ws right:term)*                             -> BinOp
@silent operand = neg | primary
neg      = '-' ws operand:operand                                              -> Neg
addop "operator" = [+\-]                                                       -> str
@silent ws = ([ \t\n\r] | '#' [^\n]*)*
```

- **Rules** are PEG expressions: sequences, ordered choice `|`, `*` `+` `?`,
  predicates `&` `!`, literals, character classes, `.`.
- **Labels** (`cond:expr`) name a child. How a label is used fixes its shape:
  once is the value, under `?` the value or `None`, under `*`/`+` a list.
- **`@silent`** rules make no node: their children belong to the rule around.
- **`@left` / `@right` / `@postfix`** fold chains in the tree: `1+2-3` under
  `@left` is `sum(sum(1, +, 2), -, 3)`; a lone operand stands for the rule;
  `@postfix` makes `a.b(c)` a call of a member.
- **`@memo`** caches a rule's result per position (packrat), for rules that are
  re-tried.
- **Display names** (`ident "name" = ...`) are what error messages call a rule.
- **`@recover(expr)`** names where a broken element ends, for error recovery.
- **Actions** (`-> Name`) say what a node's value is when an AST is built:
  a class called with the labelled children as keyword arguments, or a native
  built-in: `str`, `int`, `float`, `unquote` (a string literal, escapes
  replaced), `list`, `tuple`, `dict`, `True`/`False`/`None`, `drop`, `first`.

Left recursion is detected and refused: `@left`/`@right` express what it would.

### Parsing

| | |
|---|---|
| `parser.parse(text)` | the root `Node`: rule, text, span, children, labelled fields |
| `parser.parse_tree(text)` | a `Tree`: the flat node array and its capsule, for native readers |
| `parser.parse_ast(text)` | the AST: each node converted by its action, in one native pass |
| `parser.matches(text)` | accept or reject, from a separate validator that builds nothing |
| `parser.expected(text, offset)` | what the grammar takes at a position (completion) |
| `parser.rules()`, `labels()`, `literals()` | the grammar's names and its word literals (keywords) |

The tree is an array of 16-byte nodes in pre-order: start and end offsets,
subtree size, and a word packing the child count, rule id and label id. A
node's descendants are the contiguous range after it, so walking, searching
and slicing are linear scans with no pointers. The input isn't copied: nodes'
texts are slices of the string's own UTF-8 buffer. AST objects get `__zspan__`
and `__znode__`, so results keyed by node apply to them directly.

### Errors and recovery

A failing parse reports the furthest failure down to the terminal: a missing
`;` is "expected ';'" where it belongs, `f(1 2)` is "expected ',' or ')'". The
detail comes from re-running the failed parse in an interpreter of the
grammar; successful parses pay nothing for it.

With `recover=True`, broken text becomes error nodes and the parse goes on,
reporting every error (`tree.errors`). No grammar changes are needed:

- **Skipping**: a repetition of elements that make nodes (statements, items,
  arguments) skips a broken element into an error node and resumes at the next
  place an element matches, outside any brackets the broken text opened.
  Comments, strings and the grammar's keywords are respected: a bracket in a
  comment doesn't count, a block's `end` isn't swallowed.
- **Insertion**: a missing literal is taken as present (`let a 1;` keeps its
  `let_stmt`, with "expected '='"); a missing separator (`f(a 2)`, a table's
  `{a = 1 b = 2}`) is inserted; a closing word or bracket found later on the
  line closes there. The first item of a sequence, which decides whether it
  applies, is never made up.
- **Guesses**: an optional part's first punctuation is guessed, tried in order,
  and taken back if what follows can't match.

### Compiling

- **Native code per grammar**, optimized for the host CPU: inline node
  allocation, SIMD scanning of character-class runs, alternatives that look at
  the next byte before calling a rule that can't start with it, rules called
  from one place inlined.
- **Two caches**: the 16 most recent grammars in memory, and compiled grammars
  on disk (the platform's cache directory), keyed by what zgram generated for
  the grammar, the zgram and LLVM versions and the CPU. A process compiling a
  grammar another process compiled loads it in milliseconds.
- **Threads**: compiling releases the GIL; parsing releases it for inputs of
  16 KB or more. A parser can be shared between threads.

zgram is the fastest or tied in every comparison of its benchmark (JSON and
expressions, building trees and validating) against Spirit X3, lexy, PEGTL,
rust-peg, pest and others (zgram's BENCHMARK.md).

### LLVM for the suite

zgram carries the suite's only LLVM, and lends it: the `zgram.llvm.v1` capsule
exports LLVM's C API, zgram's JIT (compile a module, look up symbols, define
native functions, release), object files (emit for this or another x86-64
target, load) and bitcode. zrun builds its code with it; nothing else in the
suite carries a compiler.

## zrules: static semantics

Rules that decide whether a syntactically valid program is valid, checked
natively over zgram's node array. A `Rules` object holds a parser and a list
of rules; `rules.check(source)` returns diagnostics, `rules.analyze(source)` an
`Analysis` with the symbol table and types.

### Selectors

Every rule says where it applies with a selector over node kinds:

| Selector | Matches |
|---|---|
| `call` / `Call` | nodes of a rule, or of rules mapped to a class |
| `.cond`, `If.then` | a node under a label; a rule or class with a label |
| `call[name=len]` | a `call` whose child labelled `name` has the text `len` |
| `a > b`, `a b` | child, descendant |
| `:not(x)`, `:has(> x)`, `:nth(n)`, `:first`, `:last` | negation, containment, position |
| `a, b` | either |

Rules visit only the nodes their selector can end on (an index by rule and by
label), so a check costs about as much as the parse for a handful of rules.

### Structural rules

```python
from zrules import Rules, inside, unique, forbid, require, count

Rules(parser, [
    inside("Break", within="While", stop_at="FuncDef", message="'break' outside loop"),
    unique("FuncDef > .params", message="duplicate parameter '{text}'"),
    forbid("FuncDef FuncDef", message="functions cannot be nested"),
    require("FuncDef > .params"),
    count("Call[name=len] > .args", exactly=1),
])
```

### Names: `scopes()`

```python
scopes(scope=("Program", "FuncDef"),
       define=("Let > .name", "FuncDef > .params"),
       define_outer="FuncDef > .name",     # defined in the scope around its node
       use="Name",
       hoist="FuncDef > .name",            # visible before its definition
       after="Let > .name",                # `let a = a;` sees the outer `a`
       builtins=("print",))
```

Scopes and names: definitions, uses, shadowing, hoisting, declaration order
(`ordered`), undefined and unused names; several `scopes()` rules give
separate namespaces. **Members**: `a.b` resolves `b` in the scope `a` names
(a struct, a module). **Imports across files**: `rules.analyze_project({key:
source}, resolve=...)` resolves module imports, named imports, wildcards,
re-exports and cycles; `Project.origin(symbol)` follows an import to its
definition.

### Types: `types()`

One more rule, saying which nodes play which part (declarations, functions,
structs, calls, operators, literals, conditions, returns), read through their
labels, with a table of what the operators do:

```python
types(basic=("int", "float", "str", "bool", "void", "nil"),
      coerce={"int": "float"},
      literals={"int_lit": "int", "string": "str"},
      variables="let_stmt, param, field", functions="funcdef", structs="struct_def",
      binary="sum, term", calls="call_args", returns="return_stmt",
      operators={"+": [("int", "int", "int"), ("str", "str", "str")]},
      unions="union_type")
```

Each part is read through its labels (`name`, `params`, `returns`, `tparams`,
`bases`, `members`...), renamable with `labels=`.

- **Inference is local and gradual**: a variable takes its value's type, a call
  its function's result; an unknown type is compatible with everything, so an
  untyped program has no type errors and types can be added a piece at a time.
- **Declared types are nominal**: structs with fields, methods and a
  constructor; subtyping through declared bases (`struct Dog: Animal`), fields
  and methods inherited.
- **Generics**: generic functions and types (`fn first[T](xs: list[T]) -> T`,
  `struct Box[T]`), their parameters bound by the arguments at each call;
  built-in generics (`list[int]`); invariant, and function types
  contravariant in their parameters.
- **Unions and optionals**: `int | str`, `T?` (a union with `nil`).
- **Across files**: types are interned in one table shared by a project's
  files, and cross imports.

`Analysis.type_of(node)` and `Symbol.type` are what zrun's typed code and zlsp's
hover, signature help and inlay hints read.

### Control flow: `flow()`

One walk over sequences, branches, loops, `break`/`continue`, exits and
`goto`/labels reports unreachable code, functions that must return but can
reach their end, and variables read where some path gives them no value.

### Custom rules

```python
@rules.rule("Call", code="arity")
def check_arity(call, ctx):
    symbol = ctx.resolve(call.get("name"))
    ...
    ctx.error(call, f"{symbol.name}() takes {n} arguments")
```

Python rules get the zgram `Node` and a context (`error`, `warning`, `note`,
`resolve`, `type_of`, `symbols`): the escape hatch for anything the
declarative rules don't say.

### Performance

The whole check runs on the node array; `Symbol` objects are made only when
asked for. Names are integers after one hash, scopes a table. `analyze_project`
checks files on parallel threads with the GIL released. Lua's checker over
nmap's 3 MB Lua library: about 0.06 ms per thousand nodes with names, types
and flow.

## zrun: execution

### The idea: write an interpreter in Python, get a compiler

A language author says what each kind of node *does*, as Python functions: an
interpreter, the most natural way to define a language. zrun runs those
functions, and it also compiles them. Because the program's tree is known
before it runs, zrun specializes the interpreter for that program (partial
evaluation, the first Futamura projection): `node.op == "+"` is decided while
compiling, evaluating a child becomes the child's own code, and with zrules'
types an `a + b` of two ints becomes one machine add.

```python
lang = zrun.Language(PARSER, RULES)
lang.function("FuncDef")                 # nodes of this kind define functions

@lang.eval("BinOp")
def binop(node, rt):
    a, b = rt.eval(node.left), rt.eval(node.right)
    if node.op == "+":
        return a + b
    ...

@lang.exec("While")
def while_(node, rt):
    while rt.eval(node.cond):
        if not rt.loop(node.body):
            break

@lang.host                               # plain Python, any code
def print(*args):
    builtins.print(*args)

program = lang.load(source, "fib.tiny")  # parse, check: zrun.LoadError lists the errors
program.run(mode="compiled")
```

Three kinds of code meet in zrun:

| Code | Written in | Runs as |
|---|---|---|
| The program | the language | native code |
| The semantics: what each node does | Python | compiled into the program; anything outside the compilable subset runs as Python |
| Host functions: I/O, libraries | any Python (or a native library) | Python, called across the boundary (or native, directly) |

zrun is the runtime, not a code generator: the semantics are the definition,
and every way of running a program gives the same output and the same errors,
at the same nodes, with the same call stacks.

### The runtime interface

Semantics reach everything through `rt`: `eval`/`exec` of child nodes,
`load`/`store` of variables (by zrules symbol: slot accesses, not lookups),
`function`/`call`, `loop`, `raise rt.Return(v)`/`rt.Break()`/`rt.Continue()`,
`rt.tail_call(f, args)` (a return of what `f` returns, the frame given up
first, so chains of tail calls run in constant stack), errors
(`raise rt.Throw(value)`, `rt.error(node, message)`), zrules' view
(`rt.scope`, `rt.symbol`, `rt.type_of`), 64-bit wrapping arithmetic
(`rt.wrapping_add`, ...), and data read in place (`rt.u8(data, i)` ...
`rt.i64be`). `lang.function(kind, ...)` makes a node kind the language's
functions: frames, closures, hoisting, missing and extra arguments.

### Modes

- **`mode="python"`, the reference**: the semantics run as Python over the
  tree. Exactly what the semantics say.
- **`mode="compiled"`**: the semantics partially evaluated for the program's
  tree into LLVM IR, compiled with zgram's LLVM. A program whose optimized
  code isn't cached runs code compiled fast at once while the optimized code
  is made on worker threads (tiers).
- **`mode="auto"`**: as Python until the optimized code is ready.

Semantics are read from their Python source (`inspect` and `ast`, stable
across Python 3.10-3.14, where bytecode isn't). What compiles is a large
subset (values, statements, comprehensions, `try`, records and their methods,
helpers of the module); a semantic outside it runs as Python, and
`lang.python_semantics()` says which and why. zrun's guide to writing fast
semantics says what compiles and how to make it fast.

### Values and types

- **Tagged values**: 16-byte words; ints are 64-bit and checked (an overflow is
  the program's error at the node), never allocated, as floats and bools.
  Strings, lists, dicts, tuples and records (dataclasses, `__slots__` classes)
  are native, and shared with Python through proxies, not copied, when Python
  sees them.
- **Typed code**: with zrules' `types()` and `lang.types({...})`, a value is
  checked against its node's declared type once, where it's made; compiled code
  knows its kind from there: ints and floats in registers, typed functions
  called with plain arguments.
- **Speculation** for untyped code: a hot function gets a typed entry for the
  kinds of arguments it's called with, guarded where it's entered, so nothing
  ever needs undoing mid-function. Lists know when their items are all ints or
  all floats, so reads from them have a known kind.

### Engines

A language is used as a program (run once, from its start) or as an engine
(rules, filters, queries: loaded once, called many times over data). For
engines:

- `program.call(name, *args, context=None)`: a compiled call, about 0.15 µs
  from Python, the GIL released.
- `program.map(name, items, threads=n)`: calls on native threads.
- `zrun.Bytes` over `bytes`, `bytearray`, `memoryview` and `mmap`: read in
  place with bounds-checked loads, sliced without copies.
- `lang.native_host(name, capsule)`: a native library's function, called by
  compiled code directly, without Python or the GIL.
- `rt.context`: what the host gave the call (where results go).

### Ahead of time

- **The cache**: compiled code is kept in the platform's cache directory,
  keyed by its IR, LLVM's version and the CPU, bounded in size (least recently
  used first out). A program compiled once loads its code in the next process.
- **Compiled modules**: `lang.compile(source, path)` / `program.save(path)`
  write the program with its compiled code; `lang.load_compiled(path)` loads it
  without compiling, refused for another definition of the language (a hash of
  its grammar, semantics and host functions), another zrun or another CPU.
- **Executables**: `zrun.build_executable(language, source, output, target=)`
  makes one file running the program on a machine without Python: a Python
  runtime, the four packages, the language's module, the program and its
  compiled code, behind a small launcher (built with Zig) that unpacks them
  once into the cache directory. For x86_64 Linux and Windows, built from
  either.

### The runtime underneath

- **Memory**: reference counting with a cycle collector of CPython's design
  (generations, collected as containers are made). Containers holding only
  numbers aren't tracked until they may hold a container.
- **The GIL**: compiled runs and calls release it, and take it back only to
  touch Python (host functions, semantics run as Python); `report()` counts
  those crossings and says where they are.
- **Errors**: a runtime error is a `zgram.Diagnostic` at the failing node with
  the language's call stack.
- **Sessions and a REPL**: `lang.session()` runs entries one after another,
  each seeing what the ones before it defined; `lang.repl()` on top of it.

Lua 5.4, its semantics about 2,300 lines of plain Python, runs 17-400x faster
compiled than its semantics run as Python, within 1.6-3.2x of Lua's own C
interpreter; typed code is within 2x of C.

## zlsp: editors

A Language Server Protocol server for any language of the suite, configured in
Python:

```python
from zlsp import Server

Server(PARSER, RULES,
       name="tiny", extensions=[".tiny"],
       symbols={"FuncDef > .name": "function", "FuncDef > .params": "parameter",
                "Let > .name": "variable"},
       tokens={"number": "number", "string": "string", "cmpop, addop, mulop": "operator"},
       comments=["#"]).start_io()
```

### Features

From the grammar and the rules, with nothing language-specific to write:
diagnostics as you type (every syntax error, from zgram's recovery, and
zrules' findings, for every file of the workspace); go to definition and
declaration, type definition, references, highlights and rename, across files
through imports; hover (kind, name, type, the comments above the definition);
signature help; inlay hints with inferred types; completion (the names
visible at the cursor by the scope rules, members after `.`, the keywords the
grammar takes there); quick fixes for misspelled names; outline, workspace
symbols, folding, semantic highlighting; a TextMate grammar generated for
editors to use before the server answers.

**Hooks** extend it in Python: `hover`, `completion`, `code_actions`,
`format`, `configuration` (the editor's settings, which rules can read).

### Design

- **Native core**: the protocol (JSON-RPC framing, JSON), documents
  (incremental edits, line index, positions) and every feature are Zig. Trees
  are read through `zgram.tree.v1`, symbols and imports through
  `zrules.analysis.v2`, selectors through `zrules.selector.v1`: no Python
  object per node, symbol or use.
- **Incremental checking**: the files an edit can affect (the edited one,
  those importing it) are checked again; the others keep their analyses.
- **Debounced by the input**: edits apply as they arrive; analysis runs when
  no input is waiting, so a burst of keystrokes costs one. Cancelled requests
  are dropped, and an analysis gives way to newer messages.
- **Never dies on bad input**: a rule or hook raising an exception is logged
  to the editor, and the last good analysis is kept.
- **Testing and embedding**: `server.handle(message)` runs one message without
  I/O; `start_io()` serves stdin/stdout, as every editor launches it.

An edit of a 553 KB file is parsed, checked and published in about 18 ms.

## The tutorial language: tiny

tiny is small and complete: every stage of the suite is exercised by it, and
each package has it as an example.

```
program     = ws (body:stmt ws)*                                      -> Program
@silent stmt = funcdef | while_stmt | if_stmt | return_stmt | break_stmt
             | let_stmt | assign | expr_stmt
funcdef     = 'fn' kw ws name:ident ws '(' ws (params:ident (ws ',' ws params:ident)*)? ws ')' ws body:block  -> FuncDef
block       = '{' ws (stmt ws)* '}'                                   -> list
while_stmt  = 'while' kw ws cond:expr ws body:block                   -> While
if_stmt     = 'if' kw ws cond:expr ws then:block (ws 'else' kw ws else_:block)?  -> If
return_stmt = 'return' kw (ws value:expr)? ws ';'                     -> Return
break_stmt  = 'break' kw ws ';'                                       -> Break()
let_stmt    = 'let' kw ws name:ident ws '=' ws value:expr ws ';'      -> Let
assign      = name:ident ws '=' !'=' ws value:expr ws ';'             -> Assign
@silent expr_stmt = expr ws ';'

@left expr "expression" = left:sum (ws op:cmpop ws right:sum)?        -> BinOp
@left sum  "expression" = left:term (ws op:addop ws right:term)*      -> BinOp
@left term "expression" = left:operand (ws op:mulop ws right:operand)*  -> BinOp
@silent operand = neg | primary
neg         = '-' ws operand:operand                                  -> Neg
@silent primary = number | string | call | ident | '(' ws expr ws ')'
call        = name:ident ws '(' ws (args:expr (ws ',' ws args:expr)*)? ws ')'  -> Call

number      = [0-9]+                                                  -> int
string      = '"' ('\\' . | [^"\\])* '"'                              -> unquote
ident "name"       = !keyword [a-zA-Z_] [a-zA-Z0-9_]*                 -> Name
cmpop "operator"   = '==' | '!=' | '<=' | '>=' | '<' | '>'            -> str
addop "operator"   = [+\-]                                            -> str
mulop "operator"   = [*/%]                                            -> str

@silent keyword = ('fn' | 'while' | 'if' | 'else' | 'return' | 'break' | 'let') kw
@silent kw      = ![a-zA-Z0-9_]
@silent ws      = ([ \t\n\r] | '#' [^\n]*)*
```

```python
RULES = Rules(PARSER, [
    inside("Break", within="While", stop_at="FuncDef", code="break-outside-loop",
           message="'break' outside loop"),
    inside("Return", within="FuncDef", code="return-outside-function",
           message="'return' outside function"),
    forbid("FuncDef FuncDef", code="nested-function",
           message="functions cannot be defined inside functions"),
    scopes(scope=("Program", "FuncDef"),
           define=("Let > .name", "FuncDef > .params"),
           define_outer="FuncDef > .name",
           use="Name", hoist="FuncDef > .name", after="Let > .name",
           builtins=("print",)),
])
```

```
# The first ten Fibonacci numbers
fn fib(n) {
    if n < 2 { return n; }
    return fib(n - 1) + fib(n - 2);
}

let i = 0;
while i < 10 {
    print(fib(i));
    i = i + 1;
}
```

The semantics are zrun's `examples/tiny` (about 150 lines), the language
server zlsp's `examples/tiny` (with every hook used).

## Decisions

The choices that shape the suite, and why:

- **The tree is built by the parser, the AST from the tree afterwards.** A
  backtracking parser creating Python objects would discard many and need the
  GIL; zrules, zrun and zlsp need only the tree. The AST pass is one native
  scan of 16-byte nodes.
- **One flat node array, read in place.** Pre-order with subtree sizes: no
  pointers, contiguous descendants, cheap to share through a capsule.
- **No left recursion; folding annotations instead.** `@left`, `@right` and
  `@postfix` give the trees left recursion would, without seed-growing
  memoization in the generated code.
- **Error messages from an interpreter of the grammar.** The generated parser
  only tracks where it failed furthest; a failed parse is re-run to say what
  was expected, so successful parses pay nothing.
- **Types in zrules are a rule, local and gradual.** Untyped languages use none
  of it; typed ones get errors and, through zrun, faster code.
- **Semantics compiled from source, by partial evaluation.** Python source is
  stable across versions where bytecode isn't; specializing an interpreter for
  a known tree gives compiled code without a second definition of the
  language. A semantic outside the subset runs as Python, never refused.
- **Integers are 64-bit and checked.** An overflow is an error at the node in
  every mode; languages that wrap (Lua, hashes) say so with `rt.wrapping_*`.
- **Reference counting with a cycle collector.** Memory is freed as soon as it's
  unused, without pauses, and values cross into Python without translation.
- **Speculation guarded at function entry.** Typed entries for the kinds a hot
  function sees, checked where it's entered, where nothing has run yet: no
  deoptimization in the middle of code.
- **One LLVM, zgram's.** LLVM is most of a wheel's size and of a process's
  memory; zgram lends its copy through a capsule, and zrun builds its IR in
  memory through the C API.
- **Executables embed Python.** Semantics and host functions are Python;
  bundling a Python runtime makes every program shippable, not only those
  whose code never touches Python.
- **Stable ABI wheels.** One wheel per platform for every CPython from 3.10.
- **Byte offsets everywhere, editor encodings at the edge.** zgram, zrules and
  zrun speak UTF-8 byte offsets; zlsp converts per line from its line index.
- **No incremental parsing.** A full parse of 3 MB takes 14 ms; files an
  editor holds are far smaller. zlsp re-checks only what an edit can affect.

## Roadmap

- **Untyped code closer to a hand-written interpreter.** Lua runs within
  1.6-3.2x of its own C interpreter; the largest remaining gap is memory
  management of short-lived objects (binary trees).
- **macOS and ARM.** An LLVM with the AArch64 backend, zgram's code generator
  and SIMD paths per architecture, wheels and executables for macOS.
