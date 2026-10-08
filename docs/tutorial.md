# Building a language with zsuite

This tutorial builds **tiny**, a small language with functions, variables,
loops and recursion, through all four stages of the suite:

1. **Syntax** with zgram: a grammar, compiled to a native parser.
2. **Checks** with zrules: the program's names and the language's rules.
3. **Meaning** with zrun: what each kind of node does, compiled to native code.
4. **An editor** with zlsp: errors as you type, navigation, completion.

Then it ships tiny as an executable and tests it. The finished language is in
[examples/tiny](../examples/tiny): one file per stage, about 300 lines in all.

```bash
pip install zsuite-py          # zgram-py, zrules-py, zrun-py, zlsp-py
```

A tiny program:

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

## 1. Syntax: the grammar

zgram takes a PEG grammar and compiles it, in the process, to a native parser.
[syntax.py](../examples/tiny/syntax.py) is tiny's. Its statements:

```
program     = ws (body:stmt ws)*                                      -> Program
@silent stmt = funcdef | while_stmt | if_stmt | return_stmt | break_stmt
             | let_stmt | assign | expr_stmt
funcdef     = 'fn' kw ws name:ident ws '(' ws (params:ident (ws ',' ws params:ident)*)? ws ')' ws body:block  -> FuncDef
block       = '{' ws (stmt ws)* '}'                                   -> list
while_stmt  = 'while' kw ws cond:expr ws body:block                   -> While
let_stmt    = 'let' kw ws name:ident ws '=' ws value:expr ws ';'      -> Let
...
```

Four things to notice, because the rest of the suite relies on them:

- **Labels** (`name:ident`, `cond:expr`, `body:block`) name a node's parts.
  The rules, the semantics and the editor all reach them by these names:
  `node.cond`, `"FuncDef > .name"`.
- **`-> Name`** gives a rule's nodes a kind name (`While`, `FuncDef`): what
  rules and semantics select on.
- **`@silent`** rules make no node of their own: `stmt` is a choice, not a
  level of the tree.
- **`kw` and `ws`**: `@silent kw = ![a-zA-Z0-9_]` after each keyword keeps
  `while` from matching the start of `whilex`; `ws` (whitespace and `#`
  comments) is written where it may appear.

Expressions use `@left` to fold operator chains into nested nodes, and
display names (`"expression"`) for error messages:

```
@left expr "expression" = left:sum (ws op:cmpop ws right:sum)?        -> BinOp
@left sum  "expression" = left:term (ws op:addop ws right:term)*      -> BinOp
@left term "expression" = left:operand (ws op:mulop ws right:operand)*  -> BinOp
```

`1 + 2 - 3` is `BinOp(BinOp(1, +, 2), -, 3)`; a lone `7` is just the number.

Compile and parse:

```python
import zgram
PARSER = zgram.compile(GRAMMAR)

tree = PARSER.parse("fn f(a) { return a + 1; }\n")
func = tree[0]
func.rule()                                   # 'funcdef'
func.get("name").text()                       # 'f'
[p.text() for p in func.get_all("params")]    # ['a']
```

A syntax error is a `zgram.ParseError` saying where and what was expected.
With `recover=True`, the parser reports every error and keeps going, which
is what an editor needs:

```python
tree = PARSER.parse_tree("let a = ;\nlet b = 2;\nlet c = * 3;\n", recover=True)
[(e.line, e.message) for e in tree.errors]
# [(1, 'expected expression'), (3, 'expected expression')]
```

The grammar compiles in a fraction of a second, and zgram keeps the compiled
parser on disk: the next process loads it in milliseconds.

## 2. Checks: the rules

A program that parses can still be wrong: a `break` outside a loop, a name
never defined. [checks.py](../examples/tiny/checks.py) says what tiny
requires, with zrules:

```python
from zrules import Rules, forbid, inside, scopes

RULES = Rules(PARSER, [
    inside("Break", within="While", stop_at="FuncDef", code="break-outside-loop",
           message="'break' outside loop"),
    inside("Return", within="FuncDef", code="return-outside-function",
           message="'return' outside function"),
    forbid("FuncDef FuncDef", code="nested-function",
           message="functions cannot be defined inside functions"),
    scopes(
        scope=("Program", "FuncDef"),
        define=("Let > .name", "FuncDef > .params"),
        define_outer="FuncDef > .name",
        use="Name",
        hoist="FuncDef > .name",
        after="Let > .name",
        builtins=("print",),
        on_unused="warning",
    ),
])
```

Rules select nodes with selectors over the grammar's kinds and labels:
`"Break"` is every `break_stmt`, `"FuncDef > .params"` the children of a
function labelled `params`. `inside` says where a node may appear; `scopes`
is the language's names:

- `scope`: the nodes that open a scope (the program, each function).
- `define`: what defines a name (a `let`'s name, a function's parameters).
- `define_outer`: a function's name belongs to the scope *around* the
  function, not its own.
- `hoist`: functions can be called before they're defined.
- `after`: in `let a = a;` the right side sees the outer `a`, not the new one.
- `builtins`: names the language provides.

```python
for d in RULES.check("let x = 1;\nbreak;\nprint(y);\n"):
    print(d.render(source, "bad.tiny"))
```

```
bad.tiny:1:5: warning: 'x' is never used [unused-name]
    1 | let x = 1;
      |     ^
bad.tiny:2:1: error: 'break' outside loop [break-outside-loop]
    2 | break;
      | ^^^^^^
bad.tiny:3:7: error: undefined name 'y' [undefined-name]
    3 | print(y);
      |       ^
```

`RULES.analyze(source)` gives the symbol table too: each name's definition and
uses, which zrun and zlsp both build on. A typed language adds a `types()`
rule (inference, generics, unions); a language with loops and returns can add
`flow()` (unreachable code, missing returns, unassigned variables). tiny
needs neither.

## 3. Meaning: the semantics

[semantics.py](../examples/tiny/semantics.py) says what each kind of node
*does*, one Python function each: an interpreter.

```python
import zrun

lang = zrun.Language(PARSER, RULES)
lang.function("FuncDef")        # these nodes define functions

@lang.exec("While")
def while_(node, rt):
    while rt.eval(node.cond):
        if not rt.loop(node.body):      # False: the body broke out
            break

@lang.exec(["Let", "Assign"])
def assign(node, rt):
    rt.store(node.name, rt.eval(node.value))

@lang.exec("Return")
def return_(node, rt):
    raise rt.Return(rt.eval(node.value) if node.value is not None else None)

@lang.eval("BinOp")
def binop(node, rt):
    a = rt.eval(node.left)
    b = rt.eval(node.right)
    op = node.op
    if op == "+":
        return a + b
    ...

@lang.eval("Call")
def call(node, rt):
    return rt.call(rt.eval(node.name), rt.eval(node.args))

@lang.host
def print(*args):
    builtins.print(*args)
```

- `@lang.eval(kind)` is an expression's value; `@lang.exec(kind)` a statement.
- `rt` is the runtime: `rt.eval`/`rt.exec` run a child node, `rt.store`/
  `rt.load` are the program's variables (by zrules' symbols: slots, not name
  lookups), `rt.call` calls a function, `rt.Return`/`rt.Break` are control flow.
- `lang.function("FuncDef")` makes `fn` nodes functions: zrun handles frames,
  arguments, recursion and the call stack in error messages.
- `@lang.host` is plain Python the program calls by name: anything goes.

Run it:

```python
program = lang.load(source, "fib.tiny")   # parse and check: zrun.LoadError lists the errors
program.run(mode="python")                # the reference: the semantics run as Python
program.run(mode="compiled")              # native code
```

Both print the same ten numbers. In compiled mode zrun runs your semantics
over the program's tree *while compiling*: everything known from the tree is
decided then. `if op == "+"` is a test on `node.op`, known for each node, so
compiled code has no test at all, just the add. The semantics stay a readable
interpreter; the program runs as native code.

Runtime errors are diagnostics too, at the node, with the language's call
stack:

```
div.tiny:1:18: error: division by zero [runtime]
    1 | fn f(x) { return x / 0; }
      |                  ^^^^^
  in f(), called at div.tiny:2:7
```

`lang.python_semantics()` lists any semantic that didn't compile (it runs as
Python, correctly but slower) and why; `program.run(mode="compiled",
report=True)` then `program.report()` shows where compiled code still goes
through Python. zrun's [guide to writing fast
semantics](https://github.com/dzonerzy/zrun/blob/main/docs/writing-fast-semantics.md)
covers what compiles and what makes it fast.

## 4. An editor: the language server

[server.py](../examples/tiny/server.py) gives tiny an editor, from the grammar
and the rules:

```python
from zlsp import Server

def make_server():
    return Server(
        PARSER, RULES,
        name="tiny",
        extensions=[".tiny"],
        symbols={"FuncDef > .name": "function", "FuncDef > .params": "parameter",
                 "Let > .name": "variable"},
        tokens={"number": "number", "string": "string",
                "cmpop, addop, mulop": "operator"},
        comments=["#"],
        hover=hover,
    )

make_server().start_io()       # speaks LSP on stdin/stdout
```

That's all it takes for: every syntax error and rule finding as you type, go
to definition, references, rename, hover, signature help, completion of the
names in scope and the keywords the grammar takes there, the outline,
highlighting and folding. `symbols` says what kind of thing each definition
is; `tokens` highlights the rest. Hooks add what only the language knows:
tiny's `hover` shows the builtins' docs.

To use it, point the editor at `python tiny.py lsp` for `*.tiny` files. In
Neovim:

```lua
vim.filetype.add({ extension = { tiny = "tiny" } })
vim.lsp.config("tiny", {
  cmd = { "python", "/path/to/tiny.py", "lsp" },
  filetypes = { "tiny" },
  root_markers = { ".git" },
})
vim.lsp.enable("tiny")
```

zlsp's README shows VS Code, Helix and Emacs.

## 5. Shipping

**An executable**, running the program on a machine without Python:

```bash
pip install "zrun-py[exe]"            # Zig, to build the launcher
python tiny.py build fib.tiny fib     # zrun.build_executable("semantics:lang", ...)
./fib
```

The file holds a Python runtime, the suite, tiny's modules, the program and
its compiled code (about 40 MB); it unpacks once and starts in a fraction of
a second after that. `target="x86_64-windows"` builds a Windows executable
from Linux, and the other way round.

**A compiled module**, for programs loaded again and again (rules an engine
runs): `lang.compile(source, "rules.zrc")` now, `lang.load_compiled(
"rules.zrc")` later, without compiling.

## 6. Testing

Test each stage on its own, and run every program in **both modes**: the
reference (`mode="python"`) is the definition, and compiled code must give the
same output and the same errors.
[test_tiny.py](../examples/tiny/test_tiny.py):

```python
@pytest.mark.parametrize("mode", ["python", "compiled"])
def test_fib_in_every_mode(mode):
    out = io.StringIO()
    with redirect_stdout(out):
        lang.load(FIB, "fib.tiny").run(mode=mode)
    assert out.getvalue().split() == ["0", "1", "1", "2", "3", "5", "8", "13", "21", "34"]
```

The language server is tested without an editor: `server.handle(message)`
runs one LSP message and returns the replies.

## Where to go from here

- [Best practices](best-practices.md): grammars that recover well, rules,
  semantics that compile fast, testing.
- Each package's README is its full reference:
  [zgram](https://github.com/dzonerzy/zgram),
  [zrules](https://github.com/dzonerzy/zrules),
  [zrun](https://github.com/dzonerzy/zrun),
  [zlsp](https://github.com/dzonerzy/zlsp).
- Bigger languages built this way: zrules' and zrun's `examples/lua` (Lua
  5.4: its full grammar, a checker run over real-world code, and an
  implementation passing Lua's test programs) and zrun's `examples/scan` (a
  YARA-like rule engine with native host functions).
