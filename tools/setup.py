from setuptools import setup, find_packages

setup(
    name="fivem-locker",
    version="0.1.0",
    description="FiveM Lua resource locker/obfuscator with bundling and encryption",
    packages=find_packages(),
    install_requires=[
        "cryptography>=42.0.0; platform_python_implementation != 'PyPy'",
    ],
    entry_points={
        "console_scripts": [
            "fivem-locker=fivem_locker.cli:main",
        ]
    },
    python_requires=">=3.10",
)
