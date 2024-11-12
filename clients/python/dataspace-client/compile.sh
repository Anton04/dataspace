#!/bin/bash

rm dist/dataspace_client-0.1.*.tar.gz
python3 setup.py sdist
twine upload dist/*
