from tempfile import NamedTemporaryFile
import io
import numpy as np
import sys
import os

from numpy.lib.utils import safe_eval
from numpy.compat import (long, asstr)

MAGIC_PREFIX = b'\x93NUMPY'
MAGIC_LEN = len(MAGIC_PREFIX) + 2

def _check_version(version):
    if version not in [(1, 0), (2, 0), None]:
        msg = "we only support format version (1,0) and (2, 0), not %s"
        raise ValueError(msg % (version,))

def _filter_header(s):
    """Clean up 'L' in npz header ints.

    Cleans up the 'L' in strings representing integers. Needed to allow npz
    headers produced in Python2 to be read in Python3.

    Parameters
    ----------
    s : byte string
        Npy file header.

    Returns
    -------
    header : str
        Cleaned up header.

    """
    import tokenize
    if sys.version_info[0] >= 3:
        from io import StringIO
    else:
        from StringIO import StringIO

    tokens = []
    last_token_was_number = False
    # adding newline as python 2.7.5 workaround
    string = asstr(s) + "\n"
    for token in tokenize.generate_tokens(StringIO(string).readline):
        token_type = token[0]
        token_string = token[1]
        if (last_token_was_number and
                token_type == tokenize.NAME and
                token_string == "L"):
            continue
        else:
            tokens.append(token)
        last_token_was_number = (token_type == tokenize.NUMBER)
    # removing newline (see above) as python 2.7.5 workaround
    return tokenize.untokenize(tokens)[:-1]

def _read_bytes(fp, size, error_template="ran out of data"):
    """
    Read from file-like object until size bytes are read.
    Raises ValueError if not EOF is encountered before size bytes are read.
    Non-blocking objects only supported if they derive from io objects.

    Required as e.g. ZipExtFile in python 2.6 can return less data than
    requested.
    """
    data = bytes()
    while True:
        # io files (default in python3) return None or raise on
        # would-block, python2 file will truncate, probably nothing can be
        # done about that.  note that regular files can't be non-blocking
        try:
            r = fp.read(size - len(data))
            data += r
            if len(r) == 0 or len(data) == size:
                break
        except io.BlockingIOError:
            pass
    if len(data) != size:
        msg = "EOF: reading %s, expected %d bytes got %d"
        raise ValueError(msg % (error_template, size, len(data)))
    else:
        return data

def read_magic(fp):
    """ Read the magic string to get the version of the file format.

    Parameters
    ----------
    fp : filelike object

    Returns
    -------
    major : int
    minor : int
    """
    magic_str = _read_bytes(fp, MAGIC_LEN, "magic string")
    if magic_str[:-2] != MAGIC_PREFIX:
        msg = "the magic string is not correct; expected %r, got %r"
        raise ValueError(msg % (MAGIC_PREFIX, magic_str[:-2]))
    if sys.version_info[0] < 3:
        major, minor = map(ord, magic_str[-2:])
    else:
        major, minor = magic_str[-2:]
    return major, minor

def descr_to_dtype(descr):
    '''
    descr may be stored as dtype.descr, which is a list of
    (name, format, [shape]) tuples. Offsets are not explicitly saved, rather
    empty fields with name,format == '', '|Vn' are added as padding.

    This function reverses the process, eliminating the empty padding fields.
    '''
    if isinstance(descr, (str, dict)):
        # No padding removal needed
        return np.dtype(descr)

    fields = []
    offset = 0
    for field in descr:
        if len(field) == 2:
            name, descr_str = field
            dt = descr_to_dtype(descr_str)
        else:
            name, descr_str, shape = field
            dt = np.dtype((descr_to_dtype(descr_str), shape))

        # Ignore padding bytes, which will be void bytes with '' as name
        # Once support for blank names is removed, only "if name == ''" needed)
        is_pad = (name == '' and dt.type is numpy.void and dt.names is None)
        if not is_pad:
            fields.append((name, dt, offset))

        offset += dt.itemsize

    names, formats, offsets = zip(*fields)
    # names may be (title, names) tuples
    nametups = (n  if isinstance(n, tuple) else (None, n) for n in names)
    titles, names = zip(*nametups)
    return np.dtype({'names': names, 'formats': formats, 'titles': titles,
                        'offsets': offsets, 'itemsize': offset})

def _read_array_header(fp, version):
    """
    see read_array_header_1_0
    """
    # Read an unsigned, little-endian short int which has the length of the
    # header.
    import struct
    if version == (1, 0):
        hlength_type = '<H'
    elif version == (2, 0):
        hlength_type = '<I'
    else:
        raise ValueError("Invalid version {!r}".format(version))

    hlength_str = _read_bytes(fp, struct.calcsize(hlength_type), "array header length")
    header_length = struct.unpack(hlength_type, hlength_str)[0]
    header = _read_bytes(fp, header_length, "array header")

    # The header is a pretty-printed string representation of a literal
    # Python dictionary with trailing newlines padded to a ARRAY_ALIGN byte
    # boundary. The keys are strings.
    #   "shape" : tuple of int
    #   "fortran_order" : bool
    #   "descr" : dtype.descr
    header = _filter_header(header)
    try:
        d = safe_eval(header)
    except SyntaxError as e:
        msg = "Cannot parse header: {!r}\nException: {!r}"
        raise ValueError(msg.format(header, e))
    if not isinstance(d, dict):
        msg = "Header is not a dictionary: {!r}"
        raise ValueError(msg.format(d))
    keys = sorted(d.keys())
    if keys != ['descr', 'fortran_order', 'shape']:
        msg = "Header does not contain the correct keys: {!r}"
        raise ValueError(msg.format(keys))

    # Sanity-check the values.
    if (not isinstance(d['shape'], tuple) or
            not np.all([isinstance(x, (int, long)) for x in d['shape']])):
        msg = "shape is not valid: {!r}"
        raise ValueError(msg.format(d['shape']))
    if not isinstance(d['fortran_order'], bool):
        msg = "fortran_order is not a valid bool: {!r}"
        raise ValueError(msg.format(d['fortran_order']))
    try:
        dtype = descr_to_dtype(d['descr'])
    except TypeError as e:
        msg = "descr is not a valid dtype descriptor: {!r}"
        raise ValueError(msg.format(d['descr']))

    return d['shape'], d['fortran_order'], dtype


def open_memmap(filename, mode='r+', max_num_of_row=0):

    # Read the header of the file first.
    fp = open(filename, 'rb')
    try:
        version = read_magic(fp)
        _check_version(version)

        shape, fortran_order, dtype = _read_array_header(fp, version)
        if dtype.hasobject:
            msg = "Array can't be memory-mapped: Python objects in dtype."
            raise ValueError(msg)
        offset = fp.tell()
    finally:
        fp.close()

    if fortran_order:
        order = 'F'
    else:
        order = 'C'

    # We need to change a write-only mode to a read-write mode since we've
    # already written data to the file.
    if mode == 'w+':
        mode = 'r+'

    sample_shape = (max_num_of_row, ) + shape[1:]
    marray = np.memmap(filename, dtype=dtype, shape=sample_shape, order=order,
                          mode=mode, offset=offset)

    return marray

# Takes raw bytes from SST-100 and make some samples
class Sampler:
    def __init__(self, rawbytes, filetype, num_sample_line_tup=(1000, 2000, 3000)):
        self.sample_filenames = []
        self.sample_filesizes = []
        self._num_sample_line_tup = num_sample_line_tup
        if filetype == 'txt':
            self._sampling_ascii(rawbytes)
        elif filetype == 'json':
            self._sampling_json(rawbytes)
        elif filetype == 'npy':
            self._sampling_numpy(rawbytes)
        else:
            raise Exception('file type not supported')
        self.sample_filesizes = np.asarray(self.sample_filesizes, dtype='int')


    def _sampling_ascii(self, rawbytes):
        i = 0
        line = 0
        for num_sample_line in self._num_sample_line_tup:
            # from the starting point, if we find the newline char
            # we take a sample before this point
            while line < num_sample_line:
                while rawbytes[i] != 0xa:
                    i += 1
                line += 1
                i += 1
            self._save(rawbytes, i, 'wb')

    def _sampling_json(self, rawbytes):
        # assume the first char in the file is always the open bracket, so skip it
        i = 1
        bracket_cnt = 0
        line = 0
        for num_sample_line in self._num_sample_line_tup:
            # at the beginning,
            # stack is empty, we get a row and need to find the next open bracket
            # to avoid keeping adding invalid line
            while rawbytes[i] != '{':
                i += 1

            while line < num_sample_line:
                if rawbytes[i] == '{':
                    bracket_cnt += 1

                # when we can close a bracket, we need to check the stack is empty or not
                elif rawbytes[i] == '}':
                    bracket_cnt -= 1
                    # if stack is empty, we first check we take enough rows for sampling
                    if bracket_cnt == 0:
                        line += 1

                        if line >= num_sample_line:
                            break

                        # if we haven't get to the required sampling number of rows,
                        # we need to find the next open bracket to avoid keeping adding invalid line
                        while rawbytes[i] != '{':
                            i += 1
                        bracket_cnt += 1

                i += 1

            partial_data = rawbytes[:i+1] + '}'
            self._save(partial_data, len(partial_data), 'w')

    def _sampling_numpy(self, rawbytes):
        tmp_mmap = NamedTemporaryFile()
        tmp_mmap.write(rawbytes)
        tmp_mmap.seek(0)
        memload = open_memmap(tmp_mmap.name, mode='r', max_num_of_row=max(self._num_sample_line_tup))
        for num_sample_line in self._num_sample_line_tup:
            tmp = NamedTemporaryFile(delete=False, suffix='.npy')
            arr = memload[:num_sample_line]
            np.save(tmp.name, arr)
            tmp.seek(0)
            self.sample_filenames.append(tmp.name)
            self.sample_filesizes.append(os.stat(tmp.name).st_size)
        tmp_mmap.close()

    def _save(self, rawbytes, i, mode):
        tmp = NamedTemporaryFile(delete=False, mode=mode)
        tmp.write(rawbytes[:i])
        tmp.seek(0)
        self.sample_filenames.append(tmp.name)
        self.sample_filesizes.append(os.stat(tmp.name).st_size)




