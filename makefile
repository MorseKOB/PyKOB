#
# MIT License
#
# Copyright (c) 2020-24 PyKOB - MorseKOB in Python
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# ############################################################################
#
# Makefile to create:
#  * A binary package of PyKOB (MKOB, MRT, Configure, ...) using Nuitka.
#  * The manuals (pdf from the adoc)
#
AWK				?= awk
CP				?= cp
CP_RECURSE		?= $(CP) -r
GREP			?= grep
KILL			?= kill
KILL_FLAGS		?= -f
PDFGEN			?= asciidoctor-pdf
PR				?= pr
PS				?= ps
PS_FLAGS		?= -W
PS_FIELDS		?= "9 47 100"
PYTHON			?= /c/Program\ Files/Python311/python.exe
PY2BIN			?= $(PYTHON) -m nuitka
SHELL			:= /bin/bash
SORT			?= sort
#
PY_BIN_EXT		:= .pyd

DOC_DIR			?= Documentation

MANUAL_SETTINGS	:= $(DOC_DIR)/man_settings.adoc
PyKOB_THEME		:= $(DOC_DIR)/PyKOB-theme.yml
MKOB_MANUAL		:= $(DOC_DIR)/MKOB/User-Manual-MKOB4.pdf
MRT_MANUAL		:= $(DOC_DIR)/MRT/User-Manual-MRT.pdf

NUITKA_FLAGS	?= --warn-implicit-exceptions --warn-unusual-code

BIN_DIR		?= bin
SRCPY_DIR	?= src.py

PYKOB_BIN_DEBUG_FLAGS	?= --enable-console\
	--force-stdout-spec=exe.out.txt\
	--force-stderr-spec=exe.err.txt\
	--trace\
	--python-flag=-v --debugger

PYKOB_BIN_FLAGS	?= --standalone\
	--include-data-dir=$(SRCPY_DIR)/pykob/data=pykob/data\
	--include-data-dir=$(SRCPY_DIR)/pykob/resources=pykob/resources\
	--output-dir=$(BIN_DIR)\
	$(PYKOB_BIN_DEBUG_FLAGS)

PYKOB_PACKAGE_FLAGS	?= --module src.py/pykob --include-package=pykob\
	--output-dir=$(BIN_DIR)\
	$(PYKOB_BIN_DEBUG_FLAGS)

NO_INC_PYKOB_FLAGS	?= --nofollow-import-to=pykob

# Utility and Application Bin-Build flags
## Configure
CONFIGURE_BIN_FLAGS		?= $(PYKOB_BIN_FLAGS) --enable-console --enable-plugin=tk-inter
## MKOB
MKOB_BIN_FLAGS			?= $(PYKOB_BIN_FLAGS)\
	--enable-console\
	--enable-plugin=tk-inter\
	--include-data-dir=$(SRCPY_DIR)/resources=resources
## MRT
MRT_BIN_FLAGS			?= $(PYKOB_BIN_FLAGS) --enable-console

# pykob binary package file
PYKOB_PKG_BIN		?= $(BIN_DIR)/pykob.cp311-win_amd64.pyd

vpath %.py		src.py
vpath %.pyw		src.py

# macros
#
# $(call kill-program,awk-pattern)
define kill-program
	@ $(PS) $(PS_FLAGS) |										\
	$(AWK) 'BEGIN	{ FIELDWIDTHS = $(PS_FIELDS) }				\
		/$1/	{												\
						print "Killing " $$3;					\
						system( "$(KILL) $(KILL_FLAGS) " $$1 )	\
					}'
endef

# help - Print a list of all targets in this makefile
.PHONY: help
help:
	@$(MAKE_COMMAND) --print-data-base --question no-such-target | \
	$(GREP) -v -e '^no-such-target' -e '^makefile' | \
	$(AWK) '/^[^.%][-A-Za-z0-9_]*:/ { print substr($$1, 1, length($$1)-1) }' | \
	$(SORT) | \
	$(PR) --omit-pagination --width=80 --columns=4

.PHONY: all
all: docs

.PHONY: clean_all_bin
clean_all_bin: clean_bld_dirs clean_dist_dirs

.PHONY: clean_bld_dirs
clean_bld_dirs:
	rm -rf $(BIN_DIR)/Configure.build
	rm -rf $(BIN_DIR)/MKOB.build
	rm -rf $(BIN_DIR)/MRT.build

.PHONY: clean_dist_dirs
clean_dist_dirs:
	rm -rf $(BIN_DIR)/Configure.dist
	rm -rf $(BIN_DIR)/MKOB.dist
	rm -rf $(BIN_DIR)/MRT.dist

.PHONY: docs
docs: $(MKOB_MANUAL)

$(MKOB_MANUAL): $(MANUAL_SETTINGS) $(PyKOB_THEME)

%.pdf: %.adoc
	$(PDFGEN) $<

.PHONY: bins
bins: pykob Configure MKOB MRT

.PHONY: pykob
pykob:
	$(PY2BIN) $(PYKOB_PACKAGE_FLAGS)

Configure: Configure.py
	$(PY2BIN) $(CONFIGURE_BIN_FLAGS) $<

MKOB: MKOB.pyw pykob
	$(PY2BIN) $(NO_INC_PYKOB_FLAGS) $(MKOB_BIN_FLAGS) $<
	$(CP) $(PYKOB_PKG_BIN) $(BIN_DIR)/$@.dist/pykob$(PY_BIN_EXT)

MRT: MRT.py pykob
	$(PY2BIN) $(NO_INC_PYKOB_FLAGS) $(MRT_BIN_FLAGS) $<
	$(CP) $(PYKOB_PKG_BIN) $(BIN_DIR)/$@.dist/pykob$(PY_BIN_EXT)
