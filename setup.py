#!/usr/bin/env python
"""DNS python caching."""

from setuptools import find_packages, setup

__version__ = "0.3.0"

classifiers = """\
Environment :: Console
Environment :: Plugins
Environment :: Web Environment
Intended Audience :: Developers
Intended Audience :: Information Technology
Intended Audience :: Science/Research
Intended Audience :: System Administrators
License :: OSI Approved :: MIT License
Operating System :: OS Independent
Programming Language :: Python :: 2.7
Programming Language :: Python :: 3.5
Programming Language :: Python :: 3.6
Programming Language :: Python :: 3.7
Programming Language :: Python :: 3.8
Programming Language :: Python :: Implementation :: CPython
Development Status :: 3 - Alpha
"""

setup(
    name="dns-cache",
    version=__version__,
    description="DNS lookup cache for Python using dnspython",
    license="MIT",
    author_email="jayvdb@gmail.com",
    url='https://github.com/jayvdb/dns-cache',
    packages=find_packages(exclude=["tests", "tests.*"]),
    python_requires=">=2.7,!=3.0.*,!=3.1.*,!=3.2.*,!=3.3.*",
    install_requires=[
        "dnspython",
        "ProxyTypes",
        "reconfigure",
    ],
    classifiers=classifiers.splitlines(),
)
