"""The zsuite package: the suite installed together, and `zsuite new`."""

import os
import subprocess
import sys

import pytest
import zsuite
from zsuite.__main__ import main


def test_every_package_installed():
    v = zsuite.versions()
    assert set(v) == {"zsuite", "zgram", "zrules", "zrun", "zlsp"}
    assert all(v.values()), v


def test_the_versions_command(capsys):
    assert main(["versions"]) == 0
    assert "zgram" in capsys.readouterr().out


@pytest.mark.parametrize("bad", ["", "Foo", "1lang", "my-lang", "class", "syntax", "zrun"])
def test_bad_names(bad, tmp_path):
    with pytest.raises(ValueError):
        zsuite.new(bad, str(tmp_path / "x"))


def test_not_over_a_project(tmp_path):
    (tmp_path / "taken").mkdir()
    (tmp_path / "taken" / "a.txt").write_text("x")
    with pytest.raises(FileExistsError):
        zsuite.new("calc", str(tmp_path / "taken"))


def test_a_new_language_runs_and_passes_its_tests(tmp_path):
    path = zsuite.new("calc", str(tmp_path / "calc"))
    assert sorted(os.listdir(path)) == ["calc.py", "checks.py", "fib.calc", "semantics.py", "server.py", "syntax.py", "test_calc.py"]
    run = subprocess.run([sys.executable, "calc.py", "run", "fib.calc"], cwd=path, capture_output=True, text=True, timeout=600)
    assert run.returncode == 0, run.stderr
    assert run.stdout.split() == ["0", "1", "1", "2", "3", "5", "8", "13", "21", "34"]
    check = subprocess.run([sys.executable, "calc.py", "check", "fib.calc"], cwd=path, capture_output=True, text=True, timeout=600)
    assert check.returncode == 0, check.stderr
    tests = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "test_calc.py"], cwd=path, capture_output=True, text=True, timeout=600)
    assert tests.returncode == 0, tests.stdout + tests.stderr
