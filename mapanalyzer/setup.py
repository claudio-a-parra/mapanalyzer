from setuptools import setup, find_packages

setup(
    name="mapanalyzer",
    version="2.0",
    packages=find_packages(),
    python_requires=">=3.6",
    entry_points={
        "console_scripts": [
            #cli 'mapanalyzer' -> mapanalyzer/main.py:main()
            "mapanalyzer=mapanalyzer.main:main",
        ],
    },
    install_requires=[
        # build dependencies
        "setuptools",
        "wheel",
        # program dependencies
        "matplotlib",
        "jsonschema",
        "colorama"
    ],
)
