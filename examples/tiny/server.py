"""tiny in an editor: a language server from the grammar and the rules.

The editor gets, as you type: every syntax error, the rules' findings, go to
definition, references, rename, hover, signature help, completion, the
outline, highlighting and folding. The hook adds what only the language
knows: the builtins' docs in hover.
"""

from zlsp import Server

from checks import RULES
from syntax import PARSER

BUILTIN_DOCS = {"print": "Writes its arguments, separated by spaces, then a new line."}


def hover(uri, text, offset, analysis):
    """The docs of a builtin, below what the server shows of it."""
    symbol = analysis.at(offset) if analysis is not None else None
    if symbol is not None and symbol.builtin:
        return BUILTIN_DOCS.get(symbol.name)
    return None


def make_server():
    return Server(
        PARSER,
        RULES,
        name="tiny",
        extensions=[".tiny"],
        # What names are: for the outline, highlighting and completion
        symbols={"FuncDef > .name": "function", "FuncDef > .params": "parameter", "Let > .name": "variable"},
        tokens={"number": "number", "string": "string", "cmpop, addop, mulop": "operator"},
        comments=["#"],
        hover=hover,
    )
