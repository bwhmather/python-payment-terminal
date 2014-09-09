from struct import Struct
from collections import namedtuple
from datetime import datetime

import logging
log = logging.getLogger('nm_payment')


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


_print_text_format = Struct(
    '>B'  # CMSG
    'B'  # SUB
    'B'  # MEDIA
    'B'  # MODE
)


def pack_print_text(commands):
    header = _print_text_format.pack(
        0x42,
        0x20,
        0x22,  # always print to journal and receipt
        0x2a,
    )

    text = bytearray()

    def op_write(text):
        return text.encode('ascii')

    for command in commands:
        if isinstance(command, str):
            command_name, args = command, []
        else:
            command_name = command[0]
            args = command[1:]

        command = {
            'write': op_write,
            'cut-partial': b'\x0e',
            'cut-through': b'\f',
        }[command_name]

        if isinstance(command, bytes):
            text += command
        else:
            text += command(*args)

    return header + text


def unpack_print_text(data):
    header, sub, media, mode = _print_text_format.unpack_from(data)

    if header != 0x42:
        raise ValueError()

    if sub != 0x20:
        raise ValueError()

    if media != 0x22:
        if media in {0x20, 0x21}:
            # TODO
            log.warn("should always print and record print messages")
        else:
            raise ValueError()

    if mode != 0x2a:
        raise ValueError()

    text = data[_print_text_format.size:].decode('ascii')

    for message in text.split('\f'):
        # ignore trailing message and doubled up form feeds
        if not len(message):
            continue

        partitions = (p for p in message.split('\x0e') if len(p))

        # cut between partitions but not at beginning and end
        yield ('write', next(partitions))
        for partition in partitions:
            yield ('cut-partial')
            yield ('write', partition)

        yield ('cut-through')


_reset_timer_format = Struct(
    '>B'  # CMSG
    '3s'  # SEC
)


def pack_reset_timer(seconds):
    seconds = '{:03.0f}'.format(seconds).encode('ascii')
    if len(seconds) > 3:
        raise ValueError()

    return _reset_timer_format.pack(0x43, seconds)


def unpack_reset_timer(data):
    header, seconds = _reset_timer_format.unpack(data)

    if header != 0x43:
        raise ValueError()

    seconds = int(seconds)

    return seconds


def pack_local_mode():
    # TODO
    raise NotImplementedError()


def unpack_local_mode(data):
    # TODO
    raise NotImplementedError()


_keyboard_input_request_format = Struct(
    '>B'  # CMSG
    'B'  # ECHO
    '2s'  # MIN
    '2s'  # MAX
)
_keyboard_input_request_tuple = namedtuple(
    'keyboard_input_request', 'echo, min_chars, max_chars'
)


def pack_keyboard_input_request(echo=False, min_chars=0, max_chars=99):
    min_chars = '{:02.0f}'.format(min_chars).encode('ascii')
    if len(min_chars) > 2:
        raise ValueError()

    max_chars = '{:03.0f}'.format(max_chars).encode('ascii')
    if len(max_chars) > 2:
        raise ValueError()

    return _keyboard_input_request_format.pack(
        0x46,
        0x20 if echo else 0x21,
        min_chars,
        max_chars
    )


def unpack_keyboard_input_request(data):
    header, echo, min_chars, max_chars = \
        _keyboard_input_request_format.unpack(data)

    if header != 0x46:
        raise ValueError()

    echo = {
        0x20: True,
        0x21: False,
    }[echo]

    min_chars = int(min_chars)
    max_chars = int(max_chars)

    return _keyboard_input_request_tuple(
        echo=echo, min_chars=min_chars, max_chars=max_chars
    )


def pack_keyboard_input(text):
    return b'0x55' + text.encode('ascii') + b'0'


def unpack_keyboard_input(data):
    header = ord(data[0])
    if header != 0x55:
        raise ValueError()

    return data[1:-1].decode('ascii')


def pack_send_data():
    # TODO
    raise NotImplementedError()


def unpack_send_data_request(data):
    # TODO
    raise NotImplementedError()


def pack_transfer_amount():
    # TODO
    raise NotImplementedError()


def unpack_transfer_amount(data):
    # TODO
    raise NotImplementedError()


def pack_transfer_card_data():
    # TODO
    raise NotImplementedError()


def unpack_transfer_card_data(data):
    # TODO
    raise NotImplementedError()


def pack_administration_request():
    # TODO
    raise NotImplementedError()


def unpack_administration_request(data):
    # TODO
    raise NotImplementedError()


def pack_device_attribute_request():
    # TODO
    raise NotImplementedError()


def unpack_device_attribute_request(data):
    # TODO
    raise NotImplementedError()


def pack_device_attribute():
    # TODO
    raise NotImplementedError()


def unpack_device_attribute(data):
    # TODO
    raise NotImplementedError()


def pack_status():
    # TODO
    raise NotImplementedError()


def unpack_status():
    # TODO
    raise NotImplementedError()
