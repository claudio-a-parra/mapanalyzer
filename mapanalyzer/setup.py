from setuptools import setup, find_packages

setup(
    name="mapanalyzer",
    version="1.0",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "mapanalyzer=mapanalyzer.main:main_wrapper",  # Maps `mapanalyzer` command to `main()` function in `main.py`
        ],
    },
    install_requires=[
        "matplotlib"
    ],
)
