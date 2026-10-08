# Contributing

Thanks for helping improve the Cybersecurity Career Roadmap.

## Before a change

- Check `ROADMAP.md` and existing issues for the active release scope.
- Keep workbook-derived personal data, databases, credentials, and lab evidence out of commits.
- Preserve source values and note any uncertain mapping instead of silently rewriting it.

## Development

1. Use Python 3.11 or newer.
2. Create a virtual environment and install `requirements.txt`.
3. Keep database, import, service, and UI code in their existing modules.
4. Add or update tests for behavior changes.
5. Run `python -m unittest discover -s tests -v` before opening a pull request.

Use conventional commit messages such as `feat: add roadmap progress tracking`, `fix: preserve formula caches`, or `docs: explain local database setup`. Releases follow the review gates in `ROADMAP.md`.

## Pull requests

Describe the user-visible change, implementation area, test command and result, and any remaining limitations. Do not attach a real workbook or populated SQLite database.
