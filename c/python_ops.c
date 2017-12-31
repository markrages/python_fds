#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <assert.h>

#include "sdk_config.h"
#include "fstorage.h"
#include "fds.h"

extern fs_config_t fs_config;

/* external function API are prefixed with api_:

   int api_fs_size() -- filesystem size, in bytes. See fds_config.h
   int api_fds_mount() -- mount an image
   int api_fds_dir() -- scan for records
   uint32_t api_gc() -- garbage collect
   uint32_t api_del_record() -- delete single record
   uint32_t api_del_file() -- delete all records of file
   uint32_t api_get_record() -- get file_id, key, contents
   uint32_t api_write_record() --
   uint32_t api_update_record() -- writes a record and deletes previous one
 */

/*
  FDS will call fs_store() or fs_erase() for writing or erasing pages.

  It expects us to call fs_callback() with the return value.  (FDS
  maintains a static variable to internally track which call the
  response is for.)

  But if fs_callback() is called within fs_store() or fs_erase(), the
  FDS will deadlock in an infinite loop.  You must be this tall to
  write multithreaded programs.

  The solution is to maintain a FIFO of return codes, then pump that
  back into fs_callback() after the FDS call completes.

  The actual return code from the FDS call comes back in
  on_fds_event(), which was registered at init time.

  So the sequence is make call, then pump return codes while waiting
  for return code event, then return that.  Thus we avoid infecting
  higher layers with event spaghetti.

 */

#define RESULT_QUEUE_SIZE (256)
static uint32_t result_queue[RESULT_QUEUE_SIZE];
static int result_queue_head = 0;
static int result_queue_tail = 0;

static void add_result(uint32_t result)
{
	result_queue[result_queue_tail++] = result;
	result_queue_tail %= RESULT_QUEUE_SIZE;
	assert(result_queue_tail != result_queue_head);
}

// this callback is always the same, so just keep a single pointer
// around, rather than a copy for each fs_* call.
static void (*fs_callback)(fs_evt_t const * const evt, fs_ret_t result);

static bool pump_event(void)
{
	if (result_queue_tail == result_queue_head)
		return false;
	uint32_t result = result_queue[result_queue_head++];
	result_queue_head %= RESULT_QUEUE_SIZE;

	fs_callback(NULL, result);
	return true;
}

static void pump_events(void)
{
	while (pump_event())
		;
}

/* There are six events that FDS can supply us with according to the
   fds_evt_id_t enumeration.

   We will keep a copy of the last event of each type so we can
   examine the return code at our leisure.

   So the sequence is:

   - mark the particular last_evt with bogus value (clear_event())

   - pump return events into the fds callback until last_evt takes on
     the correct value. (pump_and_wait())

   - return the return code out of that last_evt.
*/

static fds_evt_t last_evt[6];

static void clear_event(fds_evt_id_t evt_type)
{
	last_evt[evt_type].id = 0xff;
}

static void on_fds_event(fds_evt_t const * const p_evt)
{
	memcpy(last_evt + p_evt->id, p_evt, sizeof(fds_evt_t));
}

static bool await_fds_event(fds_evt_id_t evt_type, uint32_t *result)
{
	if (last_evt[evt_type].id != evt_type) {
		return false;
	} else {
		*result = last_evt[evt_type].result;
		return true;
	}
}

uint32_t pump_and_wait(fds_evt_id_t evt_type)
{
	uint32_t result=-1;

	while (!await_fds_event(evt_type, &result))
		pump_event();
	return result;
}

fs_ret_t fs_init(void)
{
	return 0;
}

/*
  Copies length_words words from p_src to the location pointed by
  p_dest.  If the length of the data exceeds FS_MAX_WRITE_SIZE_WORDS,
  the data will be written down in several chunks, as necessary. Only
  one event will be sent to the application upon completion. Both the
  source and the destination of the data must be word aligned. This
  function is asynchronous, completion is reported via an event sent
  the the callback function specified in the supplied configuration.

  Warning: The data to be written to flash has to be kept in memory
           until the operation has terminated, i.e., an event is
           received.

  p_config        fstorage configuration registered by the application.
  p_dest          The address in flash memory where to store the data.
  p_src           Pointer to the data to store in flash.
  length_words    Length of the data to store, in words.
  p_context       User-defined context passed to the interrupt handler.

  returns FS_SUCCESS              If the operation was queued successfully.
          FS_ERR_NOT_INITIALIZED  If the module is not initialized.
          FS_ERR_INVALID_CFG      If p_config is NULL or contains invalid data.
          FS_ERR_NULL_ARG         If p_dest or p_src are NULL.
          FS_ERR_INVALID_ARG      If length_words is zero.
          FS_ERR_INVALID_ADDR     If p_dest or p_src are outside of the flash memory
                                  boundaries specified in p_config.
          FS_ERR_UNALIGNED_ADDR   If p_dest or p_src are not aligned to a word boundary.
          FS_ERR_QUEUE_FULL       If the internal operation queue is full.
 */
fs_ret_t fs_store(fs_config_t const * const p_config,
                  uint32_t    const * const p_dest,
                  uint32_t    const * const p_src,
                  uint16_t    const         length_words,
                  void *                    p_context)
{
	int i;
	uint32_t *dest = (uint32_t *)p_dest;
	for (i=0; i<length_words; i++) {
		dest[i] &= p_src[i];
	}

	fs_callback = p_config->callback;
	add_result(0);

	return FS_SUCCESS;
}

/*
  Starting from the page at p_page_addr, erases num_pages flash pages.
  p_page_addr must be aligned to a page boundary. All pages to be
  erased must be within the bounds specified in the supplied fstorage
  configuration.  This function is asynchronous. Completion is
  reported via an event.

  p_config        fstorage configuration registered by the application.
  p_page_addr     Address of the page to erase. Must be aligned to a page boundary.
  num_pages       Number of pages to erase. May not be zero.
  p_context       User-defined context passed to the interrupt handler.

  returns FS_SUCCESS              If the operation was queued successfully.
          FS_ERR_NOT_INITIALIZED  If the module is not initialized.
          FS_ERR_INVALID_CFG      If p_config is NULL or contains invalid data.
          FS_ERR_NULL_ARG         If p_page_addr is NULL.
          FS_ERR_INVALID_ARG      If num_pages is zero.
          FS_ERR_INVALID_ADDR     If the operation would go beyond the flash memory boundaries
                                  specified in p_config.
          FS_ERR_UNALIGNED_ADDR   If p_page_addr is not aligned to a page boundary.
          FS_ERR_QUEUE_FULL       If the internal operation queue is full.
*/
fs_ret_t fs_erase(fs_config_t const * const p_config,
                  uint32_t    const * const p_page_addr,
                  uint16_t    const         num_pages,
                  void *                    p_context)
{
	uint32_t *page_addr = (uint32_t *)p_page_addr;
	memset(page_addr, 0xff, 4 * FDS_PHY_PAGE_SIZE * num_pages);

	fs_callback = p_config->callback;
	add_result(0);

	return FS_SUCCESS;
}

/* Configured filesystem size (per fds_config.h), in bytes */
int api_fs_size(void)
{
	return 4*FDS_VIRTUAL_PAGES*FDS_VIRTUAL_PAGE_SIZE;
}

int api_fds_mount(uint8_t *image)
{
	if (!is_word_aligned(image))
		return FDS_ERR_UNALIGNED_ADDR;

	fs_config.p_start_addr = (uint32_t *)image;

	clear_event(FDS_EVT_INIT);

	uint32_t ret = fds_register(on_fds_event);
	if (ret) return ret;

	ret = fds_init();
	if (ret) return ret;

	return pump_and_wait(FDS_EVT_INIT);
}

// Calls back with record_ids

int api_fds_dir(void (entry_cb)(uint32_t record_id))
{

	fds_record_desc_t   record_desc;
	fds_find_token_t    ftok = {0,};

	//memset(&ftok, 0, sizeof(ftok));

	while (fds_record_iterate(&record_desc, &ftok) == FDS_SUCCESS) {
		entry_cb(record_desc.record_id);
	}
	return 0;
}


uint32_t api_gc(void)
{
	clear_event(FDS_EVT_GC);

	uint32_t ret = fds_gc();
	if (ret) return ret;

	ret = pump_and_wait(FDS_EVT_GC);
	return ret;
}

uint32_t api_del_record(uint32_t record_id)
{
	fds_record_desc_t record_desc = {.record_id = record_id};

	uint32_t ret;

	clear_event(FDS_EVT_DEL_RECORD);

	ret = fds_record_delete(&record_desc);
	if (ret) return ret;

	return pump_and_wait(FDS_EVT_DEL_RECORD);
}

uint32_t api_del_file(uint32_t file_id)
{
	uint32_t ret;

	clear_event(FDS_EVT_DEL_FILE);

	ret = fds_file_delete(file_id);
	if (ret) return ret;

	return pump_and_wait(FDS_EVT_DEL_FILE);
}

uint32_t api_get_record(uint32_t record_id, // input
                        uint16_t *file_id, // output
                        uint16_t *record_key, // output
                        uint16_t *record_len, // output, in 32-bit words
                        uint8_t **data // output
                        )
{

	fds_record_desc_t record_desc = {.record_id = record_id};
	fds_flash_record_t flash_record;

	uint32_t ret;

	ret = fds_record_open(&record_desc, &flash_record);
	if (ret) return ret;

	if (file_id)
		*file_id = flash_record.p_header->ic.file_id;
	if (record_key)
		*record_key = flash_record.p_header->tl.record_key;
	if (record_len)
		*record_len = flash_record.p_header->tl.length_words;
	if (data)
		*data = (uint8_t *)flash_record.p_data;

	return fds_record_close(&record_desc);
}

uint32_t api_write_record(uint16_t record_key,
                          uint16_t file_id,
                          uint8_t *data,
                          int data_len_words)
{
	fds_record_t        record;
	fds_record_desc_t   record_desc;
	fds_record_chunk_t  record_chunk;
	// Set up data.
	record_chunk.p_data       = data;
	record_chunk.length_words = data_len_words;
	// Set up record.
	record.file_id         = file_id;
	record.key             = record_key;
	record.data.p_chunks   = &record_chunk;
	record.data.num_chunks = 1;

	clear_event(FDS_EVT_WRITE);

	uint32_t ret = fds_record_write(&record_desc, &record);
	if (ret) return ret;

	return pump_and_wait(FDS_EVT_WRITE);
}

uint32_t api_update_record(uint32_t record_id,
                           uint8_t *data,
                           int data_len_words)
{
	fds_record_t        record;
	fds_record_desc_t   record_desc = {.record_id = record_id};
	fds_record_chunk_t  record_chunk;
	// Set up data.
	record_chunk.p_data       = data;
	record_chunk.length_words = data_len_words;
	// Set up record.
	uint32_t ret;
	ret = api_get_record(record_id,
	                     &record.file_id,
	                     &record.key,
	                     NULL, NULL);
	if (ret) return ret;

	record.data.p_chunks   = &record_chunk;
	record.data.num_chunks = 1;

	clear_event(FDS_EVT_UPDATE);

	ret = fds_record_update(&record_desc, &record);
	if (ret) return ret;

	return pump_and_wait(FDS_EVT_UPDATE);
}
