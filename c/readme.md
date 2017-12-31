# fds.py
A Python interface to the Nordic FDS filesystem.

![FDS Logo](/logo.png)

## What is the FDS filesystem?

[FDS](https://infocenter.nordicsemi.com/index.jsp?topic=%2Fcom.nordic.infocenter.sdk5.v13.1.0%2Flib_fds.html&cp=4_0_8_3_30)
is a weird flash-based filesystem developed by Nordic Semiconductor
for use in storing, amongst other things, Bluetooth credentials.

## What is this?

This is a Python interface to FDS. This allows manipulation of FDS
images offline, on a PC, for debugging purposes, or to prepopulate a
flash image with provisioning and calibration information before
blasting in the image over JTAG or radio.

## How does it work?

The `fds.c` file is compiled unchanged from the Nordic SDK. There is a
C shim that wraps the event-driven callback insanity with a simple
procedural interface.  There are linked together into a DLL, then a
Python module calls this wrapper using ctypes.

It is depressingly complicated to compile Nordic libraries
out-of-tree.  The Makefile handles this.

## Requirements

1. A Nordic SDK.  SDK versions 12.1.0, 12.2.0, 12.3.0, 13.1.0 have
   been tested. Other versions almost certainly won't work, due to the
   gratuitious naming and API churn that happens with every point
   releases of the SDK.

1. The fds_config.h with parameters corresponding to the filesystem in
   questions.  The parameters are compiled-in.

1. C compiler, GNU Make, etc.

1. Python 3

1. A Linux operating sysem. OS X is probably working or near-working.
   For Windows use, you are on your own.

# Usage

1. Edit fds_config.h with the appropriate parameters for your
   application. The default parameters are OK for most SDK projects.
   (The SDK comes with 101 projects, 79 have FDS enabled, and all but
   the Eddystone one use these parameters.)

   If you have a Nordic project you are working with, it is good
   software engineering to separate out FDS-specific settings from the
   giant `sdk_config.h`, replacing them with `#include
   "fds_config.h"`. Now you have a single-point-of-truth FDS config
   file that you can use for both your project and this Python
   interface.

1. Edit the Makefile and point `SDK` at the path to a supported Nordic
   n5 SDK.

1. `make` will compile the DLLs. By default it compiles both 32-bit
   and 64-bit libraries. You are probably interested in just one of
   these, so edit `DEFAULTS` in the Makefile. The alternative is to
   install compatibility libraries for the other architecture.

1. Run `fds.py` to compile the DLL and run some tests.

1. See `_tests()` in fds.py to see example usage.

# Limitations

1. `fds.c` uses global compile-time configuration. It is not possible
   to use different settings in one Python process.

1. `fds.c` reads by dereferencing pointers, so it is not possible to
   have an API with `erase()`/`read()`/`write()` methods.  Instead,
   you must initialize with the image of the filesystem, then write it
   back out afterwards. (This same limitation prevents FDS from being
   used with external SPI EEPROM or Flash.)

1. The fiddly edit-the-header-file configuration means that it is not
   obvious or simple to incorporate this library into a package
   manager.

All of these could be fixed by rewriting the filesystem in pure
Python...
