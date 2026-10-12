# Changelog

All notable changes to zsuite are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.3] - 2026-10-13

### Fixed
- **zrun-py 0.7.4**: compiled code of a helper changing or passing on a known list or dict inside its `try` body (after a call there that may fail): rejected by LLVM ("Instruction does not dominate all uses"), or the list changed while compiling instead of at run time; and, in 0.7.3, a known list changed by a helper inside its caller's `if` or loop changed only once, whichever path ran. The `exe` extra asks for it too.

## [0.4.2] - 2026-10-11

### Changed
- **zrun-py 0.7.2**: more natively in compiled code and standalone programs: reading and writing files, stdin, `os.getenv()`/`os.path`, Python's `OSError`s; `repr()`, Unicode `lower()`/`upper()`/`isalpha()`, `<<`/`>>`, `node.find()`; a strict language's module table native all through; methods dispatched by number (about 10% faster on method-heavy code). The `exe` extra asks for it too.

## [0.4.1] - 2026-10-11

### Fixed
- **zrun-py 0.7.1**: crashes and leaks fixed in compiled code (a parsed node kept in a record, a loop over known tuples, known lists inside lists), module-level sets native in strict languages.
- **The `exe` extra** asked for zrun-py 0.6, which the suite's own zrun-py 0.7 requirement excludes: `zsuite[exe]` couldn't be installed. It asks for 0.7.1 now.

## [0.4.0] - 2026-10-11

### Changed
- **zgram-py 0.6.0**: parsers built ahead of time (`GrammarParser.build()`: an object file, a C header and zgram's runtime, for programs in any language with no Python and no LLVM: the same trees and error messages), and `GrammarParser.capsule` for native code in other packages.
- **zrun-py 0.7.0**: `rt.parse(grammar, text)`, text parsed with a zgram grammar while a program runs and read as its own nodes; natively in compiled code, strict languages and standalone programs.

## [0.3.2] - 2026-10-11

### Fixed
- **zgram-py 0.5.4**: a syntax error message about a non-ASCII class or a partial UTF-8 literal raised `UnicodeDecodeError` instead of `ParseError`; such bytes are written `\xHH` now.

## [0.3.1] - 2026-10-11

### Changed
- **zgram-py 0.5.3**: `\xHH` escapes in grammars' character classes and literals, to match non-ASCII text exactly (`[\x80-\xff]`, `'\xe2\x80\x93'` for an en dash).

## [0.3.0] - 2026-10-10

### Changed
- **zrun-py 0.6**: standalone programs half the size and built faster, their objects cached between builds; for Windows and from either system (`build_native(target=...)`); libraries with a C API (`build_native(shared=True)`); a program's arguments (`setup=`); a float's digits natively on every platform.

## [0.2.0] - 2026-10-10

### Changed
- **zrun-py 0.5** (and zgram-py 0.5.2): strict languages, `@zrun.comptime`, native errors, closures, sets, bytes, `struct`, printing, and standalone programs (`zrun.build_native`: a strict language's program as an executable with no Python). `zsuite-py[exe]` brings Zig for those too.

## [0.1.0] - 2026-10-08

The first release.

### Added
- **`zsuite-py`**: installs zgram-py 0.5, zrules-py 0.2, zrun-py 0.4 and zlsp-py 0.1, the versions that work together; `zsuite-py[exe]` adds what executables need.
- **`zsuite new NAME`**: a language project (grammar, rules, semantics, language server, a command line and tests), the tutorial's language under its new name: it runs, checks, serves an editor and passes its tests from the start.
- **`zsuite versions`** and `zsuite.versions()`: the suite's installed versions.
- **Documentation**: the tutorial (building tiny through all four stages), best practices, and the suite's design.
- **examples/tiny**: the tutorial's language, one file per stage, with its tests.
