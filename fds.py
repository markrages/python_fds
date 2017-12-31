#!/usr/bin/python3

import struct
import os

page_magic = struct.pack('<I',0xdeadc0de)
swap_magic = struct.pack('<I',0xf11e01ff)
data_magic = struct.pack('<I',0xf11e01fe)

def guess_page_size(image):
    pages = image.split(page_magic)
    if len(pages[0]):
        return False # Should start with page_magic
    pagelens = [len(p) + len(page_magic) for p in pages[1:]]
    uniqlens = set(pagelens)
    if len(uniqlens) != 1:
        return False # All pages not same length
    pagelen = uniqlens.pop()
    if pagelen % 256:
        return False # Page length not divisible by smallest physical page

    return pagelen//4 # Return value in words.

def crc16_compute(data):
    """Straight port of the bank CRC used by DFU

    data is a sequence or generator of integer in 0..255
    """
    crc = 0xffff
    for d in data:
        crc = (crc >> 8 & 0xff) | (crc << 8 & 0xff00)
        crc ^= d
        crc ^= (crc & 0xff) >> 4 & 0xff
        crc ^= crc << 12 & 0xffff
        crc ^= (crc & 0xff) << 5

    return crc

def getcrc(record):
    crcrecord = record[:6]+record[8:]
    return crc16_compute(crcrecord)

def decode_records(image, virtual_page_size, crc_check=False):
    page_size = 4 * virtual_page_size # in bytes
    assert len(image) % page_size == 0
    for page_start in range(0, len(image), page_size):
        page = image[page_start:page_start+page_size]
        if not page.startswith(page_magic): # bogus page
            continue
        if not page[4:8]==data_magic: # not data page, swap maybe
            continue
        page = page[8:]
        while len(page)>=12:
            key,length,file_id,crc,record_id = struct.unpack('<HHHHI',page[:12])
            length *= 4

            if len(page) < 12+length:
                page = page[12:]
                continue # partial data / illegal length

            record,page = page[:12+length],page[12+length:]
            data = record[12:]

            if file_id == 0xffff: # invalid
                continue
            if key == 0x0000: # deleted
                continue

            if crc_check and crc != getcrc(record):
                raise Exception("CRC Fail")

            yield {'file_id':file_id,
                   'key':key,
                   'record_id':record_id,
                   'data':data}

def encode_records(records, pages, virtual_page_size):
    page_size = 4*virtual_page_size
    image = b''

    i=0
    for page_start in range(0, page_size * pages, page_size):
        page_image = page_magic[:]
        if (page_start==0):
            page_image += swap_magic
        else:
            page_image += data_magic

            while i<len(records):
                if len(records[i]['data'])+12 + len(page_image) > page_size:
                    break
                record = records[i]
                data = record['data'][:]
                while len(data)%4:
                    data += b'\0'
                crc = getcrc(struct.pack('<HHHHI',
                                          record['key'],
                                          len(data)//4,
                                          record['file_id'],
                                          0,
                                          1+i)+record['data'])
                page_image += struct.pack('<HHHHI',
                                          record['key'],
                                          len(data)//4,
                                          record['file_id'],
                                          crc,
                                          1+i)
                page_image += record['data']
                i+=1

        pad_len = page_size - len(page_image)
        image += page_image
        image += b'\xff'*pad_len

    if i < len(records):
        raise Exception("All records do not fit.")

    return image

class Fds():
    def __init__(self,
                 image=None,
                 virtual_page_size=None, # In 32-bit words
                 virtual_pages=None):
        self.image = image
        self.virtual_page_size = virtual_page_size
        self.virtual_pages = virtual_pages

        if self.image:
            self.mount(self.image)
        else:
            self.records = []

    def mount(self, image):
        if not self.virtual_page_size:
            self.virtual_page_size = guess_page_size(image)
        if not self.virtual_pages:
            assert len(image) % 256 == 0
            assert len(image)//4 % self.virtual_page_size == 0
            self.virtual_pages = (len(image)//4)//self.virtual_page_size

        self.records = list(decode_records(image, self.virtual_page_size))

    def unmount(self):
        pass

    def dir(self):
        return list(range(len(self.records)))

    def write_record(self, record_key, file_id, data):
        while len(data)%4:
            data += b'\0'
        self.records.append({'file_id':file_id,
                             'key':record_key,
                             'record_id': len(self.records),
                             'data':data})

    def update_record(self, record_id, data):
        self.records[record_id]['data']=data

    def read_record(self, record_id):
        record = self.records[record_id]
        return record['file_id'],record['key'],record['data']

    def read_all(self):
        return self.records

    def delete_record(self, record_id):
        del self.records[record_id]

    def delete_file(self, file_id):
        self.records = [r for r in self.records if r['file_id'] != file_id]

    def gc(self):
        "garbage-collect, no-op."
        pass

    @property
    def contents(self):
        return encode_records(self.records,
                              self.virtual_pages,
                              self.virtual_page_size)

    def hd(self):
        "Prints a hexdump of the image to stdout using 'hd'"
        with open('/tmp/image.bin','wb') as fd:
            fd.write(self.contents)
        os.system('hd < /tmp/image.bin | tee /tmp/hexdump1')
        return open('/tmp/hexdump1').read()

def _crc_tests():
    import c.fds as cfds
    a = b'asdfhlakjshflaskjdhfla12346521845ASDFSADFsadf'
    py = crc16_compute(a)
    c = cfds.crc16_compute(a)
    assert py == c

def _tests():
    _crc_tests()
    _rw_tests()

def _rw_tests():
    import c.fds as cfds

    cfd = cfds.Fds()
    cfd.write_record(file_id=6,
                   record_key=100,
                   data=b"Hello World.")
    cfd.write_record(file_id=6,
                   record_key=2100,
                   data=b"Hello World. 2")
    # cfd.hd()

    fd = Fds(bytes(cfd.im))

    ids = fd.dir()
    assert len(ids)==2
    fid,key,data = fd.read_record(ids[0])
    assert fid==6
    assert key==100
    assert data==b"Hello World."

    assert cfd.read_all() == fd.read_all()

    cfd2 = cfds.Fds(fd.contents)
    assert fd.read_all() == cfd2.read_all()

    # fd.hd()
    print("pass")

if __name__=="__main__":
    _tests()
