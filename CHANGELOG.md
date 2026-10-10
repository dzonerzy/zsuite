# Changelog

All notable changes to zsuite are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
