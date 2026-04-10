from setuptools import Extension, setup

setup(
    ext_modules=[
        Extension(
            "terminal.cbuf",
            sources=["src/terminal/cbuf.c"],
            extra_compile_args=["-O2"],
        ),
    ],
)
