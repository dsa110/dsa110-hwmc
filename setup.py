"""Setuptools information file"""

from setuptools import setup
from version import get_git_version

setup(
    name='dsa110hwmc',
    version=get_git_version(),
    packages=['hwmc'],
    url='https://github.com/dsa110',
    license='California Institute of Technology',
    author='James W Lamb',
    author_email='lamb@caltech.edu',
    description='DSA-110 hardware monitor and control package'
)
