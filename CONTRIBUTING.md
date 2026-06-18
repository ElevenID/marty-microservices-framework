# Contributing to Marty Microservices Framework

Thank you for your interest in contributing. This document describes the contribution process and guidelines.

---

## Types of Contributions

### 1. Bug Reports

- Open an issue with label `bug`
- Include: Python version, OS, framework version, steps to reproduce, and expected vs. actual behavior
- Attach a minimal reproducing example where possible

### 2. Feature Requests

- Open an issue with label `enhancement`
- Describe the use-case motivation and any API surface you have in mind
- Breaking API changes require discussion before a PR is opened

### 3. Documentation Fixes

- Open a PR with label `docs`
- Fixes to README, docstrings, or files under `docs/` are always welcome

### 4. Platform Plugin Contributions

- Open an issue with label `plugin` before writing code
- Plugins live under `platform_plugins/`; follow the interface defined in `mmf/platform/`
- Include tests under `tests/` and an example under `examples/`

### 5. Test Coverage

- Open a PR with label `tests`
- New tests must use the existing pytest fixtures; see `tests/conftest.py`
- Do not reduce overall coverage below the current threshold recorded in `pyproject.toml`

---

## Pull Request Process

1. Fork the repository and create a branch: `feat/`, `fix/`, `docs/`, `test/`, `chore/`
2. Make your changes with clear, atomic commit messages
3. Run the test suite locally: `uv run pytest`
4. Run the linter: `uv run ruff check .`
5. Update `CHANGELOG.md` under `[Unreleased]`
6. Open a PR against `main` with a description of the change and its version impact

---

## License and Copyright

This project is licensed under the **GNU Affero General Public License v3 (AGPL-3.0-only)**. By submitting a contribution you agree that your contribution will be licensed under the same terms.

### Important AGPL Note

If you deploy a modified version of this framework to provide a network service to others, the AGPL requires that you make the complete corresponding source code of your modified version available to those users. See the LICENSE file and [AGPL FAQ](https://www.gnu.org/licenses/gpl-faq.html#AGPLv3InteractingRemotely) for details.

### Developer Certificate of Origin (DCO)

All commits must be signed off to certify you have the right to submit the contribution under the AGPL-3.0-only license. Add a sign-off to every commit:

```
git commit -s -m "your commit message"
```

This adds a `Signed-off-by: Your Name <email@example.com>` trailer. See <https://developercertificate.org/> for the full DCO text. PRs with unsigned commits will not be merged.

---

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating you agree to abide by its terms.

---

## Version Impact Reference

| Contribution Type | Typical Version Impact |
|---|---|
| Bug fix (no API change) | PATCH |
| Deprecation of existing API | MINOR |
| New public API (backward-compatible) | MINOR |
| Removal or incompatible change to public API | MAJOR |
| New platform plugin | MINOR |
| Documentation or test only | PATCH |
