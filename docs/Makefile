# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line, and also
# from the environment for the first two.
SPHINXOPTS    ?=
SPHINXBUILD   ?= sphinx-build
AUTODOC       ?= sphinx-apidoc
AUTODOCOPTS   ?= -Mef -o "$(SOURCEDIR)" "$(CODEROOT)" "$(SKIPDIRS)"
WORKSTATIONOPTS = -b html -t workstation
TODOLIST      = build/doctrees/todolist.doctree
CODEROOT      = ../chapps
SKIPDIRS      = ../chapps/alembic/*
SOURCEDIR     = source
BUILDDIR      = build

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help Makefile

.PHONY: workstationhtml
workstationhtml:
	@rm $(TODOLIST) || echo "No todolist doctree to remove; continuing..."
	@$(AUTODOC) $(AUTODOCOPTS)
	@$(SPHINXBUILD) "$(SOURCEDIR)" "$(BUILDDIR)" $(WORKSTATIONOPTS)
	@echo "Workstation documentation built with to-do list"

# Catch-all target: route all unknown targets to Sphinx using the new
# "make mode" option.  $(O) is meant as a shortcut for $(SPHINXOPTS).
%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
