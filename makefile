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
#  For the binaries, file copying is done to arrange source to produce
#  smaller executables than would be the case if they were just generated
#  from the runnable Python source. The reason for this is that the runnable
#  Python source has the 'pykob' package/modules as a subdirectory to make it
#  convenient for 'includes' within the applications. However, when
#  generating the binaries, if done from the original source, the pykob
#  package/modules is pulled in and included with each of the executables.
#  What is actually wanted is for the pykob package to be generated as a
#  separate binary that is then used by each of the applications. To
#  accomplish this, the original Python source is copied into 'build/src'
#  directories such that each exists in its own separate subdirectory.
#
#  This copy is make, if needed when make is run. The build/src directory
#  (in fact, all of the bin and build directories) are excluded from Git.
#  But they will be kept up to date from changes in the original Python Source.
#

# Cygwin path conversions for use when programs need a full path.
ifdef COMSPEC
  cygpath-mixed			= $(shell cygpath -m "$1")
  cygpath-unix			= $(shell cygpath -u "$1")
  drive-letter-to-slash	= /$(subst :,,$1)
  PYTHON				?= .venv/Scripts/python.exe
  EXEC_EXT				:= .exe
else
  cygpath-mixed			= $1
  cygpath-unix			= $1
  drive-letter-to-slash	= $1
  PYTHON				?= .venv/bin/python3
  EXEC_EXT				:= .bin
endif

AWK				?= awk
CP				?= cp
CP_RECURSE		?= $(CP) -r
CP_TOFILE		?= $(CP) -T
GREP			?= grep
KILL			?= kill
KILL_FLAGS		?= -f
MKDIR			?= mkdir
PDFGEN			?= asciidoctor-pdf
PR				?= pr
PS				?= ps
PS_FLAGS		?= -W
PS_FIELDS		?= "9 47 100"
PY2BIN_FAC		?= $(PYTHON) c:/Users/aesil/code/Nuitka-factory/Nuitka/bin/nuitka
PY2BIN_REL		?= $(PYTHON) -m nuitka
PY2BIN			?= $(PY2BIN_REL)
SHELL			:= /bin/bash
SORT			?= sort

# ### Documentation Section                                          ###

DOC_DIR			?= Documentation

MANUAL_SETTINGS	:= $(DOC_DIR)/man_settings.adoc
PyKOB_THEME		:= $(DOC_DIR)/PyKOB-theme.yml
MKOB_MANUAL		:= $(DOC_DIR)/MKOB/User-Manual-MKOB4.pdf
MRT_MANUAL		:= $(DOC_DIR)/MRT/User-Manual-MRT.pdf

# ### Binary Executable Section                                      ###

NUITKA_FLAGS	?= --warn-implicit-exceptions --warn-unusual-code --msvc=latest

BIN_DIR					?= bin
#
BUILD_SRC_DIR			?= build/src
BUILD_SRC_CONFIG_DIR	?= build/src/config
BUILD_SRC_PYKOB_DIR		?= build/src/pykob
BUILD_SRC_MKOB_DIR		?= build/src/mkob
BUILD_SRC_MRT_DIR		?= build/src/mrt
BUILD_SRC_UTILS_DIR		?= build/src/utils

APP_BUILD_SRC_DIRS	:= \
    $(BUILD_SRC_DIR) \
    $(BUILD_SRC_CONFIG_DIR) \
	$(BUILD_SRC_MKOB_DIR) \
	$(BUILD_SRC_MRT_DIR) \
	$(BUILD_SRC_UTILS_DIR)

REQUIRED_BIN_DIRS	:= $(BIN_DIR) $(APP_BUILD_SRC_DIRS)

PYKOB_DIR			:= pykob
PYKOB_DATA_DIR		:= $(PYKOB_DIR)/data
PYKOB_RESOURCES_DIR	:= $(PYKOB_DIR)/resources

SRC_PY_DIR			?= src.py
SRC_PY_RES_DIR		:= $(SRC_PY_DIR)/resources

SRC_PKAPPARGS		:= $(SRC_PY_DIR)/pkappargs.py

SRC_PYKOB_DIR		?= $(SRC_PY_DIR)/$(PYKOB_DIR)
SRC_PYKOB_DATA_DIR	:= $(SRC_PYKOB_DIR)/data
SRC_PYKOB_RES_DIR	:= $(SRC_PYKOB_DIR)/resources

SRC_PYKOB			:= $(SRC_PYKOB_DIR)/*.py
SRC_PYKOB_DATA		:= $(SRC_PYKOB_DATA_DIR)/*
SRC_PYKOB_RESOURCES	:= $(SRC_PYKOB_RES_DIR)/*

ORIGINAL_SRC_CONFIG		:= $(SRC_PY_DIR)/Configure.py # Have this as its own app.
ORIGINAL_SRC_MKOB		:= $(SRC_PY_DIR)/MKOB.py $(SRC_PY_DIR)/mkob*.py
ORIGINAL_SRC_MRT		:= $(SRC_PY_DIR)/MRT.py
ORIGINAL_SRC_UTILS		:= $(SRC_PY_DIR)/[A-Z][a-z]*.py # This includes Configure.py, so it needs to be removed.


PY_BIN_MODULE_EXT		:= .pyd
PY_BIN_MODULE_INC_EXT	:= .pyi

APP_BIN_DEBUG_FLAGS	?= \
	--force-stdout-spec=exe.out.txt\
	--force-stderr-spec=exe.err.txt\
	--debug\
	--python-flag=-v\
#	--trace

PYKOB_BIN_DEBUG_FLAGS	?= \
	--debug\
	--python-flag=-v\
#	--trace

COMMON_BIN_FLAGS	?= --python-flag=no_annotations --python-flag=no_docstrings

APP_BIN_FLAGS	?= $(NUITKA_FLAGS) $(COMMON_BIN_FLAGS) --standalone\
	--output-dir=$(BIN_DIR)\
#	$(APP_BIN_DEBUG_FLAGS)

PKAPPARGS_PACKAGE_FLAGS	?= --module $(NUITKA_FLAGS) $(COMMON_BIN_FLAGS)\
	--output-dir=$(BIN_DIR)\
	$(SRC_PKAPPARGS)

PYKOB_PACKAGE_FLAGS	?=  --module $(NUITKA_FLAGS) $(COMMON_BIN_FLAGS)\
	--include-package=pykob\
	--include-module=socket\
	--include-module=ctypes\
	--output-dir=$(BIN_DIR)\
	$(SRC_PYKOB_DIR)
#	$(PYKOB_BIN_DEBUG_FLAGS)

### pkappargs binary package file
PKAPPARGS_PKG_BIN_FILE	?= $(BIN_DIR)/pkappargs.cp311-win_amd64.pyd

### pykob binary package file
PYKOB_PKG_BIN_FILE		?= $(BIN_DIR)/pykob.cp311-win_amd64.pyd

## Applications and Utilities Bin-Build flags
### Configure
ifdef COMSPEC
  CONFIGURE_EXEC		:= Configure.exe
else
  CONFIGURE_EXEC		:= Configure.bin
endif
CONFIGURE_BIN_FLAGS		?= $(APP_BIN_FLAGS)\
	--enable-console\
	--enable-plugin=tk-inter

### MKOB
MKOB_DIST				:= $(BIN_DIR)/MKOB.dist
ifdef COMSPEC
  MKOB_EXEC				:= $(MKOB_DIST)/MKOB.exe
  MKOB_ICON				:= --windows-icon-from-ico=$(SRC_PY_RES_DIR)/mkob-icon.ico
else
  MKOB_EXEC				:= $(MKOB_DIST)/MKOB.bin
  MKOB_ICON				:=
endif

MKOB_BIN_FLAGS			?= $(APP_BIN_FLAGS)\
	$(MKOB_ICON)\
	--enable-console\
	--enable-plugin=tk-inter

### MRT
MRT_DIST				:= $(BIN_DIR)/MRT.dist
ifdef COMSPEC
  MRT_EXEC				:= MRT.exe
  MRT_ICON				:= --windows-icon-from-ico=$(SRC_PY_RES_DIR)/mrt-icon.ico
else
  MMRT_EXEC				:= MRT.bin
  MRT_ICON				:=
endif
MRT_BIN_FLAGS			?= $(APP_BIN_FLAGS) $(MRT_ICON) --enable-console

### Utilities
UTILITIES_BIN_FLAGS		?= $(APP_BIN_FLAGS) --enable-console


#
vpath pykob/%.py	$(SRC_PYKOB_DIR)
vpath MKOB.py		$(BUILD_SRC_MKOB_DIR)
vpath mkob%.py		$(BUILD_SRC_MKOB_DIR)
vpath MRT.py		$(BUILD_SRC_MRT_DIR)
vpath %.py			$(BUILD_SRC_UTILS_DIR)
vpath %.pyd			$(BIN_DIR)

# Utilities Executable rules
%$(EXEC_EXT): %.py pykob.pyd
	$(CP) $(BIN_DIR)/pykob.pyi $(BUILD_SRC_UTILS_DIR)
	$(CP_TOFILE) $(PYKOB_PKG_BIN_FILE) $(BUILD_SRC_UTILS_DIR)/pykob.pyd
	$(PY2BIN) $(UTILITIES_BIN_FLAGS) $<
	$(CP) $(BUILD_SRC_MKOB_DIR)/pykob.py* $(BIN_DIR)/$@.dist

# Documentation rules
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

# help (the default target) - Print a list of all targets in this makefile
.PHONY: help
help:
	@$(MAKE_COMMAND) --print-data-base --question no-such-target | \
	$(GREP) -v -e '^no-such-target' -e '^makefile' | \
	$(AWK) '/^[^.%][-A-Za-z0-9_]*:/ { print substr($$1, 1, length($$1)-1) }' | \
	$(SORT) | \
	$(PR) --omit-pagination --width=132 --columns=4

# Currently 'all' is just the documentation. It will become everything (binaries, docs, installers)
# once the kinks are ironed out of the binaries.
#
.PHONY: all
all: docs

.PHONY: clean_all_bin
clean_all_bin: clean_bld_dirs clean_bld_src_dirs clean_dist_dirs clean_pkg_dir
	rm -f $(BIN_DIR)/*

.PHONY: clean_bld_dirs
clean_bld_dirs:
	rm -rf $(BIN_DIR)/Configure.build
	rm -rf $(BIN_DIR)/MKOB.build
	rm -rf $(BIN_DIR)/MRT.build
	rm -rf $(BIN_DIR)/pkappargs.build
	rm -rf $(BIN_DIR)/pykob.build
	rm -rf $(BIN_DIR)/Sample.build

.PHONY: clean_bld_src_dirs
clean_bld_src_dirs:
	rm -rf $(BUILD_SRC_DIR)

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
bins: pykob Configure MKOB MRT

.PHONY: package_bins
package_bins:
	$(MKDIR) $(BIN_DIR)/pkg
	$(CP) -r $(BIN_DIR)/Configure.dist/* $(BIN_DIR)/pkg
	$(CP) -r $(BIN_DIR)/MKOB.dist/* $(BIN_DIR)/pkg
	$(CP) -r $(BIN_DIR)/MRT.dist/* $(BIN_DIR)/pkg
	$(CP) -r $(BIN_DIR)/Sample.dist/* $(BIN_DIR)/pkg

.PHONY: setup_build_src
setup_build_src:
	$(shell for d in $(REQUIRED_BIN_DIRS);	\
			do										\
				[[ -d $$d ]] || mkdir -p $$d;		\
			done)
	$(CP) -rup $(ORIGINAL_SRC_CONFIG) $(BUILD_SRC_CONFIG_DIR)
	$(CP) -rup $(ORIGINAL_SRC_MKOB) $(BUILD_SRC_MKOB_DIR)
	$(CP) -rup $(ORIGINAL_SRC_MRT) $(BUILD_SRC_MRT_DIR)
	$(CP) -rup $(ORIGINAL_SRC_UTILS) $(BUILD_SRC_UTILS_DIR)
	# Configure is treated as a specific target, so remove it from the utilites.
	$(RM) $(BUILD_SRC_UTILS_DIR)/Configure.py


# The following PHONY targets will be replaced by true targets given time
# to build out the proper names and dependencies.
#
# For now, they are PHONY, such that they will always build.

.PHONY: pykob
pykob: pykob.pyd ;

.PHONY: Configure
Configure: Configure.py
	$(PY2BIN) $(CONFIGURE_BIN_FLAGS) $<
	$(CP) $(SRC_PY_DIR)/pykob.py* $(BIN_DIR)/$@.dist

.PHONY: MKOB
MKOB: $(MKOB_EXEC) ;

.PHONY: MRT
MRT: $(MRT_EXEC) ;

# #############################################################################
#
# True targets
#
# #############################################################################

$(MKOB_EXEC): MKOB_SOURCES := $(shell for d in $(REQUIRED_BIN_DIRS); \
							do									\
								[[ -d $$d ]] || mkdir -p $$d;	\
							done;								\
						$(CP) -rup $(ORIGINAL_SRC_MKOB) $(BUILD_SRC_MKOB_DIR))

$(MKOB_EXEC): $(BUILD_SRC_MKOB_DIR)/MKOB.py $(BUILD_SRC_MKOB_DIR)/*.py  pkappargs.pyd pykob.pyd
	$(CP) -up $(BIN_DIR)/pykob.py* $(BUILD_SRC_MKOB_DIR)
	$(CP) -up $(BIN_DIR)/pkappargs.py* $(BUILD_SRC_MKOB_DIR)
	$(PY2BIN) $(MKOB_BIN_FLAGS) $<
	$(CP) -up $(BUILD_SRC_MKOB_DIR)/pykob.py* $(MKOB_DIST)
	$(MKDIR) -p $(MKOB_DIST)/$(PYKOB_DATA_DIR)
	$(CP) -rup $(SRC_PYKOB_DATA) $(MKOB_DIST)/$(PYKOB_DATA_DIR)
	$(MKDIR) -p $(MKOB_DIST)/$(PYKOB_RESOURCES_DIR)
	$(CP) -rup $(SRC_PYKOB_RESOURCES) $(MKOB_DIST)/$(PYKOB_RESOURCES_DIR)


$(MRT_EXEC): MRT_SOURCES := $(shell for d in $(REQUIRED_BIN_DIRS); \
							do									\
								[[ -d $$d ]] || mkdir -p $$d;	\
							done;								\
						$(CP) -rup $(ORIGINAL_SRC_MRT) $(BUILD_SRC_MRT_DIR))

$(MRT_EXEC): MRT.py pkappargs.pyd pykob.pyd
	$(CP) -up $(BIN_DIR)/pykob.py* $(BUILD_SRC_MRT_DIR)
	$(CP) -up $(BIN_DIR)/pkappargs.py* $(BUILD_SRC_MRT_DIR)
	$(PY2BIN) $(MRT_BIN_FLAGS) $<
	$(CP) -up $(BUILD_SRC_MRT_DIR)/pykob.py* $(MRT_DIST)
	$(MKDIR) -p $(MRT_DIST)/$(PYKOB_DATA_DIR)
	$(CP) -rup $(SRC_PYKOB_DATA) $(MRT_DIST)/$(PYKOB_DATA_DIR)
	$(MKDIR) -p $(MRT_DIST)/$(PYKOB_RESOURCES_DIR)
	$(CP) -rup $(SRC_PYKOB_RESOURCES) $(MRT_DIST)/$(PYKOB_RESOURCES_DIR)


pkappargs.pyd: $(PKAPPARGS_PKG_BIN_FILE)
	$(CP) $< $(dir $<)$@

$(PKAPPARGS_PKG_BIN_FILE): $(SRC_PY_PKAPPARGS)
	$(PY2BIN) $(PKAPPARGS_PACKAGE_FLAGS)

pykob.pyd: $(PYKOB_PKG_BIN_FILE)
	$(CP) $< $(dir $<)$@

$(PYKOB_PKG_BIN_FILE): $(SRC_PY_PYKOB) $(SRC_PYKOB_DATA) $(SRC_PYKOB_RESOURCES)
	$(PY2BIN) $(PYKOB_PACKAGE_FLAGS)
