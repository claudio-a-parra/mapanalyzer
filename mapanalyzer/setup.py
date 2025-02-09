from setuptools import setup, find_packages

setup(
    name="mapanalyzer",
    version="1.0",
    packages=find_packages(),
    python_requires=">=3.6",
    entry_points={
        "console_scripts": [
            #cli 'mapanalyzer' -> mapanalyzer/main.py:main()
            "mapanalyzer=mapanalyzer.main:main",
        ],
    },
    install_requires=[
        "matplotlib",
        "jsonschema",
        "colorama"
    ],
)
