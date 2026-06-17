# Contributing

Contributions are welcome. Please open an issue before submitting large changes.

## Development setup

```bash
git clone https://github.com/amaar-mc/scoreboarding
cd scoreboarding
uv venv .venv
uv pip install -e ".[dev]"
```

## Quality gates (all must pass)

```bash
uv run pytest -q
uv run ruff check .
uv run mypy src
uv build
```

## Code style

- Python 3.10+, strict mypy, ruff lint.
- No default parameter values in public API functions -- use keyword-only arguments.
- No `TODO` or `FIXME` in committed code -- implement or note the omission in an issue.
- Commit format: `type(scope): description`.

## Testing

New behaviour must be accompanied by tests. Bug fixes must include a failing test
that demonstrates the bug before the fix is applied.

## License

By contributing you agree that your changes are licensed under the MIT License.
