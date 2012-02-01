try:
    from setuptools import setup, find_packages
except ImportError:
    from ez_setup import use_setuptools
    use_setuptools()
    from setuptools import setup, find_packages

from quantum import version

import sys

Name = 'quantum-ryu-plugin'
ProjecUrl = ""
Version = version.version_string()
License = 'Apache License 2.0'
Author = 'Ryu Network Operating System Team'
AuthorEmail = 'discuss@openvswitch.org'
Maintainer = ''
Summary = 'Ryu plugin for Quantum'
ShortDescription = Summary
Description = Summary

requires = [
    'quantum-common',
    'quantum-server',
    'quantum-plugin-ovscommon',
]

EagerResources = [
    'quantum',
]

ProjectScripts = [
]

PackageData = {
}

# If we're installing server-wide, use an aboslute path for config
# if not, use a relative path
config_path = '/etc/quantum/plugins/ryu'
relative_locations = ['--user', '--virtualenv', '--venv']
if [x for x in relative_locations if x in sys.argv]:
    config_path = 'etc/quantum/plugins/ryu'

DataFiles = [
    (config_path,
    ['etc/quantum/plugins/ryu/ryu.ini'])
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
    packages=["quantum.plugins.ryu"],
    package_data=PackageData,
    data_files=DataFiles,
    eager_resources=EagerResources,
)
