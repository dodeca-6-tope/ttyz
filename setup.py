from pathlib import Path

from setuptools import Extension, setup

# module.c is a unity build that #includes every other .c/.h under csrc.
# List those as `depends` so `setup.py build_ext` triggers a rebuild
# when any of them change (setuptools only tracks `sources` by default).
CSRC = Path("src/ttyz/csrc")
DEPENDS = sorted(str(p) for p in CSRC.glob("*.[ch]"))

setup(
    ext_modules=[
        Extension(
            "ttyz.ext",
            sources=["src/ttyz/csrc/module.c"],
            depends=DEPENDS,
            extra_compile_args=["-O2"],
        ),
    ],
)
