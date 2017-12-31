#ifndef SDK_CONFIG_H
#define SDK_CONFIG_H

#include <stdint.h>
#include <stdbool.h>

// see https://infocenter.nordicsemi.com/index.jsp?topic=%2Fcom.nordic.infocenter.sdk5.v12.0.0%2Fgroup__fds__config.html

#define FDS_ENABLED (1)

#define NRF52

#if   defined(NRF51)
    #define FDS_PHY_PAGE_SIZE   (256)
#elif defined(NRF52)
    #define FDS_PHY_PAGE_SIZE   (1024)
#endif

#include "fds_config.h"

#define NRF_SECTION_VARS_REGISTER_VAR(fs_data, cfg_var) cfg_var
#define NRF_SECTION_ITEM_REGISTER(fs_data, cfg_var) cfg_var

// from compiler_abstraction.h
#define __ALIGN(n)          __attribute__((aligned(n)))
#define ANON_UNIONS_ENABLE
#define ANON_UNIONS_DISABLE

#define NRF_MODULE_ENABLED(module) \
    ((defined(module ## _ENABLED) && (module ## _ENABLED)) ? 1 : 0)

// stuff to make it compile
#define NRF_SUCCESS (0)
//#ifdef SDK12
typedef int ret_code_t;
//#endif

// from app_util.h
static bool is_word_aligned(void const* p)
{
	return (((uintptr_t)p & 0x03) == 0);
}

#endif // guard
