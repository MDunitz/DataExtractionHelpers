#!/bin/sh
.PHONY: env test fmt

## Create a fresh venv and install labdata (editable) with the auth extra.
env:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -e ".[auth]"

test:
	.venv/bin/python -m pytest tests/ -q

fmt:
	.venv/bin/python -m black labdata tests
