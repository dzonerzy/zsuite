# Best practices

What makes a zsuite language pleasant to use and fast to run, stage by stage.
The [tutorial](tutorial.md) shows the basics; this is what to do as the
language grows.

## Grammars

**Label what anything downstream reads.** Rules, semantics and the editor
reach a node's parts by label (`node.cond`, `"FuncDef > .name"`), never by
position. A label that may repeat (`params:ident (ws ',' ws params:ident)*`)
is a list; under `?` it's the node or `None`.

**Give each construct a kind.** `-> While`, `-> FuncDef`: rules and semantics
select on kinds, and several rules can share one (`expr`, `sum` and `term` are
all `BinOp`). Make helper rules `@silent` so they don't add levels to the
tree.

**Keywords end at a word boundary.** Follow each keyword with a silent
lookahead, and keep identifiers from being keywords:

```
while_stmt = 'while' kw ws cond:expr ws body:block
@silent keyword = ('fn' | 'while' | 'if' | 'else' | 'return') kw
@silent kw      = ![a-zA-Z0-9_]
ident           = !keyword [a-zA-Z_] [a-zA-Z0-9_]*
```

Word literals are also what zlsp highlights and completes as keywords.

**One whitespace rule, comments included.** `@silent ws = ([ \t\n\r] | '#'
[^\n]*)*`, written wherever whitespace may appear. Lists of statements as
`(stmt ws)*`.

**Fold operators, don't nest by hand.** `@left` for left-associative
operators, `@right` for right-associative ones, `@postfix` for calls, indexing
and member access (`a.b(c)[d]`). Each level gets exactly `left`, `op`,
`right` (or `target`), and a lone operand isn't wrapped.

**Name rules for error messages.** `ident "name" = ...`, `expr "expression" =
...`: errors read "expected expression", not "expected sum".

**Avoid exponential backtracking.** Two alternatives that share a long prefix
re-parse it: `type = union | single` where a union begins with a single. Write
it as one rule with a suffix chain (`@postfix type = members:single
union_tail*`), or factor the prefix out. `@memo` helps a rule that's re-tried
at the same position, at the cost of a table lookup per call: add it where
profiling shows retries, not everywhere.

**Shape the grammar for error recovery.** zgram recovers without grammar
changes, best when the grammar has the usual shapes:

- statements and items as repetitions (`(stmt ws)*`, `(item (ws ',' ws item)*)?`),
  so a broken one is skipped and the rest kept;
- closing brackets and words (`}`, `end`) as literals, so a missing one is
  inserted and a stray one recognized;
- separators as literals or small punctuation classes (`','`, `[,;]`), so a
  missing one is inserted;
- the word that decides a construct first (`'let' kw ...`): it's never made up.

For statements that end at a terminator, `@recover(';')` makes a broken one
end there. Try broken input as you write the grammar:
`parser.parse_tree(src, recover=True).errors`.

## Rules

**Give every rule a code.** `code="break-outside-loop"`: diagnostics carry it,
tests match on it, editor quick fixes key on it, users search for it. Write
messages for the user, with the node's text where it helps (`"duplicate
parameter '{text}'"`).

**Model the names exactly.** Most of a language's checks are its scoping, and
`scopes()` has an option for each common rule: `define_outer` (a function's
name lives outside it), `hoist` (usable before its definition), `after`
(`let a = a` sees the outer `a`), `ordered` (visible only after its
definition), `members` (`a.b`), imports. Separate namespaces (types and
values, labels) are separate `scopes()` rules. Report unused names
(`on_unused="warning"`) once the scoping is right.

**Add types when the language has them.** `types()` is gradual: start with
literals and declarations, add operators, calls and structs; anything unknown
is compatible, so a partial setup never reports false errors. A typed language
gets more than errors: zrun compiles typed code to unboxed values, and zlsp
shows types in hover, signature help and inlay hints.

**Add `flow()` for languages with returns and loops**: unreachable code,
functions that may end without returning, variables read before they have a
value, `goto` to missing labels.

**Write Python rules last.** `@rules.rule(selector)` can check anything, but
it runs in Python, per node, with the GIL held. Prefer the declarative rules;
use Python for what only the language knows.

**Check real code.** Run the rules over every file of the language you can
find: zrules' Lua checker runs over 830 real-world files, with no false error
allowed.

## Semantics

**Branch on the node, not on values.** Anything computed from the node (its
kind, its operator text, the number of its children) is decided while
compiling and costs nothing. `if node.op == "+"` is free; looking an operator
up in a dict of Python functions and calling one isn't.

**Use the values zrun knows.** Ints, floats, bools, strs, lists, dicts, tuples
and records are native in compiled code. Make the language's objects records:
dataclasses or classes with `__slots__`, whose methods compile too. An
instance of an ordinary class, a set or `bytes` is a Python object: every
operation on it goes through Python.

**Don't allocate on the common path.** Each list, dict or record made is
allocation, reference counting and collection. Return one value as itself,
not a one-item list (Lua's single results); create a part of an object only
when it's used (a Lua table's hash part); avoid temporary lists for things
known in advance.

**Wrap integers with `rt.wrapping_*`.** Ints are 64-bit and checked: an
overflow is the program's error. For a language whose ints wrap (Lua, hashes,
bit tricks), use `rt.wrapping_add`, `_sub`, `_mul`, `_shl`, `_shr`, `_ushr`.
Wrapping by hand (`(a + b) & 0xFFFFFFFFFFFFFFFF`, then the sign) makes 128-bit
arithmetic first.

**Keep lists of one kind.** A list whose items are all ints, or all floats, is
marked so, and reads from it need no checks.

**Use `rt.tail_call` where the language guarantees tail calls.** `return
f(x)` in Lua or Scheme: the frame is given up first, so tail recursion runs in
constant stack, in every mode.

**Make everything compile.** `lang.python_semantics()` should be empty: each
entry says which semantic runs as Python, and why. Then run with
`report=True` and read `program.report()["python_crossings"]`: each line is a
place compiled code went through Python, with a count. Fix the biggest.

**Host functions: small, or native.** A small Python host function compiles
inline. One that does real work in Python is a call into Python each time; for
a hot one, write it in Zig or C and register it with `lang.native_host`.

zrun's [guide to writing fast
semantics](https://github.com/dzonerzy/zrun/blob/main/docs/writing-fast-semantics.md)
has the full list of what compiles.

## Testing

**Run every program in both modes and compare.** The reference
(`mode="python"`) is the definition; compiled code must print the same and
fail the same way: the same message, at the same node, with the same call
stack. A difference is a zrun bug worth reporting.

**Test each stage on its own.** The grammar on valid and broken input (and
the errors recovery reports), the rules on programs that should and shouldn't
pass (match on codes), the semantics on programs and their output, the server
through `server.handle(message)` without an editor.

**Test what users will write wrong.** Undefined names, misplaced statements,
unclosed brackets, a missing separator: the error messages are part of the
language.

## Editor support

**Say what each definition is.** `symbols={"FuncDef > .name": "function",
...}` drives the outline, highlighting and completion; names without a kind
are guessed from their type and use.

**Highlight with selectors.** `tokens={"number": "number", "string":
"string"}`; keywords come from the grammar's word literals, comments from
`comments=`.

**Use hooks for what only the language knows**: documentation in hover,
snippets in completion, quick fixes for its own diagnostics, a formatter, the
editor's settings for rules that need them.

**Generate the TextMate grammar** (`server.textmate()`) for VS Code, so files
are colored before the server answers.

## Shipping and running

**Compiled code is cached.** zgram keeps compiled grammars and zrun compiled
programs in the platform's cache directory, so only the first run of a
program pays for compiling. Where the home directory isn't writable, point
them elsewhere: `zgram.configure(cache=...)`, `zrun.configure(cache=...)`.

**Programs or engines.** A script runs once from its start: `program.run()`.
An engine (rules, filters, queries) is loaded once and called many times:
`program.call()` from Python, about 0.15 µs a call, and `program.map()` over
many inputs on native threads, with data passed as `zrun.Bytes`, not copied.
Calls that never touch Python run in parallel; `report()["gil_taken"]` says
whether they do.

**Ship programs as executables** (`zrun.build_executable`) to machines
without Python, and engines' rule sets as **compiled modules**
(`lang.compile`, `lang.load_compiled`) to skip compiling on every start.
