# First-time editable install of the package + extension.
ext:
	uv pip install -e .

# Fast incremental rebuild of the C extension in place.  Use during
# development after editing anything under src/ttyz/csrc/.  ~10x faster
# than `make ext` (which re-runs pip's full reinstall dance).
build:
	uv run --with setuptools python setup.py build_ext --inplace

example:
	cc -shared -fPIC -O2 -undefined dynamic_lookup \
		$$(uv run python3-config --includes) \
		examples/_torus.c -o examples/_torus$$(uv run python3-config --extension-suffix)
	PYTHONPATH=examples uv run python examples/stress.py

check: build
	uv run ruff format .
	uv run ruff check . --fix
	uv run pyright
	uv run pytest tests/ -q

.PHONY: ext build example check
