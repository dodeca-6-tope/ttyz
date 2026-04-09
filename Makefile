ext:
	uv pip install -e .

check:
	uv run ruff format .
	uv run ruff check . --fix
	uv run pyright
	uv run pytest tests/ -q
