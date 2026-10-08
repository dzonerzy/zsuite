"""`zsuite new NAME`: a language project made from the tutorial's language.

The template is examples/tiny (packaged as zsuite/template): its files are
copied with `tiny` renamed to the new language's name, in their names and
their text, so the project runs, checks, serves an editor and passes its
tests from the start.
"""

import keyword
import os
import re

TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "template")
# (in a checkout, before building: the example itself)
SOURCE_TREE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "examples", "tiny")
FILES = ("syntax.py", "checks.py", "semantics.py", "server.py", "tiny.py", "test_tiny.py", "fib.tiny")
# (modules of the template: a language named like one would shadow it)
TAKEN = {"syntax", "checks", "semantics", "server", "zgram", "zrules", "zrun", "zlsp", "zsuite", "test"}


def template_dir():
    if os.path.isdir(TEMPLATE):
        return TEMPLATE
    if os.path.isdir(SOURCE_TREE):
        return SOURCE_TREE
    raise FileNotFoundError("zsuite's template is missing (a broken install?)")


def check_name(name):
    if not re.fullmatch(r"[a-z][a-z0-9_]*", name or ""):
        raise ValueError("a language's name is lowercase letters, digits and _, starting with a letter: %r" % name)
    if keyword.iskeyword(name) or name in TAKEN:
        raise ValueError("%r can't be a language's name here (a Python keyword, or a module of the project)" % name)


def new(name, directory=None):
    check_name(name)
    target = os.path.abspath(directory or name)
    if os.path.exists(target) and os.listdir(target):
        raise FileExistsError("%s exists and isn't empty" % target)
    os.makedirs(target, exist_ok=True)
    source = template_dir()
    word = re.compile(r"\btiny\b")
    for f in FILES:
        with open(os.path.join(source, f), encoding="utf-8") as src:
            text = word.sub(name, src.read())
        out = f.replace("tiny", name)
        with open(os.path.join(target, out), "w", encoding="utf-8", newline="\n") as dst:
            dst.write(text)
    return target
