from setuptools import setup, find_packages
setup(
name='dataspace-client',
version='0.1.0',
author='Anton Gustafsson',
author_email='anton.gustafsson@ri.se',
description='This is a tool for connecting to a dataspace created with publish subscribe paradigm. ',
packages=find_packages(),
classifiers=[
'Programming Language :: Python :: 3',
'License :: OSI Approved :: MIT License',
'Operating System :: OS Independent',
],
python_requires='>=3.6',
)
