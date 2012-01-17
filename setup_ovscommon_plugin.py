try:
    from setuptools import setup, find_packages
except ImportError:
    from ez_setup import use_setuptools
    use_setuptools()
    from setuptools import setup, find_packages

from quantum import version
import sys

Name = 'quantum-plugin-ovscommon'
ProjecUrl = ""
Version = version.version_string()
License = 'Apache License 2.0'
Author = 'Open vSwitch Team'
AuthorEmail = 'discuss@openvswitch.org'
Maintainer = ''
Summary = 'OVS common library for Quantum plugin'
ShortDescription = Summary
Description = Summary

requires = [
    'quantum-common',
    'quantum-server',
]

EagerResources = [
    'quantum',
]

ProjectScripts = [
]

PackageData = {
}

DataFiles = [
]

setup(
    name=Name,
    version=Version,
    author=Author,
    author_email=AuthorEmail,
    description=ShortDescription,
    long_description=Description,
    license=License,
    scripts=ProjectScripts,
    install_requires=requires,
    include_package_data=True,
    packages=["quantum.plugins.ovscommon"],
    package_data=PackageData,
    eager_resources=EagerResources,
)
