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
AWK			?= awk
GREP		?= grep
KILL		?= kill
KILL_FLAGS	?= -f
PDFGEN		?= asciidoctor-pdf
PR			?= pr
PS			?= ps
PS_FLAGS	?= -W
PS_FIELDS	?= "9 47 100"
SHELL		:= /bin/bash
SORT		?= sort

DOC_DIR		:= Documentation
MKOB_DIR	:= MKOB
MRT_DIR		:= MRT

MKOB_MANUAL	:= $(DOC_DIR)/$(MKOB_DIR)/User-Manual-MKOB4.pdf
MRT_MANUAL	:= $(DOC_DIR)/$(MRT_DIR)/User-Manual-MRT.pdf

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

.PHONY: all
all: docs

# help - Print a list of all targets in this makefile
.PHONY: help
help:
	@$(MAKE_COMMAND) --print-data-base | \
	$(GREP) -v -e '^makefile' | \
	$(AWK) '/^[^.%][-A-Za-z0-9_]*:/ { print substr($$1, 1, length($$1)-1) }' | \
	$(SORT) | \
	$(PR) --omit-pagination --width=80 --columns=4

.PHONY: docs
docs: $(MKOB_MANUAL)

%.pdf: %.adoc
	$(PDFGEN) $<
