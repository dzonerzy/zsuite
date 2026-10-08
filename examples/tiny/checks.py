"""tiny's checks: what makes a well-formed program valid, as zrules rules.

Selectors name nodes by the grammar's kinds and labels: `Break` is a
`break_stmt` node (its `-> Break()`), `FuncDef > .params` the children
labelled `params` of a function.
"""

from zrules import Rules, forbid, inside, scopes

from syntax import PARSER

RULES = Rules(
    PARSER,
    [
        inside("Break", within="While", stop_at="FuncDef", code="break-outside-loop", message="'break' outside loop"),
        inside("Return", within="FuncDef", code="return-outside-function", message="'return' outside function"),
        forbid("FuncDef FuncDef", code="nested-function", message="functions cannot be defined inside functions"),
        # One namespace: variables, parameters and functions. A function's
        # own name belongs to the scope outside it and is visible before its
        # definition; everything else is visible from its definition on.
        scopes(
            scope=("Program", "FuncDef"),
            define=("Let > .name", "FuncDef > .params"),
            define_outer="FuncDef > .name",
            use="Name",
            hoist="FuncDef > .name",
            after="Let > .name",  # `let a = a;` doesn't see the new `a`
            builtins=("print",),
            on_unused="warning",
        ),
    ],
)
