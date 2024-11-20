from setuptools import setup, find_packages

setup(
    name="pycfg",
    version="1.1.2",
    author="David Schneider",
    author_email="davidschneider821@gmail.com",
    description="A package for defining config file structure in python, "
                "converting types, and validating config values",
    url="https://github.com/blurpit/pycfg",
    packages=find_packages(),
    python_requires=">=3.7",
)
