# First-time editable install of the package + extension.
ext:
	uv pip install -e .

# Fast incremental rebuild of the C extension in place.  Use during
# development after editing anything under src/ttyz/csrc/.  ~10x faster
# than `make ext` (which re-runs pip's full reinstall dance).
build:
	uv run --with setuptools python setup.py build_ext --inplace

# Render a node expression to stdout.  Usage:
#   make preview "text('hi')"
#   make preview "box(text('hi'))" W=20
#   echo "vstack(text('a'), text('b'))" | make preview
#
# The expression is taken from positional args after `preview`.  Omit
# it to read from stdin.  W= sets width, H= clamps height.
PREVIEW_EXPR := $(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))
preview:
	@uv run python -m ttyz.preview "$(if $(PREVIEW_EXPR),$(PREVIEW_EXPR),-)" \
		$(if $(W),--width $(W)) $(if $(H),--height $(H))

# Catch-all so make doesn't try to build the forwarded expression words
# as targets.  Only active when `preview` is the first goal.
ifeq (preview,$(firstword $(MAKECMDGOALS)))
%:
	@:
endif

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

.PHONY: ext build preview example check
