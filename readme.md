# fds.py
A Python interface to the Nordic FDS filesystem.

![FDS Logo](/logo.png)

## What is the FDS filesystem?

[FDS](https://infocenter.nordicsemi.com/index.jsp?topic=%2Fcom.nordic.infocenter.sdk5.v13.1.0%2Flib_fds.html&cp=4_0_8_3_30)
is a weird flash-based filesystem developed by Nordic Semiconductor
for use in storing, amongst other things, Bluetooth credentials.

## What is this?

This is a Python implementation to FDS. This allows manipulation of FDS
images offline, on a PC, for debugging purposes, or to prepopulate a
flash image with provisioning and calibration information before
blasting in the image over JTAG or radio.

In the `c/` subdirectory is a C version of the library, with a similar
interface.  The C version uses `fds.c` directly from the SDK.

## Requirements

1. A flash image, or the `VIRTUAL_PAGE_SIZE` parameter from
   `fds_config.h` or `sdk_config.h`.

1. Python 3

# Usage

1. See `_tests()` in fds.py to see example usage.

1. The general approach is to build up records in the `Fds()` object,
   then get the filesystem image (as bytes) from the `.contents`
   property.

2. To access the fields from a filesystem image, pass it (as bytes) to
   the Fds() object.

# Limitations

1. You can build up an arbitrary number of records, and you won't know
   that you are out of space until you try to access the `.contents`
   property.
