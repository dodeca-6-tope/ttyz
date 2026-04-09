ext:
	uv pip install -e .

example:
	cc -shared -fPIC -O2 -undefined dynamic_lookup \
		$$(uv run python3-config --includes) \
		examples/_torus.c -o examples/_torus$$(uv run python3-config --extension-suffix)
	PYTHONPATH=examples uv run python examples/stress.py

check:
	uv run ruff format .
	uv run ruff check . --fix
	uv run pyright
	uv run pytest tests/ -q
