from setuptools import Extension, setup

setup(
    ext_modules=[
        Extension(
            "terminal._buffer",
            sources=["src/terminal/_buffer.c"],
            extra_compile_args=["-O2"],
        ),
    ],
)
