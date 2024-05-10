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
PY2BIN_FAC		?= $(PYTHON) /Users/aesil/code/Nuitka-factory/Nuitka/bin/nuitka
PY2BIN_REL		?= $(PYTHON) -m nuitka
PY2BIN			?= $(PY2BIN_FAC)
SHELL			:= /bin/bash
SORT			?= sort
#
PY_BIN_EXT		:= .pyd
PY_BIN_INC_EXT	:= .pyi

DOC_DIR			?= Documentation

MANUAL_SETTINGS	:= $(DOC_DIR)/man_settings.adoc
PyKOB_THEME		:= $(DOC_DIR)/PyKOB-theme.yml
MKOB_MANUAL		:= $(DOC_DIR)/MKOB/User-Manual-MKOB4.pdf
MRT_MANUAL		:= $(DOC_DIR)/MRT/User-Manual-MRT.pdf

NUITKA_FLAGS	?= --warn-implicit-exceptions --warn-unusual-code

BIN_DIR			?= bin
SRC_PY_DIR		?= src.py
SRC_PYKOB_DIR	?= src.pykob

APP_BIN_DEBUG_FLAGS	?= \
	--force-stdout-spec=exe.out.txt\
	--force-stderr-spec=exe.err.txt\
	--debug\
	--python-flag=-v
#	--trace

PYKOB_BIN_DEBUG_FLAGS	?= \
	--debug\
	--python-flag=-v
#	--trace

APP_BIN_FLAGS	?= --standalone\
	--include-data-dir=$(SRC_PYKOB_DIR)/pykob/data=pykob/data\
	--include-data-dir=$(SRC_PYKOB_DIR)/pykob/resources=pykob/resources\
	--output-dir=$(BIN_DIR)\
#	$(APP_BIN_DEBUG_FLAGS)

PYKOB_PACKAGE_FLAGS	?= --module $(SRC_PYKOB_DIR)/pykob --include-package=pykob\
	--include-module=socket\
	--include-module=ctypes\
	--output-dir=$(BIN_DIR)\
#	$(PYKOB_BIN_DEBUG_FLAGS)

#NO_INC_PYKOB_FLAGS	?= --nofollow-import-to=pykob

# Utility and Application Bin-Build flags
## Configure
CONFIGURE_BIN_FLAGS		?= $(APP_BIN_FLAGS)\
	--enable-console\
	--enable-plugin=tk-inter

## MKOB
MKOB_BIN_FLAGS			?= $(APP_BIN_FLAGS)\
	--enable-console\
	--enable-plugin=tk-inter\
	--include-data-dir=$(SRC_PY_DIR)/resources=resources

## MRT
MRT_BIN_FLAGS			?= $(APP_BIN_FLAGS) --enable-console

## Sample
SAMPLE_BIN_FLAGS		?= $(APP_BIN_FLAGS) --enable-console

# pykob binary package file
PYKOB_PKG_BIN_FILE		?= $(BIN_DIR)/pykob.cp311-win_amd64.pyd

vpath pykob/%.py	src.pykob
vpath %.py		src.py
vpath %.pyd		src.py
vpath %.pyw		src.py

%.pdf: %.adoc
	$(PDFGEN) $<

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

# Currently 'all' is just the documentation. It will become everything (binaries, docs, installers)
# once the kinks are ironed out of the binaries.
#
.PHONY: all
all: docs

.PHONY: clean_all_bin
clean_all_bin: clean_bld_dirs clean_dist_dirs clean_pkg_dir
	rm $(BIN_DIR)/*

.PHONY: clean_bld_dirs
clean_bld_dirs:
	rm -rf $(BIN_DIR)/Configure.build
	rm -rf $(BIN_DIR)/MKOB.build
	rm -rf $(BIN_DIR)/MRT.build
	rm -rf $(BIN_DIR)/pykob.build
	rm -rf $(BIN_DIR)/Sample.build

.PHONY: clean_dist_dirs
clean_dist_dirs:
	rm -rf $(BIN_DIR)/Configure.dist
	rm -rf $(BIN_DIR)/MKOB.dist
	rm -rf $(BIN_DIR)/MRT.dist
	rm -rf $(BIN_DIR)/Sample.dist

.PHONY: clean_pkg_dir
clean_pkg_dir:
	rm -rf $(BIN_DIR)/pkg

.PHONY: docs
docs: $(MKOB_MANUAL)

$(MKOB_MANUAL): $(MANUAL_SETTINGS) $(PyKOB_THEME)

.PHONY: bins
bins: pykob Configure MKOB MRT Sample

.PHONY: package_bins
package_bins:
	mkdir $(BIN_DIR)/pkg
	cp -r $(BIN_DIR)/Configure.dist/* $(BIN_DIR)/pkg
	cp -r $(BIN_DIR)/MKOB.dist/* $(BIN_DIR)/pkg
	cp -r $(BIN_DIR)/MRT.dist/* $(BIN_DIR)/pkg
	cp -r $(BIN_DIR)/Sample.dist/* $(BIN_DIR)/pkg

# The following PHONY targets will be replaced by true targets given time
# to build out the proper names and dependencies.

.PHONY: pykob
pykob: pykob.pyd

.PHONY: Configure
Configure: Configure.py
	$(PY2BIN) $(CONFIGURE_BIN_FLAGS) $<
	$(CP) $(SRC_PY_DIR)/pykob.py* $(BIN_DIR)/$@.dist

.PHONY: MKOB
MKOB: MKOB.pyw #pykob
	$(PY2BIN) $(MKOB_BIN_FLAGS) $<
	$(CP) $(SRC_PY_DIR)/pykob.py* $(BIN_DIR)/$@.dist

.PHONY: MRT
MRT: MRT.py #pykob
	$(PY2BIN) $(MRT_BIN_FLAGS) $<
	$(CP) $(SRC_PY_DIR)/pykob.py* $(BIN_DIR)/$@.dist

.PHONY: Sample
Sample: Sample.py #pykob
	$(PY2BIN) $(SAMPLE_BIN_FLAGS) $<
	$(CP) $(SRC_PY_DIR)/pykob.py* $(BIN_DIR)/$@.dist

pykob.pyd: $(PYKOB_PKG_BIN_FILE)
	cp $(BIN_DIR)/pykob.pyi $(SRC_PY_DIR)
	cp $(PYKOB_PKG_BIN_FILE) $(SRC_PY_DIR)/pykob.pyd

$(PYKOB_PKG_BIN_FILE): # TODO: generate dependencies.
	$(PY2BIN) $(PYKOB_PACKAGE_FLAGS)
