# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
import builtins

builtins.__sphinx_build__ = True

sys.path.insert(0, os.path.abspath("../.."))
from chapps._version import __version__ as chapps_version

DEV_HOSTNAMES = ["velocipede", "nekobus"]


def is_dev(hosts=DEV_HOSTNAMES):
    return os.uname()[1] in hosts


# -- Project information -----------------------------------------------------

project = "CHAPPS"
copyright = "2022, Caleb Cullen and EasyDNS Technologies Inc."
author = "Caleb Cullen"

# The full version, including alpha/beta/rc tags
release = chapps_version


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx_autodoc_typehints",
    "sphinx.ext.intersphinx",
    "sphinx.ext.todo",
    "sphinx.ext.viewcode",
    "myst_parser",
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []

# Intersphinx mapping
intersphinx_mapping = {"python": ("https://docs.python.org/3", None)}

# session setup
default_role = "py:obj"
rst_prolog = """
.. _fastapi: https://fastapi.tiangolo.com/
.. _sqlalchemy: https://sqlalchemy.org/
.. _pydantic: https://pydantic-docs.helpmanual.io/
.. _readme: https://github.com/easydns/chapps
.. _installation: https://github.com/easydns/chapps/blob/main/INSTALLATION.md
.. _changelog: https://github.com/easydns/chapps/blob/main/CHANGELOG.md
"""

# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "sphinx_rtd_theme"
html_theme_path = ["_themes"]


# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = []  # "_static"]

# Autodoc options
autodoc_typehints = "description"
autodoc_class_signature = "separated"
autodoc_member_order = "bysource"

# TODO options: only include if building on a development workstation
# (if you are also developing, add your workstation's name in your fork/branch)
todo_include_todos = is_dev()

# Typehints options
# typehints_defaults = "comma"

# MyST options
myst_heading_anchors = 4
