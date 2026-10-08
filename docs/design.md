# zsuite — a toolkit for building languages in Python

Status: **implemented and released** (zgram 0.5, zrules 0.2, zrun 0.4, zlsp 0.1); the roadmap at the end says what's next. Written as the design before the code, it records the decisions and why they were made: each package's README and documentation say how it works now.

zsuite is a set of Python libraries for building programming languages, DSLs
and data formats, from syntax to running code to editor support. Each stage is
its own package and repository:

| Package | Stage | Answers |
|---|---|---|
| **zgram** | Syntax | Is this text well-formed? What is its structure? Build my AST. |
| **zrules** | Static semantics | Is this program valid? Scopes, names, context rules, types. |
| **zrun** | Execution | What does this program do? Interpreter, later a JIT. |
| **zlsp** | Tooling | Editor support: diagnostics, go-to-definition, highlighting. |

## Principles

1. **Layered API: easy by default, open underneath.** Every package has a
   declarative top layer (a grammar, one-line rules, a ready-made interpreter)
   so a DSL author gets a working language quickly, and a public low-level
   layer (the node array, rule callbacks, custom passes and backends) for
   serious language implementers. High-level features are built only from
   public low-level ones: nothing is magic, anything can be replaced.
2. **Dynamic core, optional types.** Scopes, name resolution and context rules
   work for every language. Types are an optional layer in zrules that a
   dynamic language simply doesn't use.
3. **One source of truth per stage.** Syntax and AST shape live in the grammar,
   validity in zrules rules. The parse tree is AST-shaped and the AST is a 1:1
   projection of it, so zrules (on the tree), zrun (on the AST) and zlsp see
   the same nodes under the same names. No hand-written tree walks unless you
   want one.
4. **Fast by construction.** zgram's flat node array is the shared data
   structure. zrules checks and zrun lowering walk it natively, so later stages
   run at close to parse speed instead of in a Python tree walk.
5. **Designed by building a language.** Every API below is exercised by the
   demo language (see the end); if it's awkward there, the API is wrong.

## Repositories and dependencies

Separate repositories under one working folder. Every package is named
`<name>-py` on PyPI and imported as `<name>` (`pip install zrules-py`,
`import zrules`):

```
zsuite/
  docs/toolkit.md      this document
  zgram/               github.com/dzonerzy/zgram    PyPI: zgram-py
  zrules/              github.com/dzonerzy/zrules   PyPI: zrules-py
  zrun/                (to be created)              PyPI: zrun-py
  zlsp/                (to be created)              PyPI: zlsp-py
```

```
zlsp ──► zrules ──► zgram
  │                   ▲
  └──► zrun ──────────┘
```

- **zgram is the foundation.** The shared node-array interface and the shared
  diagnostics type live in zgram and are versioned there. Downstream packages
  depend on a zgram version range (`zgram-py>=0.2,<0.3`).
- **Cross-repo CI.** Each downstream repository tests against the latest zgram
  release, and against zgram's `main` on a schedule, so zgram changes that
  would break them show up before a release.
- **Versioning.** The node-array interface has its own version number
  (`zgram.TREE_ABI`), bumped only on incompatible layout changes. Packages
  compiled against it check the number at import and fail with a clear message
  on a mismatch.

## zgram (0.2): the foundation

zgram 0.1 turns a grammar into a JIT-compiled parser that produces a flat
parse tree. 0.2 adds what the rest of the suite builds on.

### Tree shape and AST mapping

Decided and **implemented in zgram (unreleased)**: the grammar shapes the
parse tree, and the AST is built from the tree afterwards, one object per
node. Three additions to the grammar, none of which puts expressions into it
(zgram's README is the reference; this is the summary):

```
if_stmt = 'if' ws cond:expr ws then:block (ws 'else' ws else_:block)?   -> If
@left sum     = left:product (ws op:addop ws right:product)*            -> BinOp
@silent unary = neg | primary
neg     = '-' ws operand:unary                                          -> Neg
args    = expr (ws ',' ws expr)*                                        -> list
addop   = [+\-]                                                         -> str
```

1. **Labels name fields.** `label:rule` on a rule reference tags the child
   node with a field name. How a label is used fixes its type: once → the
   value; under `?` → the value or `None`; inside `*`/`+` → a list.
2. **`-> Class` converts a node.** Labelled children become keyword arguments
   (`If(cond=..., then=..., else_=...)`); unlabelled children are not passed.
   There is no `Class(field=child)` argument form. A rule without labels
   passes its children positionally, or its text if it can't have children.
   Built-in conversions run natively: `-> str` (matched text), `-> int`,
   `-> float`, `-> True` / `-> False` / `-> None`, `-> list` (the children's
   values), `-> tuple`, `-> dict` (children are pairs), `-> drop` (no value),
   `-> first` (the first child's value). A rule with no action gives a leaf's
   text, an only child's value, or a list of the children's values.
3. **`@left` / `@right` fold chains in the tree.** On a rule of the form
   `left:x (... op:o ... right:y)*` (or `?`): when nothing repeats, the rule
   emits no node and the operand stands in for it; otherwise it emits nested
   nodes, each with exactly `left`, `op`, `right`. `1+2-3` under `@left`
   is `sum(sum(1, +, 2), -, 3)`; a lone `7` is just the `number` node.

4. **`@postfix` for suffix chains.** `@postfix post = target:primary (call |
   index | member)*`: each suffix node adopts everything to its left as its
   first child, under the head's label, so `a.b(c)` is
   `Call(target=Member(target=a, name=b), args=[c])`.

"Wrap only if it matched" needs nothing new: give the wrapped form its own
rule behind a `@silent` alternation (`unary = neg | primary` above).

Consequences:

- **Only nodes carry values.** To capture something (an operator, a keyword
  flag), give it a rule that isn't `@silent`.
- **A rule maps to at most one class**; several rules may share a class
  (`compare`, `sum`, `product` → `BinOp`).
- Classes are supplied at compile time:
  `zgram.compile(grammar, ast=my_module)` or `ast={"If": If, ...}`, or later
  with `parser.bind(ast)`.
- `parser.parse_ast(text)` parses, then builds the objects in one native pass
  over the node array. Each object gets `__zspan__`, a `(start, end)` pair,
  and `__znode__`, its node's index, so zrules results keyed by node apply
  directly to AST objects. `node.to_ast()` builds from an existing tree:
  parse once, check the tree with zrules, then build the AST from it.
- Grammars without labels, actions or `@left`/`@right` produce the same tree
  as in 0.1.

Why afterwards rather than during the parse: a backtracking parser would
create and discard Python objects, would have to hold the GIL (released today
for inputs of 16 KB or more) and would complicate `@memo`; zrules and zlsp
need only the tree; and there is one generated parser instead of two. The
extra pass is a linear scan of 16-byte nodes, small next to object creation.

Measured: a JSON grammar with `-> dict`/`-> list`/`-> float` converts the
16 KB benchmark document in about 120 µs, against 70 µs for `json.loads`
(parse alone: 20 µs), and without unescaping strings. "Competitive with
`json.loads`" is therefore not a goal; AST building for a language is
dominated by the Python constructors it calls. Folding costs nothing where
no operator matches, about 1.3x the flat parse on input made only of single
operators and about 1.6x on input made only of longer chains.

Rejected: real left recursion (`sum = sum addop product | product`). It needs
seed-growing memoisation in the generated code, and the pre-order tree would
need the same header insertion as `@left`.

### Node-array interface (TREE_ABI 1)

The low-level interface zrules, zrun and zlsp read natively:

- `tree = parser.parse_tree(text)` returns a `zgram.Tree` exposing:
  - `tree.nodes`: a read-only buffer of 16-byte nodes (`text_start`,
    `text_end`, `subtree_size`, and a word packing child count (12 bits),
    rule id (12 bits) and field id (8 bits)), in pre-order. A node's descendants are the contiguous range
    after it.
  - `tree.input`: the UTF-8 input bytes.
  - `tree.rules`, `tree.fields`: rule and field names by id.
  - `tree.capsule`: a `PyCapsule` named `zgram.tree.v1` holding a C struct
    with pointers to the above plus `TREE_ABI`, for native code in other
    packages. The tree stays alive while the capsule is referenced.
- The stored child count saturates at 4,095 ("that many or more"; count by
  stepping through siblings).
- The layout is documented as a stable format; changing it bumps `TREE_ABI`.
- Status: implemented. `tree.nodes` and `tree.input` are `bytes` (the node
  array is copied; native code reads it in place through the capsule).
  `node.tree` and `node.index` tie a `Node` to its place in the array.

### Diagnostics

One type shared by every stage, implemented as the native class
`zgram.Diagnostic`:

```python
Diagnostic(severity, code, message, span, line=0, column=0, notes=())
#   severity: "error" | "warning" | "note"
#   code:     "syntax", "break-outside-loop", "type-mismatch", ...
#   span:     (start, end) byte offsets
#   line, column: 1-based; 0 = worked out from the source by render()
#   notes:    list[Diagnostic]   ("previous definition is here", ...)
d.render(source, filename=None) -> str      # message, source line, carets
```

`ParseError.diagnostic` is the syntax error as one. zrules, zrun and zlsp all
report `Diagnostic`s, so a language's errors look the same whichever stage
finds them:

```
program.z:3:9: error: 'break' outside loop [break-outside-loop]
    3 |         break
      |         ^^^^^
```

Syntax errors report the furthest failure, down to the terminal: a missing
`;` gives "expected ';'" where it belongs, `f(1 2)` gives "expected ',' or
')'", and `let x = ;` gives "expected <rule>" at the `;`.

## zrules: static semantics

Rules that decide whether a syntactically valid program is valid.
**Implemented** (github.com/dzonerzy/zrules, unreleased), natively in Zig over
the `zgram.tree.v1` capsule; its README is the reference. Summary of what was
built, where it differs from the first sketch:

### Selectors

| Selector | Matches |
|---|---|
| `call` / `Call` | every node of that rule, or of a rule mapped to that class |
| `.cond`, `If.then` | a node labelled `cond`; a rule or class with a label |
| `call[name=len]` | a `call` with a child labelled `name` whose text is `len` |
| `call > ident`, `funcdef ident` | child, descendant |
| `:not(x)`, `:has(> x)`, `:nth(n)`, `:first`, `:last` | negation, containment, position among matching siblings |

Each rule visits only the nodes its selector can end on (an index by grammar
rule and by label), so a check costs about as much as the parse for a handful
of rules.

### Rules

```python
from zrules import Rules, inside, unique, forbid, require, count, scopes

rules = Rules(parser, [
    inside("Break", within="While", stop_at="FuncDef", message="'break' outside loop"),
    unique("FuncDef > .params", message="duplicate parameter '{text}'"),
    forbid("FuncDef FuncDef", message="functions cannot be nested"),
    require("FuncDef > .params"),
    count("Call[name=len] > .args", exactly=1),
    scopes(scope=("Program", "FuncDef"),
           define=("Let > .name", "FuncDef > .params"),
           define_outer="FuncDef > .name",     # defined in the scope outside its node's
           use="Name", hoist="FuncDef > .name", after="Let > .name",
           builtins=("print",)),
])
diagnostics = rules.check(tree)      # list[zgram.Diagnostic], in source order
analysis = rules.analyze(tree)       # + symbols, resolve(node), at(offset)
```

`define_outer` and `after` were not in the first sketch: a function's name
sits inside the node whose scope it does not belong to, and `let a = a;` must
not see the new `a`. Several `scopes()` rules give separate namespaces.

The symbol table (`Analysis`) is what zrun resolves variables with (the tiny
example's interpreter already does, through `__znode__`) and what zlsp needs
for go-to-definition (`at(offset)`).

### Custom rules

```python
@rules.rule("Call", code="arity")
def check_arity(call, ctx):
    symbol = ctx.resolve(call.get("name"))
    ...
    ctx.error(call, f"{symbol.name}() takes {n} arguments")
```

The function gets the zgram `Node` and a context (`error`, `warning`, `note`,
`resolve`, `tree`, `symbols`).

### Several files

`scopes(imports=..., import_all=..., exports=...)` and
`rules.analyze_project({key: source}, resolve=None)` resolve imports between
files (module imports with qualified access, named imports, wildcards,
re-exports, cycles). `Project.file(key)` is that file's `Analysis`;
`Project.origin(symbol)` follows an import to its definition.

### Types (implemented)

`types()` is one more rule, not a separate object as first sketched. It says
which nodes play which part (declarations, functions, structs, calls,
operators, literals, conditions, returns), read through labelled children, and
gives the operators a table:

```python
types(
    basic=("int", "float", "str", "bool", "void", "nil"),
    coerce={"int": "float"},
    literals={"Int": "int", "String": "str"},
    variables="Let, Param, Field", functions="FuncDef", structs="StructDef",
    binary="Sum, Term", calls="Call", returns="Return", conditions="If > .cond",
    operators={"+": [("int", "int", "int"), ("str", "str", "str")],
               "==": [("T", "T", "bool")]},
    builtins={"print": "fn(...) -> void"},
)
```

Decisions: inference is local (a variable takes its value's type, a call its
function's result); unknown is compatible with everything, so an untyped
program has no type errors and types are gradual; generics are invariant;
`T?` takes `nil`; declared types are nominal, with fields, methods and a
constructor; types cross imports. Types are interned in a table shared by the
files of a project. `Analysis.type_of(node)` and `Symbol.type` are what zrun's
typed backend and zlsp's hover read. The checker recurses but defers past a
depth of 100, so no input runs it out of stack.

### Control flow (implemented)

`flow()` walks sequences, branches, loops, `break` / `continue` and exits once
and reports unreachable code, `must_return` functions whose end is reachable,
and variables read where some path gives them no value (declared without a
value, or defined by assignment as in languages without declarations).

### Proof

`examples/typed` (structs, optionals, imports; all four layers together) and
`examples/lua`: a complete Lua 5.4 grammar and checker run over the Lua shipped
with nmap and sysdig (830 files, 7 MB): every file parses, none has an error,
sampled warnings are real. `docs/reference.md` lists every option.

## zrun: execution

**Status: in progress (started 2026-10-04).** Built complete, not in releases
that add execution strategies one at a time: the first release has everything
below.

### Build order

One release, built from the reference outwards; every step is tested against
the ones before it (differential testing), so the fast modes can't drift from
what the semantics say.

1. **Python mode, the reference.** `Language`, the semantics decorators, the
   defaults, `rt` (eval/exec, variables by zrules symbol, functions and
   frames, Return/Break/Continue, runtime errors as Diagnostics with the
   language's call stack), host functions, `Program.run`/`call`. Integers are
   checked 64-bit even here (an `int` subclass), so every mode agrees on
   overflow. tiny and the typed language run.
2. **The semantics compiler front** (Python, `ast` module): the compilable
   subset checked, with errors at the semantics' source lines; semantics
   lowered to zrun IR.
3. **zgram's LLVM for others** (`zgram.llvm.v1` capsule: the LLVM C API and
   zgram's JIT; IR built in memory, as zgram builds its own) and
   zrun's native runtime: tagged values, reference counting, strings, lists,
   dicts, records, errors.
4. **Compiled mode, tagged values:** the program's tree and the IR
   partially evaluated into LLVM IR, compiled per function on first call.
5. **Typed code unboxed**, from zrules' types.
6. **Interpreted mode** (the native loop over the node array).
7. **Speculation and deoptimization** for untyped code.
8. **Engines:** declared entry points with native stubs, calls without the
   GIL, `map()` on native threads, zero-copy `Bytes`, `context`, native host
   functions.
9. **The cycle collector.**
10. **Ahead of time:** compiled modules, then executables.
11. **REPL, documentation, CI, the release.**

### Status and plan (2026-10-05)

**Built** (steps 1-4, and more than step 4 planned): Python mode; the front;
the capsule (ABI 2) and the native runtime; compiled mode: the program and its
semantics partially evaluated into one LLVM module, thunks for nodes known only
at run time, helpers out of line, tiered helpers (a hot call site gets the
helper compiled for what it knows), pure helpers given constants run while
compiling, module state adopted natively (adopt.zig), Python functions the code
calls compiled, compiled code kept between runs (cache.zig), inline fast paths
for the common types. `program.report()`, `Language(hot_calls=)`,
`zrun.configure()`. Lua 5.4 runs all its tests compiled, natively; untyped code
is ~15x the same semantics run as Python (funcs.lua), binary trees ~6x Lua's
own interpreter.

**Phase A so far** (typed values): `lang.types()` (scalars and
zrun.Function), kinds checked once where made, in both modes; typed entries
(a function whose parameters are declared ints, floats or bools called with
them plain, its result returned in registers); direct calls; borrowed reads
(a function's stack variables read without a reference until stored to);
a semantic's last read of a local moves its value. Typed fib(30) 0.0075s, C
with the same overflow checks 0.0022s (3.4x); a loop summing a list ~1.1ns
an item, ~5x C. What's left of the gap needs knowing what can change but
doesn't (a function's name never rebound, a list's items all ints): phase
B's guards.

**Phase A, finished** (2026-10-07, after B-F; C is gcc -O2 with the same
overflow checks). Typed fib(30): 0.0043s, C 0.0022s (1.95x; 8.2 cycles a
call, C's 4.5). A typed loop summing 1000-item lists with `len()` in its
condition: 0.27 ns an item, C 0.22 ns (1.2x). Short lists (10 items a
call): 0.71 ns an item, C 0.18 (the call's own cost: a typed entry's list
parameter is counted at each call).

How: a host function (a Python function of the language's, as `len`) is
called at its compiled code's address kept at the call site, or inline
when small; a Python list given by `program.call` is read natively (16 ns
an item: Python's int conversion, the stable ABI's only way in). Lists
keep an elements kind in their header, as V8 does (every item a program's
int, a plain int, a float; any other store drops it, never set again):
an item read from a list of ints has a constant tag, the checks after it
folded. Typed entries take native lists; they get the calls' depth as a
parameter (Ctx's kept up to date only before code that looks at it), their
receiver borrowed, their int results with a constant tag. A function read
from a top-level variable is borrowed (FN_BORROWED; the variable stored to
while code runs buries it till the code's done: Ctx.bury), so calling the
program's functions counts nothing. Not done: items stored unboxed (8
bytes): measured, it gains nothing here (the overflow checks keep LLVM
from vectorizing, as gcc's C).

**Phase B, done** (2026-10-05), as it fits code that's mostly inline now:
helpers run inline by their size *with what the call knows* (an operator's
text, a node's kind looked up in a constant table: decided compiling), again
when walking down the tree, and a helper whose first `if` is its common case
runs that inline, the rest out of line; frames are per function (a function
whose rare path calls code out of line gets its variables moved into a frame
for that call); a variable's stored function is called directly. Then
speculation: a hot function's generic entry counts the kinds of its
arguments and gets a typed entry for them (int, float, bool), guarded at the
entry, where nothing has run yet (anything else runs generically; no guard
inside the code, so nothing to deoptimize mid-way); calls whose arguments'
kinds are only known at run time check them for it. `report()["speculated"]`.
Untyped Lua: fib(30) 0.42s -> 0.062s (Lua 5.4's own: 0.026s, measured
again 2026-10-07 with os.clock; the ~0.1s first written here counted its
process start), funcs.lua
0.029s -> 0.021s, programs.lua 0.0117s -> 0.0064s, binary trees 0.0097s ->
0.0051s (Lua's 0.0016s). What's left there: a list per Lua return (the
semantics' multiple results), tag checks the semantics make. Measured
2026-10-07: zrun's Lua is 2.6-6x slower than Lua 5.4's interpreter (a
numeric loop at the top level 12.5 ns an iteration, Lua's 2.1: generic
tagged code, the top level never specialized), 11-209x faster than its
semantics run as Python. Phase B's target for untyped code (within 3x of
the same program typed) isn't measured yet.

**Phase C, done** (2026-10-05): `program.call(name, *args, context=)`
compiled (~0.15us a call from Python: the native stubs of `program.entry()`
weren't needed for the target, and aren't built); `rt.context`; `zrun.Bytes`
over bytes, bytearray, memoryview and mmap, read with `rt.u8` ... `rt.u64le`
(inline, bounds-checked) and sliced without copies; `lang.native_host(name,
capsule)` ("zrun.native.v1": a library's function called by compiled code
directly). Compiled runs and calls release the GIL and take it back only to
touch Python (`report()["gil_taken"]` counts those times); the program's
shared state is made immortal before calls share it; the values' allocator
is per thread (one thread's lists plain globals: a library's thread-locals
cost a call each). `program.map(name, items, threads=n)` runs on native
threads, the first failing item's error raised as one thread would. Proof:
`examples/scan`, a YARA-like rule language (rules over a file's bytes, with
native `count` and `entropy`): 6000 files (466 MB, memory-mapped) in 0.26s
on one thread, 0.037s on 8, 0.020s on 16, every way (threads, map(), the
reference mode) giving the same results.

**Phase D, done** (2026-10-05): the cycle collector is CPython's design, not
trial deletion from candidate roots (Bacon-Rajan was tried: a check at every
count dropped cost up to 25% on call-heavy code, and a cycle closed by a
moved reference was missed). Every container is on its thread's list through
a 16-byte header before it; the young generation is collected as containers
are made (2000 more made than freed), the old as it grows by a quarter, both
at a run's end, a map() worker's end and on `zrun.collect()`. Objects Python
holds through a proxy are roots. Cost: fib(30) in Lua (two lists per call)
0.066s -> 0.074s, funcs.lua +2.5%, programs.lua +6%; compiling ~10% longer
(errors release the semantics' locals). Running it over the Lua programs found
leaks in compiled code, fixed: a known tuple's references (and a crash
materializing one twice), a known list made a stack slot, loops over
temporary known lists, caught errors (pcall) leaving semantics' locals, a
handler's exception on a return in it; the allocator kept blocks a thread
frees but doesn't make (map()'s results). Every Lua test program now runs
without a block left over.

**Phase E, compiled modules done** (2026-10-05): `program.save(path)` and
`lang.compile(source, output, path=None)` write the program's source and the
object of every module of code compiled for it (saved after running, the code
compiled as it ran too: Python functions it called, typed entries);
`lang.load_compiled(path)` parses and checks the source again and makes the
IR again (fast), the objects standing for LLVM's work. Refused, saying why,
for another definition of the language (a hash of its grammar as its parser
tells it, its semantics' and host functions' code, its function kinds and
limits), another zrun, another CPU or LLVM; a change the hash misses makes
other IR: compiled, never wrong. programs.lua: 28s compiled, 0.73s loaded
and run in a fresh process with no cache. Differs from the plan: the IR is
made again on loading (the compiler's state isn't saved: only LLVM's work
is skipped, nearly all of it). `scan.py --compile`.

**Executables: after phase F** (decided with the user, 2026-10-05). With
decision 1 below (no Python in them), they need zrun's runtime built without
Python, start-up code making every constant the compiled code refers to
(literals, tables, record types, the node data errors are worded from), and
output through native host functions linked from their libraries: their own
phase, the native output designed first (no language's print qualifies
today: tiny's and Lua's are Python).

**Phase F, tiers and `mode="auto"`: done** (2026-10-05; decided with the
user: tiers and background compiling, no native interpreter). A program
run compiled whose optimized code isn't in the cache is compiled fast
(LLVM's level 0) and runs at once, while its optimized code is made on
worker threads; the runs after it's done run it (calls and `map()` always
run the optimized code, waiting for it: their state is the code's). Code
compiled as the program runs is compiled fast too, its optimized object
made in the background for the cache (copied to a context of its own as
bitcode: zgram's capsule exports LLVM's bitcode functions). `mode="auto"`
runs as Python until the optimized code is at hand. The process waits for
the background work when Python finalizes (no LLVM work at exit; the next
process has everything cached). `zrun.configure(tiers=False)`: optimized
at once. `report()["code"]`, `report()["optimizing"]`. programs.lua with
no cache: first run 3.3 s (27 s optimized at once), 0.0092 s per run once
cached. `rt.wrapping_add`/`sub`/`mul` and the 64-bit shifts
`rt.wrapping_shl`/`shr`/`ushr` (by n modulo 64): done, native in compiled
code (Lua's shifts no longer go through Python). `lang.repl()` and
`lang.session()`: done (2026-10-06). Each entry is a program of its own,
loaded with the names the entries before it defined as builtins (zrules'
`analyze(builtins=)`); reading or assigning one reaches the variable where
it lives (the same variable for every entry), and a function of an earlier
entry is called in its own program. An expression entry's value is shown;
the root's exec semantics can return one (Lua's chunk: a top-level
`return`). Entries run as Python. `examples/lua/lua.py` with no script is a
Lua REPL. Still to do in F: documentation, CI, the release.

Differs from the plan above: a semantic outside the subset isn't an error at
`Language` creation; it runs as Python and `lang.python_semantics()` says why.

**To build, in this order:**

- **A. Typed values (step 5).** `lang.types(int=int, float=float, ...)` says
  which Python values a language type's nodes evaluate to. The compiler asks
  zrules the type of each node it compiles: `rt.eval` of a node of a declared
  type gives a value of a known kind (checked once where it's made: a wrong
  declaration is an error at the node, never a wrong result), so arithmetic,
  comparisons and variables of it need no tag checks or reference counts.
  Then **calls across functions**: a function whose parameter and result
  types are known gets a direct native entry (its arguments and result as
  plain values, no argument or result list), its generic entry kept for
  every other caller. Proof: fib and loops over arrays within 2x of C.
- **B. Speculation and deoptimization (step 7).** Type feedback: the tags each
  operation of a hot specialized helper sees, counted. The helper is compiled
  again for the types seen, guarded at its entry (arguments) and after each
  call back into generic code; a failed guard goes to the generic code
  (deoptimization at the call site, where nothing has run yet, or at a guard
  after which the rest is re-run generically from saved state), and the
  site is compiled again without that assumption after a few failures.
  Proof: programs that make every kind of guard fail give the reference's
  results.
- **C. Engines (step 8).** `program.call(name, *args)` compiled; entries with
  declared signatures (`program.entry(...)`) through native stubs;
  `context=`; `zrun.Bytes` (bytes, mmap, memoryview as native read-only
  buffers, `rt.u8`/`rt.u32le`/slices); `@lang.native_host` (a capsule's
  function called without Python). Then calls without the GIL and
  `program.map(name, items, threads=n)`: per-call contexts, atomic counts
  for shared objects, a thread-safe allocator, compiling behind a lock.
  Proof: a small rule language over thousands of files, threads and `map()`
  giving one thread's results.
- **D. Cycle collector (step 9).** Trial deletion over native containers
  (lists, dicts, records, frames, functions), run by allocation count; the
  proxies' objects visited by Python's gc.
- **E. Ahead of time (step 10).** Compiled modules first:
  `lang.compile(source, path, module=True)` writes the program's object
  code (the cache's, all of it) with what it needs (entry points, the
  recipes for its constants: literals, tables, module state by name, Python
  objects by module and name) and a hash of the language's definition;
  `lang.load_compiled(path)` refuses another language's or zrun's. Then
  executables.
- **F. Interpreted mode, `mode="auto"`, `rt.wrapping_add` and the others,
  `lang.repl()`, documentation, CI, the release (with zgram's ABI 2).**

**Decided provisionally** (with the user, 2026-10-05; to be looked at again
when their phase comes):

1. Executables are only for programs whose compiled code never needs Python
   (no host functions, no semantics run as Python): refused, with the
   reason, otherwise. (The alternative: embedding a Python runtime.)
2. Compiled code runs without the GIL and takes it around calls into Python
   (host functions, semantics run as Python); `report()` shows those calls.
   (The alternative: entries for parallel use refused unless free of
   Python.)

Layout: one native module, like zgram, zrules and zlsp: everything in Zig
(the API classes, the reference runtime that calls the semantics, the
reading of their source through Python's `ast` objects, the IR, the partial
evaluator, code generation, the runtime). Python only configures, and is the
language of the semantics.

### The idea: write an interpreter in Python, get a compiler

A language author describes what each kind of node *does*, as Python
functions: an interpreter, the most natural way to define a language. zrun
runs those functions, and it also compiles them. Because the program's tree is
known before it runs, zrun specializes the interpreter for that program
(partial evaluation, the first Futamura projection): `node.op == "+"` is
decided at compile time, calls to evaluate child nodes become the compiled
code of those children, and with zrules' types an `a + b` of two `int`s
becomes one machine add. The author writes an interpreter; the user's program
runs as native code.

Prior art: PyPy/RPython (an interpreter in restricted Python becomes a native
interpreter with a JIT), Truffle/Graal (AST interpreters partially evaluated
into compiled code), Numba (typed Python subset to LLVM). zsuite's advantage
over all of them: zrules has already worked out the program's types, names
and control flow statically, which those systems discover at run time.

Three kinds of code meet in zrun:

| Code | Written in | Runs as |
|---|---|---|
| The program | the author's language | native code (compiled) |
| The semantics: what each node does | Python, in zrun's compilable subset | compiled into the program; or run by the native interpreter |
| Host functions: I/O, libraries | any Python | Python, called across a boundary |

### API

```python
import zrun

lang = zrun.Language(parser, rules)          # zgram parser, zrules Rules

@lang.eval(BinOp)                            # an expression: returns a value
def binop(node: BinOp, rt: zrun.Runtime):
    left, right = rt.eval(node.left), rt.eval(node.right)
    if node.op == "+":
        return left + right
    if node.op == "<":
        return left < right
    ...

@lang.exec(While)                            # a statement
def while_(node: While, rt: zrun.Runtime):
    while rt.eval(node.cond):
        rt.exec(node.body)                   # break/continue: rt.Break, rt.Continue

@lang.exec(Let)
def let(node: Let, rt: zrun.Runtime):
    rt.store(node.name, rt.eval(node.value)) # variables by zrules symbol

@lang.host                                   # plain Python, any code
def print(*args):
    builtins.print(*args)

program = lang.load(source)                  # parse, check (zrules), compile
program.run()                                # a script: run it from its start
program.call("match", data)                  # an engine: call an entry point, many times
lang.repl()
lang.compile(source, "app")                  # ahead of time: an executable
lang.compile(source, "rules.zrc", module=True)   # ... or a module to load later
```

`rt` is the runtime interface semantics use: `eval`/`exec` of child nodes,
`load`/`store` of variables (by zrules symbol: slots, not name lookups),
`call` of functions, `Return`/`Break`/`Continue` and `rt.error(node, message)`
for runtime errors. Defaults cover the common shapes (literals by zgram
action, names, blocks, calls), so a small language needs few semantics.

### The compilable subset

Semantics are compiled from their Python source (`inspect.getsource` and the
`ast` module), not from bytecode: source is stable across Python 3.10-3.14,
bytecode changes with every release. The subset:

- **Values:** `int` (64-bit, overflow checked or wrapping: the language says
  which), `float`, `bool`, `str`, `None`, tuples, lists and dicts of those,
  records (dataclasses), the language's own values, and node fields (constants
  at compile time).
- **Statements:** assignment, `if`, `while`, `for` over `range` and sequences,
  `return`, `assert`, raising zrun's control flow and errors.
- **Calls:** other semantics, `rt`, host functions (through the boundary),
  and a set of builtins (`len`, `min`, `abs`, string methods, ...).
- **Not in the subset:** `eval`/`exec`, dynamic attributes, generators,
  `try`/`except` of arbitrary exceptions, closures over mutable state, imports.

Types in semantics are inferred (from annotations, node field types and
`rt`); a semantic outside the subset is an error at `Language` creation,
reported at its Python source line with the reason ("line 12: `setattr`
can't be compiled"), unless it is marked `@lang.eval(Node, native=False)`,
which runs it as Python and is the explicit way to use full Python.

### Values

- **Typed programs** (a `types()` rule, types known): unboxed native values.
  `int` is an `i64`, `float` an `f64`, structs are native structs, `T?` a
  tagged option, `list[T]` a native array of `T`, functions are code pointers
  with an environment.
- **Untyped programs**, or parts of a program whose types are unknown: a
  16-byte tagged value, operations dispatch on the tag in native code. Still
  no Python per operation.
- **Speculation** on top, for untyped code: the first compile records which
  types each operation actually sees (type feedback), and hot functions are
  recompiled for those types (unboxed, the tag checks hoisted into guards).
  A guard that fails deoptimizes: execution resumes in the generic tagged
  code at the same node, with its values rebuilt from the guard's state, and
  the function is recompiled without that assumption. Like LuaJIT or V8, so
  dynamic languages run close to typed ones on stable code.
- **Integers** are 64-bit; overflow is a runtime error at the node, never a
  silent wraparound. A language that wants wrapping (hashing, bit tricks)
  says so in its semantics (`rt.wrapping_add`, ...).
- **Across the boundary** (host functions): values convert to and from Python
  objects; a language value with no Python equivalent is wrapped.

### Execution

All of these ship together; `program.run(mode="auto")` picks, and a mode can
be forced:

- **Compiled** (the default for loaded programs): the program's tree and the
  compiled semantics are partially evaluated into LLVM IR, optimized, and run
  through LLVM's ORC JIT. Functions are compiled when first called, so start
  up doesn't wait for code that never runs; hot functions are recompiled with
  more optimization.
- **Interpreted:** a native interpreter loop over zgram's flat node array
  that calls the compiled semantics per node, for code that runs once (a REPL
  line, a small script) where compiling costs more than it saves.
- **Python:** semantics marked `native=False` and host functions run as
  Python, called from either of the above.
- **Ahead of time**, in two forms (see the next section for which fits):
  - an **executable** (`lang.compile(source, "app")`): the program with
    zrun's runtime, for x86_64 Linux and Windows (the platforms zsuite's
    wheels cover), linked with the linker bundled in Zig so users need
    nothing installed: a language built with zsuite can ship binaries;
  - a **compiled module** (`lang.compile(source, "rules.zrc", module=True)`):
    the program's compiled code, loaded later with `lang.load_compiled()`
    without parsing, checking or compiling it again, like `yarac`'s output.

  Ahead-of-time code has no JIT to fall back on, so untyped parts use tagged
  values without speculation.

Compiled code runs without the GIL; a call to a Python host function takes it.

### Programs and engines

A language gets used in one of two ways, and zrun serves both:

| | A program (a script language, tiny) | An engine (rules, filters, queries: YARA-like) |
|---|---|---|
| Run | once, from its start | loaded once, called many times |
| Input | mostly the program itself | large data: files, packets, events |
| Driven by | the program (`main`) | a host application calling entry points |
| Mode | interpreted for short runs, compiled for long ones | compiled at load: one compile, millions of calls |
| Ahead of time | an executable | a compiled module |

An engine's rules are the program zrun compiles; the data it looks at is
input, not code. What an engine needs from zrun:

- **Entry points, called many times.** `rules = lang.load(source)` compiles
  once; `rules.call("match", data)` runs a compiled function. An entry point
  with a declared signature (`rules.entry("match", args=(zrun.Bytes,),
  returns=bool)`) is called through a native stub that converts nothing it
  doesn't have to: the target is well under a microsecond per call from
  Python.
- **Many calls in parallel.** A loaded program is immutable: its code, types
  and constants are shared, and each call gets its own stack and memory for
  its values. `call()` releases the GIL, so Python threads scan in parallel
  with one compiled rule set; `rules.map("match", items, threads=8)` runs a
  batch on native threads without returning to Python between items.
  Speculation's recompilations swap a function's code atomically, so running
  calls finish on the old code.
- **Data without copies.** `bytes`, `bytearray`, `memoryview` and `mmap`
  objects are passed as native read-only buffers, not copied: a
  `zrun.Bytes` value in the language, with bounds-checked reads
  (`rt.u8(data, i)`, `rt.u32le(data, i)`, slices that share the memory), so a
  rule over a 2 GB memory-mapped file costs no allocation. (The stable ABI
  has the buffer protocol from Python 3.11; on 3.10, `bytes` and `mmap` are
  read through their own functions.)
- **Context per call.** `rules.call("match", data, context=scan)` hands the
  call an object its semantics and host functions can reach
  (`rt.context`): where results go, which file this is.
- **Native host functions.** Some host functions must not go through Python
  at all: a pattern-matching engine called for every rule of every file.
  `@lang.native_host` registers a function from a native library (through a
  capsule, like `zgram.tree.v1`); compiled code calls it directly, without
  the GIL. The pattern matcher of a YARA-like engine (multi-pattern search,
  regular expressions) is such a library, and a zsuite package of its own.
- **Compiled modules.** `lang.compile(source, "rules.zrc", module=True)`
  saves the compiled code with what it needs to be loaded again: entry
  points, types, constants, the zrun version, the CPU features it was
  compiled for (x86-64-v2 by default, or the host's), and a hash of the
  language's definition (grammar, rules and semantics), so a module compiled
  for another version of the language is refused rather than misrun.
  `lang.load_compiled("rules.zrc")` links it into the JIT without parsing,
  checking or compiling.

### Runtime

- **Memory:** reference counting with a cycle collector, like CPython:
  memory is freed as soon as a value is unused (no pauses), and values
  crossing into Python need no translation layer. The compiler removes the
  count updates it can prove unneeded (values that don't escape a function,
  borrowed arguments).
- **Errors:** a runtime error is a `zgram.Diagnostic` at the failing node's
  span, with the language-level call stack (compiled code keeps the node ids
  of its frames for this).
- **LLVM:** zrun uses the LLVM zgram already carries (zrun always runs next
  to zgram), through the `zgram.llvm.v1` capsule: the LLVM C API's functions
  and zgram's ORC JIT. zrun builds its IR in memory through the C API, as
  zgram's own code generator does (no text, no bitcode step), and hands the
  module to the JIT. Not a second copy of LLVM: zgram's is ~70 MB of the
  process and ~17 MB of its wheel. (Decided with the user 2026-10-04.)

### Proof

- `tiny` (untyped: tagged values) and the typed language of zrules'
  `examples/typed` (unboxed) run compiled.
- **Differential testing:** every test program runs in every mode (compiled,
  interpreted, pure Python) and must give the same output and errors, like
  zgram's reference interpreter.
- **Performance targets:** typed numeric code within 2x of C (fib, loops over
  arrays); untyped code with stable types within 3x of the same program
  typed, thanks to speculation; untyped code in general at least 10x faster
  than the same semantics run as Python.
- **Deoptimization tests:** programs built to make every kind of guard fail
  (a type that changes mid-loop, an overflow, a polymorphic call) must give
  the same results as the interpreter.
- **An engine:** a small rule language (conditions over a file's bytes and
  size, calling a native host function) loaded once and called over
  thousands of files, from several Python threads and through `map()`, with
  results identical to one thread; a compiled module saved, loaded in a fresh
  process, and refused when the language definition changed.

### Decisions (zrun)

Settled with the user, 2026-09-30:

1. **Memory:** reference counting with a cycle collector.
2. **Untyped code:** tagged values *and* speculation with deoptimization.
3. **Integers:** 64-bit, overflow is an error (wrapping on request).
4. **Ahead of time:** executables for x86_64 Linux and Windows in the first
   release, linked with Zig's bundled linker.

## zlsp: editor support

A Language Server Protocol server for any language defined with zgram (and
checked with zrules), configured in a few lines of Python:

```python
from zlsp import Server

server = Server(
    parser, rules,                       # zgram parser; zrules Rules (optional)
    name="tiny",
    extensions=(".tiny",),               # the workspace's files, for imports
    symbols={"FuncDef > .name": "function", "Let > .name": "variable",
             "FuncDef > params > Name": "parameter"},
    tokens={"Number": "number", "String": "string"},
    comments=r"#[^\n]*",
)
server.start_io()                        # stdin/stdout, launched by the editor
```

### Features (0.1)

| LSP | From |
|---|---|
| diagnostics, as you type | zgram's syntax errors (`recover=True`: every error, and checking goes on) and zrules' findings, per file of the project |
| definition, declaration | `Symbol.span`; across files through `Project.origin` |
| references, document highlight | `Symbol.use_spans`, in every file of the project |
| rename (+ prepare) | the definition and every use; builtins refused |
| hover | the symbol's kind, name and type (`types()`) |
| document symbols (outline) | definitions matching `symbols=`, nested by scope (`Symbol.scope`, `owns`) |
| semantic tokens | nodes by rule (`tokens=`), names by symbol kind (a use gets its definition's kind, `declaration` on definitions), the grammar's keywords, comments by regex |
| folding | multi-line scope nodes (or `folding=` selectors), runs of comment lines |
| completion | the names visible at the cursor (scope, and position when `ordered`), members after `.` when the target names a scope, keywords |

### Design

- **Native core.** The protocol (JSON-RPC with Content-Length framing), JSON
  parsing and writing, the documents (incremental edits, line index,
  positions), and every feature are Zig. The tree is read through the
  `zgram.tree.v1` capsule; zrules' symbols are read once per analysis into
  native arrays. Python holds the configuration and runs custom rules.
- **Positions.** The client's position encoding is negotiated
  (`general.positionEncodings`): UTF-8 if it offers it (no conversion),
  otherwise UTF-16, converted per line from the line index.
- **One thread, debounced by the input.** Edits are applied as they arrive;
  analysis runs when no more input is waiting (at most 50 ms behind the
  edits), so a burst of keystrokes costs one analysis. Requests needing
  results run it first if it's stale. The GIL is held only while zgram and
  zrules run (and custom rules), released while waiting for input.
- **The project.** The workspace's files with the configured extensions, read
  from disk, with open buffers taking precedence; `analyze_project` over all
  of them with the rules' `resolve`. Trees of unchanged files are reused: an
  edit reparses one file. Without `rules`, each file is parsed alone.
- **Failures.** A Python exception in a custom rule becomes a
  `window/logMessage`, and the last good analysis is kept; the server never
  dies on bad input. `$/cancelRequest` drops queued requests.
- **Testing and embedding:** `server.handle(message) -> [messages]` runs one
  message without I/O; `start_io()` runs the loop over stdin/stdout (what
  every editor launches).
- **Native results:** trees through zgram's `zgram.tree.v1` capsule, the
  symbol table through zrules' `zrules.analysis.v1`, selectors through
  `zrules.selector.v1`: after the capsules, an edit of a 553 KB file costs
  18.5 ms (parse, check, publish), 2.2 ms for 54 KB.

### Needs from zgram and zrules

- zgram: the grammar's literals (keywords for highlighting and completion),
  `parser.literals()`.
- zrules: selectors usable on their own (`symbols=`, `tokens=`, `folding=`
  are selectors, matched by zrules' engine, not a second one):
  `Selector(parser, text).match(tree) -> [node]`.
- zrules: the names visible at a position, with its exact scope rules
  (`ordered`, `hoist`, `after`, `outside`, builtins, imports):
  `Analysis.visible(offset, namespace="name") -> [Symbol]`.
- zlsp depends on zrules-py even without `rules=` (for selectors).

All done: zgram 0.3.3 (`literals()`), zrules 0.1.3 (`Selector`,
`visible()`) and 0.1.4 (the capsules).

## The demo language: "tiny"

Small but complete: every piece of the suite gets exercised, and it becomes
the tutorial. The zgram part exists: `zgram/examples/tiny/tiny.py` is the
grammar, the AST and a stand-in interpreter (until zrun), tested in
`zgram/test/test_example_tiny.py`. Writing it changed zgram's error messages
(they now name the outermost rule that failed where it started), and added
display names (`expr "expression" = ...`) and `-> Break()`. The grammar as first
sketched (zgram 0.2, with AST mapping):

```
program   = ws (body:stmt ws)*                               -> Program
@silent stmt = funcdef | while_stmt | if_stmt | return_stmt | break_stmt
             | let_stmt | assign | expr_stmt
funcdef   = 'fn' ws name:ident ws '(' ws params:params? ws ')' ws body:block  -> FuncDef
params    = ident (ws ',' ws ident)*                         -> list
block     = '{' ws (stmt ws)* '}'                            -> list
while_stmt  = 'while' ws cond:expr ws body:block             -> While
if_stmt     = 'if' ws cond:expr ws then:block (ws 'else' ws else_:block)?  -> If
return_stmt = 'return' (ws value:expr)? ws ';'               -> Return
break_stmt  = 'break' ws ';'                                 -> Break
let_stmt    = 'let' ws name:ident ws '=' ws value:expr ws ';'  -> Let
assign      = name:ident ws '=' ws value:expr ws ';'         -> Assign
@silent expr_stmt = expr ws ';'
@silent expr = compare
@left compare = left:sum (ws op:cmpop ws right:sum)?         -> BinOp
@left sum     = left:product (ws op:addop ws right:product)* -> BinOp
@left product = left:unary (ws op:mulop ws right:unary)*     -> BinOp
@silent unary = neg | primary
neg       = '-' ws operand:unary                             -> Neg
@silent primary = number | string | call | ident | '(' ws expr ws ')'
call      = name:ident ws '(' ws args:args? ws ')'           -> Call
args      = expr (ws ',' ws expr)*                           -> list
number    = [0-9]+ ('.' [0-9]+)?                             -> Number
string    = '"' [^"]* '"'                                    -> String
ident     = !keyword [a-zA-Z_] [a-zA-Z0-9_]*                 -> Name
@silent keyword = ('fn' | 'while' | 'if' | 'else' | 'return' | 'break' | 'let') ![a-zA-Z0-9_]
cmpop = '==' | '!=' | '<=' | '>=' | '<' | '>'                -> str
addop = [+\-]                                                -> str
mulop = [*/%]                                                -> str
@silent ws    = ([ \t\n\r] | '#' [^\n]*)*
```

Rules (zrules):

```python
rules = Rules(tiny, [
    inside("Break", within="While", stop_at="FuncDef", message="'break' outside loop"),
    inside("Return", within="FuncDef", message="'return' outside function"),
    unique("FuncDef > params > Name", message="duplicate parameter '{text}'"),
    scopes(scope=("Program", "FuncDef", "block"),
           define=("Let > .name", "FuncDef > params > Name", "FuncDef > .name"),
           use=("Name",), hoist=("FuncDef > .name",),
           on_undefined="error"),
])
```

Program:

```
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

Running it: `Interpreter(tiny_ast, rules).run(source)` prints the first ten
Fibonacci numbers. Error cases the suite must report well: `break` outside a
loop, undefined names, duplicate parameters, calling an undefined function,
and a syntax error in the middle of the file.

## Roadmap

| Milestone | Contents |
|---|---|
| zgram 0.2 (released) | Labels, `@left`/`@right`, AST mapping (native built-ins, Python classes), `parse_ast`, `Tree` + `TREE_ABI` capsule, `Diagnostic` |
| zrules 0.1 (released, 0.1.7) | Selectors, `inside`/`unique`/`forbid`/`require`/`count`, scopes and symbol tables, member access, imports across files, types, control flow, Python rules, diagnostics, the analysis and selector capsules, `analyze(builtins=)` |
| zgram 0.3 (released) | Error recovery (automatic, and sync points named in the grammar): several errors per parse, a tree with error nodes |
| zgram 0.4 (released, 0.4.2) | `parser.labels()`; the `zgram.llvm.v1` capsule (LLVM's C API, the JIT, object files, bitcode) |
| zlsp 0.1 (released, 0.1.2) | Native core; diagnostics, go-to-definition, references, rename, hover, highlighting, outline, folding, completion, workspace symbols, signature help, inlay hints, code actions, incremental checking |
| zrun 0.1 (released) | Semantics in Python compiled by partial evaluation: compiled (tiers, `mode="auto"`), Python and ahead-of-time (compiled modules) execution; unboxed values for typed code, tagged values with speculation for untyped code; reference counting with a cycle collector; engines (entry points called many times, in parallel, on zero-copy data; native host functions); runtime diagnostics; sessions and a REPL; zgram's LLVM through its capsule |
| zgram 0.5 (released) | Compiled grammars kept on disk; alternatives guarded by their first bytes, rules called once inlined (fastest or tied in every benchmark); recovery on real files |
| zrules 0.2 (released) | Generic functions and types, unions, subtyping between declared types; control flow that knows `goto` |
| zrun 0.2-0.3 (released) | Executables (`build_executable`, Linux and Windows, from either); a bounded cache; `rt.tail_call`; Lua returns without lists |
| zrun next | Untyped code closer to a hand-written interpreter (Lua: 1.6-4x PUC-Rio's) |
| Later | macOS and ARM (an LLVM with the AArch64 backend, zgram's JIT per architecture) |

Each milestone ships when "tiny" (and its tests) exercises the new features.

## Open questions

Settled and implemented in zgram: labels, `-> name` actions and `parse_ast`;
`@left`/`@right`/`@postfix` folding in the tree; AST objects built from the
tree after the parse; the node layout (12-bit child count, 12-bit rule id,
8-bit global field id); the value of a rule with no action; `parse_tree`,
`Tree` and the `zgram.tree.v1` capsule; the native `Diagnostic`; errors at
the furthest failure for prefix matches. Settled for
zrules: selectors take rule names, with class names as aliases and `.field`
for labels.

1. **Column units:** `Diagnostic.column` counts bytes, as zgram always has.
   zlsp needs UTF-16 units; decide where the conversion lives.
2. **Error recovery:** zgram reports one syntax error per parse. zlsp wants
   several per file and a partial tree to keep working on.
3. **Cost of a failing parse**: measured (2026-10-08, nmap's Lua library):
   a failing parse is 6-7x a successful one; recovering from one error
   costs 6 ms on a 190 KB file, 100 ms on 3 MB (each round re-parses the
   whole input). Fine for zlsp; recovery quality was the real issue (fixed:
   zgram's CHANGELOG, Unreleased).
4. **Type inference scope** in zrules: settled as local inference with
   gradual unknowns, with user-defined generic functions and types, unions
   and subtyping between declared types (zrules 0.2).
5. **Sharing LLVM** between zgram and zrun: settled, zgram's capsule exports
   the LLVM C API and its JIT; zrun has no LLVM of its own.
6. **Incremental parsing** for zlsp on large files: not needed. A full
   parse of 3 MB is 14 ms; files a language server sees are far smaller.
