define USAGE
USAGE:
> make [
	install: ...,
	run: ...
]
endef
export USAGE

OS ?= $(shell uname -s | tr A-Z a-z)


VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(PYTHON) -m pip

$(VENV):
	python3 -m venv $(VENV)


##########
## MISC ##
##########

all:
	$(info $(USAGE))

version:
	@$(PYTHON) setup.py --version

#############
## DEV ENV ##
#############
install: $(VENV)
	$(PYTHON) -m pip install -r requirements.txt
	$(PYTHON) -m pip install -e .


run: $(VENV) 
	@$(PYTHON) -m gunicorn -w 4 --timeout 300 app:app

