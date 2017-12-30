#!/usr/bin/python3

import ctypes

import os,sys,copy,math
this_path = os.path.dirname(os.path.realpath(__file__))

assert(0==os.system('cd "%s" && make default' % this_path))

fds_lib = None
libnames = ['fds_x86_64.so','fds_x86.so']

while libnames:
    so = libnames.pop()
    try:
        fds_lib = ctypes.CDLL(os.path.join(this_path,so))
        break
    except OSError: # load failed
        if not libnames:
            raise

# Errors from fds.h
errtab = {}
for errno, (name, desc) in enumerate(
        [("FDS_SUCCESS",                "The operation completed successfully."),
         ("FDS_ERR_OPERATION_TIMEOUT",  "The operation timed out."),
         ("FDS_ERR_NOT_INITIALIZED",    "The module has not been initialized."),
         ("FDS_ERR_UNALIGNED_ADDR",     "The input data is not aligned to a word boundary."),
         ("FDS_ERR_INVALID_ARG",        "The parameter contains invalid data."),
         ("FDS_ERR_NULL_ARG",           "The parameter is NULL."),
         ("FDS_ERR_NO_OPEN_RECORDS",    "The record is not open, so it cannot be closed."),
         ("FDS_ERR_NO_SPACE_IN_FLASH",  "There is no space in flash memory."),
         ("FDS_ERR_NO_SPACE_IN_QUEUES", "There is no space in the internal queues."),
         ("FDS_ERR_RECORD_TOO_LARGE",   "The record exceeds the maximum allowed size."),
         ("FDS_ERR_NOT_FOUND",          "The record was not found."),
         ("FDS_ERR_NO_PAGES",           "No flash pages are available."),
         ("FDS_ERR_USER_LIMIT_REACHED", "The maximum number of users has been reached."),
         ("FDS_ERR_CRC_CHECK_FAILED",   "The CRC check failed."),
         ("FDS_ERR_BUSY",               "The underlying flash subsystem was busy."),
         ("FDS_ERR_INTERNAL",           "An internal error occurred."),
        ]):
    locals()[name]=errno
    errtab[errno] = name, desc

class FDSException(Exception):
    def __init__(self, errno):
        try:
            name, desc = errtab[errno]
        except KeyError:
            name = "FDS_UNKNOWN_%d"%errno
            desc = "Unknown error #%d"%errno
        self.args = errno,name,desc

class Fds(object):
    def __init__(self, image=None):
        size = fds_lib.api_fs_size()
        if image:
            if len(image) != size:
                raise Exception("Image must be exactly %d bytes."%size)
        else:
            image = b'\xff'*size

        self.mount(image)

    def mount(self, image):
        """Supply an image (as bytes) to mount as fds filesystem.

        All bytes = 255 for a new filesystem"""

        size = fds_lib.api_fs_size()
        assert len(image) == size

        self.im = ctypes.create_string_buffer(image, size)
        fds_lib.api_fds_mount.restype = ctypes.c_int

        result = fds_lib.api_fds_mount(self.im)

        if result:
            raise FDSException(result)

    def unmount(self):
        pass

    def dir(self):
        """Gets a list of record_ids, not too meaningful by themselves.
        See read_all() for a more useful function."""

        entries=[]
        def collect_entry(record_id):
            entries.append(int(record_id))

        EntryCallback = ctypes.CFUNCTYPE(None,
                                         ctypes.c_uint32, # record_id
        )
        entry_cb = EntryCallback(collect_entry)

        result = fds_lib.api_fds_dir(entry_cb)

        if result:
            raise FDSException(result)

        return entries

    def write_record(self, record_key, file_id, data):

        pad_len = (4-len(data)%4)%4
        data += b'\0'*pad_len

        assert 0 == len(data)%4
        assert 0 <= record_key < 0x10000
        assert 0 <= file_id < 0x10000

        result = fds_lib.api_write_record(record_key,
                                          file_id,
                                          data,
                                          len(data)//4)
        if result:
            raise FDSException(result)

    def update_record(self, record_id, data):
        "Replaces a record by creating a new one and deleting the old one"
        pad_len = (4-len(data)%4)%4
        data += b'\0'*pad_len

        assert 0 == len(data)%4
        assert 0 <= record_id < 0x100000000

        result = fds_lib.api_update_record(record_id,
                                          data,
                                          len(data)//4)
        if result:
            raise FDSException(result)

    def read_record(self, record_id):
        "Reads an individual record given the record_id"
        key = ctypes.c_uint16()
        file_id = ctypes.c_uint16()
        data = ctypes.POINTER(ctypes.c_uint8)()
        data_len_words = ctypes.c_int()

        result = fds_lib.api_get_record(record_id,
                                        ctypes.byref(file_id),
                                        ctypes.byref(key),
                                        ctypes.byref(data_len_words),
                                        ctypes.byref(data))

        if result:
            raise FDSException(result)

        file_id = int(file_id.value)
        key = int(key.value)
        data_len_words = int(data_len_words.value)
        data = bytes(data[i] for i in range(4*data_len_words))

        return file_id,key,data


    def read_all(self):
        "Returns a list-of-dicts of all records"
        ret = []
        for record_id in self.dir():
            file_id,key,data = self.read_record(record_id)
            ret.append({'file_id':file_id,
                        'key':key,
                        'record_id':record_id,
                        'data':data})
        return ret

    def delete_record(self, record_id):
        "Removes a single record."
        result = fds_lib.api_del_record(record_id)
        if result:
            raise FDSException(result)

    def delete_file(self, file_id):
        "Marks all records belonging to file as deleted."
        result = fds_lib.api_del_file(file_id)
        if result:
            raise FDSException(result)

    def gc(self):
        "Garbage collect."
        result = fds_lib.api_gc()
        if result:
            raise FDSException(result)

    def hd(self):
        "Prints a hexdump of the image to stdout using 'hd'"
        with open('/tmp/image.bin','wb') as fd:
            fd.write(self.im)
        os.system('hd < /tmp/image.bin')

def _tests(fds_mount):
    s = fds_mount

    ids = s.dir()
    assert len(ids)==0

    s.write_record(file_id=6,
                   record_key=100,
                   data=b"Hello World.")

    ids = s.dir()
    assert len(ids)==1
    fid,key,data = s.read_record(ids[0])
    assert fid==6
    assert key==100
    assert data==b"Hello World."

    s.write_record(file_id=6,
                   record_key=100,
                   data=b"Hello World2.")
    ids = s.dir()
    print(ids)
    assert len(ids)==2
    s.delete_record(ids[-1])
    ids = s.dir()
    assert len(ids)==1

    k = 0
    while 1:
        try:
            s.write_record(record_key=100,
                           file_id=6,
                           data=("Hello World %d."%k).encode())
        except FDSException as e:
            if e.args[0] == FDS_ERR_NO_SPACE_IN_FLASH:
                break
            else:
                raise
        k += 1

    assert len(s.dir())==1+k

    s.gc()
    assert len(s.dir())==1+k

    s.delete_file(6)
    assert len(s.dir())==0

    try:
        s.write_record(file_id=8,
                       record_key=1234,
                       data=b"This data won't fit.")
    except FDSException as e:
        assert e.args[0] == FDS_ERR_NO_SPACE_IN_FLASH
    else:
        assert False # didn't get the exception we wanted

    s.gc() # now records will fit

    s.write_record(file_id=66,
                   record_key=234,
                   data=b"This is the first data.")

    ids = s.dir()
    assert len(ids)==1

    s.update_record(ids[0],
                    data=b"This is the second data.")

    ids = s.dir()
    assert len(ids)==1

    fid,key,data = s.read_record(ids[0])
    assert fid==66
    assert key==234
    assert data==b"This is the second data."

    s.write_record(file_id=66,
                   record_key=234,
                   data=b"This is the third data.")

    all_data = s.read_all()
    assert len(all_data)==2
    assert all_data[0]['file_id']==66
    assert all_data[0]['key']==234
    assert all_data[0]['data']==b"This is the second data."

    s.hd()

if __name__=="__main__":
    fs = Fds()
    _tests(fs)
