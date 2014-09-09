from struct import Struct
from collections import namedtuple


_display_text_format = Struct(
    '>B'  # CMSG
    'B'  # DU.NO
    'B'  # TYPE
    'B'  # MODE
)
_display_text_tuple = namedtuple(
    'display_text', 'prompt_customer, expects_input, text'
)


def pack_display_text(text, *, prompt_customer=False, expects_input=False):
    header = _display_text_format.pack(
        0x41,
        0x31 if prompt_customer else 0x30,
        0x31 if expects_input else 0x30,
        0x30
    )
    # TODO pad text (?)
    # TODO Norwegian encoding
    return header + text.encode('ascii')


def unpack_display_text(data):
    header, prompt_customer, expects_input, mode = \
        _display_text_format.unpack_from(data)

    if header != 0x41:
        raise ValueError()

    prompt_customer = {
        0x31: True,
        0x30: False,
    }[prompt_customer]

    expects_input = {
        0x31: True,
        0x30: False,
    }[expects_input]

    if mode != 0x30:
        raise ValueError()

    # TODO Norwegian encoding
    text = data[_display_text_format.size:].decode('ascii')

    return _display_text_tuple(
        prompt_customer=prompt_customer,
        expects_input=expects_input,
        text=text,
    )
