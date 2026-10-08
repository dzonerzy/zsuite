"""tiny's tests: each stage, and the program the same in every mode."""

import io
import json
import os
from contextlib import redirect_stdout

import pytest
import zgram
import zrun

from checks import RULES
from semantics import lang
from server import make_server
from syntax import PARSER

HERE = os.path.dirname(os.path.abspath(__file__))
FIB = open(os.path.join(HERE, "fib.tiny"), encoding="utf-8").read()


def test_the_grammar_makes_the_tree():
    tree = PARSER.parse("fn f(a) { return a + 1; }\n")
    func = tree[0]
    assert func.rule() == "funcdef"
    assert func.get("name").text() == "f"
    assert [p.text() for p in func.get_all("params")] == ["a"]


def test_every_syntax_error_at_once():
    tree = PARSER.parse_tree("let a = ;\nlet b = 2;\nlet c = * 3;\n", recover=True)
    assert [(e.line, e.message) for e in tree.errors] == [(1, "expected expression"), (3, "expected expression")]


def test_the_rules():
    found = [(d.code, d.line) for d in RULES.check("break;\nprint(nope);\nfn f(x) { return 1; }\nf(1);\n")]
    assert found == [("break-outside-loop", 1), ("undefined-name", 2), ("unused-name", 3)]


@pytest.mark.parametrize("mode", ["python", "compiled"])
def test_fib_in_every_mode(mode):
    out = io.StringIO()
    with redirect_stdout(out):
        lang.load(FIB, "fib.tiny").run(mode=mode)
    assert out.getvalue().split() == ["0", "1", "1", "2", "3", "5", "8", "13", "21", "34"]


@pytest.mark.parametrize("mode", ["python", "compiled"])
def test_runtime_errors_say_where(mode):
    with pytest.raises(zrun.Error) as e:
        lang.load("fn f(x) { return x / 0; }\nprint(f(1));\n", "div.tiny").run(mode=mode)
    assert "division by zero" in str(e.value) and "div.tiny:1:" in str(e.value)


def test_load_refuses_invalid_programs():
    with pytest.raises(zrun.LoadError):
        lang.load("break;\n", "bad.tiny")
    with pytest.raises(zrun.LoadError):
        lang.load("let = ;\n", "bad.tiny")


def message(id_, method, params):
    m = {"jsonrpc": "2.0", "method": method, "params": params}
    if id_ is not None:
        m["id"] = id_
    return json.dumps(m)


def test_the_language_server():
    server = make_server()
    server.handle(message(1, "initialize", {"capabilities": {}}))
    server.handle(message(None, "initialized", {}))
    out = [json.loads(m) for m in server.handle(message(None, "textDocument/didOpen", {"textDocument": {"uri": "file:///a.tiny", "languageId": "tiny", "version": 1, "text": "print(nope);\n"}}))]
    published = [m for m in out if m.get("method") == "textDocument/publishDiagnostics"]
    assert [d["code"] for d in published[-1]["params"]["diagnostics"]] == ["undefined-name"]
    # (hover on a builtin: the hook's docs)
    replies = [json.loads(m) for m in server.handle(message(2, "textDocument/hover", {"textDocument": {"uri": "file:///a.tiny"}, "position": {"line": 0, "character": 2}}))]
    hover = [r for r in replies if r.get("id") == 2][0]["result"]
    assert "Writes its arguments" in hover["contents"]["value"]


def test_the_parse_error_object():
    with pytest.raises(zgram.ParseError) as e:
        PARSER.parse("let x = ;")
    assert e.value.diagnostic.code == "syntax"
