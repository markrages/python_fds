# -*- mode: makefile -*-

#SDK ?= /opt/n5sdk-12.1.0
#SDK ?= /opt/n5sdk-12.2.0
#SDK ?= /opt/n5sdk-12.3.0
SDK ?= /opt/n5sdk-13.1.0

FDS_SRC ?= $(SDK)/components/libraries/fds
FSTORAGE_SRC ?= $(SDK)/components/libraries/fstorage
CRC_SRC ?= $(SDK)/components/libraries/crc16

SOURCE_FILES = $(FDS_SRC)/fds.c \
	$(CRC_SRC)/crc16.c \
	python_ops.c \
	sdk_config.h

DUMMY = ./.dummy

INCLUDES = -I . \
	-I $(DUMMY) \
	-I $(FDS_SRC)/ \
	-I $(CRC_SRC)/ \
	-I $(FSTORAGE_SRC)/

DEFAULT = fds_x86.so fds_x86_64.so
default: $(DEFAULT)

TAGS: $(SOURCE_FILES)
	etags `find $(SDK)/ | grep \\\.[ch]$$` $(SOURCE_FILES)

fds_x86_64.so: $(SOURCE_FILES) $(DUMMY)
	$(CC) -g3 -std=gnu99 -m64 -fPIC -shared $(INCLUDES) -o $@ $(SOURCE_FILES) -lm

fds_x86.so: $(SOURCE_FILES) $(DUMMY)
	$(CC) -g3 -std=gnu99 -m32 -shared $(INCLUDES) -o $@ $(SOURCE_FILES) -lm

$(DUMMY): Makefile
	mkdir -p $(DUMMY)
	ln -sf ../sdk_config.h $(DUMMY)/sdk_common.h
	touch $(DUMMY)/app_util_platform.h
	touch $(DUMMY)/app_util.h
	touch $(DUMMY)/nrf_error.h
	touch $(DUMMY)/nrf_soc.h
	touch $(DUMMY)/section_vars.h
	touch $(DUMMY)/nrf_section.h
	touch $(DUMMY)/sdk_errors.h
	touch $(DUMMY)/nrf.h
	touch $(DUMMY)/fstorage_config.h

clean:
	rm -rf $(DEFAULT) *~ *.pyc
	rm -rf $(DUMMY) TAGS
