"""tiny's meaning: one function per kind of node, run by zrun.

This is an interpreter, written the natural way. zrun runs it as Python
(the reference), and compiles it with each program to native code.
"""

import builtins

import zrun

from checks import RULES
from syntax import PARSER

lang = zrun.Language(PARSER, RULES)

# `fn name(params) { body }` defines functions: zrun makes, calls and
# returns from them (frames, recursion, the call stack in errors)
lang.function("FuncDef")


@lang.exec("While")
def while_(node, rt):
    while rt.eval(node.cond):
        if not rt.loop(node.body):  # False: the body broke out
            break


@lang.exec("If")
def if_(node, rt):
    if rt.eval(node.cond):
        rt.exec(node.then)
    elif node.else_ is not None:
        rt.exec(node.else_)


@lang.exec("Return")
def return_(node, rt):
    raise rt.Return(rt.eval(node.value) if node.value is not None else None)


@lang.exec("Break")
def break_(node, rt):
    raise rt.Break()


@lang.exec(["Let", "Assign"])
def assign(node, rt):
    rt.store(node.name, rt.eval(node.value))


@lang.eval("BinOp")
def binop(node, rt):
    a = rt.eval(node.left)
    b = rt.eval(node.right)
    # (`node.op` is known for each node while compiling: these tests cost
    # nothing in compiled code, only the operation chosen remains)
    op = node.op
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    if op == "/":
        return a // b
    if op == "%":
        return a % b
    if op == "==":
        return a == b
    if op == "!=":
        return a != b
    if op == "<":
        return a < b
    if op == "<=":
        return a <= b
    if op == ">":
        return a > b
    return a >= b


@lang.eval("Neg")
def neg(node, rt):
    return -rt.eval(node.operand)


@lang.eval("Call")
def call(node, rt):
    return rt.call(rt.eval(node.name), rt.eval(node.args))


@lang.host
def print(*args):
    builtins.print(*args)
