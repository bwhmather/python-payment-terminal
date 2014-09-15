from collections import OrderedDict
from datetime import datetime

import logging
log = logging.getLogger('nm_payment')

from .fields import (
    BBSField,
    ConstantField, EnumField,
    IntegerField, PriceField,
    TextField, FormattedTextField,
    DateTimeField,
)


class BBSMessageMeta(type):
    def __new__(mcls, cls, bases, d):
        # find BBSField attributes and add them to a list of fields making up
        # a message
        # inherit from parent classes by updating fields dictionary
        # TODO this is a bit of a hack.  Would be much better to use super or
        # something but the obvious ways risk loosing the order.  With more
        # time this is something I would like to think through properly
        fields = OrderedDict()
        for base in bases:
            if hasattr(base, '_fields'):
                fields.update(base._fields)

        # read fields from class body
        for name, field in d.items():
            if isinstance(field, BBSField):
                fields[name] = field

        d['_fields'] = fields
        return type.__new__(mcls, cls, bases, d)

    @classmethod
    def __prepare__(mcls, cls, bases):
        # the dictionary to use to store class attributes
        # need to return OrderedDict rather than default dict as attribute
        # order affects parsing
        return OrderedDict()


class BBSMessage(metaclass=BBSMessageMeta):
    def __init__(self, **kwargs):
        for name, field in self._fields.items():
            if name in kwargs:
                value = kwargs[name]
            elif hasattr(field, 'default'):
                value = field.default
            else:
                raise TypeError('missing required argument: %r' % name)
            setattr(self, name, value)

    def pack(self):
        data = bytearray()
        for name, field in self._fields.items():
            data += field.pack(getattr(self, name))
        return bytes(data)

    @classmethod
    def unpack_fields(cls, data):
        fields = OrderedDict()

        offset = 0
        for name, field in cls._fields.items():
            # TODO multiple variable length fields
            if field.size is not None:
                fields[name] = field.unpack(data[offset:offset+field.size])
                offset += field.size
            else:
                fields[name] = field.unpack(data[offset:])
                offset = len(data)

        return fields

    @classmethod
    def unpack(cls, data):
        return cls(**cls.unpack_fields(data))

    def __repr__(self):
        parts = [self.__class__.__name__]
        parts += (
            "%s=%r" % (name, getattr(self, name))
            for name in self._fields
        )

        return "<%s>" % " ".join(parts)


class DisplayTextMessage(BBSMessage):
    type = ConstantField(b'\x41')

    prompt_customer = EnumField({
        b'\x31': True,
        b'\x30': False,
    }, default=True)

    expects_input = EnumField({
        b'\x31': True,
        b'\x30': False,
    }, default=False)

    mode = ConstantField(b'\x30')

    text = TextField()

    def __init__(self, text, **kwargs):
        # allow `text` to be passed in as a positional argument
        super(DisplayTextMessage, self).__init__(text=text, **kwargs)


class PrintTextMessage(BBSMessage):
    type = ConstantField(b'\x42')

    sub_type = EnumField({b'\x20': 'Formatted'})

    media = EnumField({
        b'\x20': 'print_on_receipt',
        b'\x21': 'print_on_journal',
        b'\x22': 'print_on_both',
    }, default='print_on_both')

    mode = EnumField({b'\x2a': 'normal_text'})

    commands = FormattedTextField()


class ResetTimerMessage(BBSMessage):
    type = ConstantField(b'\x43')

    seconds = IntegerField(3)

    def __init__(self, seconds, **kwargs):
        # allow `seconds` to be passed in as a positional argument
        super(ResetTimerMessage, self).__init__(seconds=seconds, **kwargs)


class LocalModeMessage(BBSMessage):
    type = ConstantField(b'\x44')

    result = EnumField({
        b'\x20': 'success',
        b'\x21': 'failure',
    })

    acc = EnumField({
        # indicates standard update of accumulator.
        b'\x20': 'standard',
        # indicates transaction is finalised as Offline transaction.
        b'\x22': 'offline',
        # indicates no update of accumulator.
        b'\x30': 'none',
    })

    issuer_id = IntegerField(2)

    def pack(self):
        header = super(LocalModeMessage, self).pack()

        # TODO
        raise NotImplementedError()

    @classmethod
    def unpack_fields(cls, data):
        header_fields = super(LocalModeMessage, cls).unpack_fields()

        # rest of data is sent as ';' separated strings.  No trailing ';'
        pan, timestamp, ver_method, session_num, stan_auth, seq_no, tip = \
            data[_local_mode_format.size:].split(';')

        acc

        id_

        pan

        timestamp = datetime.strptime(timestamp, '%Y%m%d%H%M%S')

        ver_method = [
            "pin based",
            "signature based",
            "not verified",
            "loyalty transaction",
        ][int(ver_method)]

        session_num = int(session_num)

        stan_auth

        seq_no = int(seq_no)

        tip

        return dict(
            pan=pan, timestamp=timestamp, ver_method=ver_method,
            session_num=session_num, stan_aut=stan_aut, seq_no=seq_no, tip=tip,
            **header_fields
        )


class KeyboardInputRequestMessage(BBSMessage):
    type = ConstantField(b'\x46')

    echo = EnumField({
        b'\x20': True,
        b'\x21': False,
    })

    min_chars = TextField(2)
    max_chars = TextField(2)


class KeyboardInputMessage(BBSMessage):
    type = ConstantField(b'\x55')

    text = TextField()

    # XXX how are you supposed to parse this
    delimiter = EnumField({
        b'0': 'Enter',
        b'9': 'Escape',
    })

    def __init__(self, text, **kwargs):
        # allow `text` to be passed in as a positional argument
        super(KeyboardInputMesage, self).__init__(text=text, **kwargs)

    @classmethod
    def unpack_fields(cls, data):
        # currently special cased because of fixed size `delimiter` field
        # following variable length `text` field.
        # TODO generalize.
        fields = OrderedDict()

        fields['header'] = cls.type.unpack(
            data[:cls.type.size]
        )

        fields['text'] = cls.text.unpack(
            data[cls.type.size:-cls.delimiter.size]
        )

        fields['delimiter'] = cls.delimiter.unpack(
            data[:-cls.delimiter.size]
        )


class SendDataMessageBase(BBSMessage):
    type = ConstantField(b'\x46')
    code = TextField(2)
    is_last_block = EnumField({
        b'\x32': True,
        b'\x31': False,
    })

    seq = TextField(4)  # ignored
    length = TextField(3)  # ignored


class SendReportsDataHeaderMessage(SendDataMessageBase):
    code = ConstantField(b'\x30\x31')

    site_number = TextField(6)
    session_number = TextField(3)
    timestamp = DateTimeField()


class SendReconciliationDataAmountsMessage(SendDataMessageBase):
    code = ConstantField(b'\x30\x32')

    issuer_id = TextField(2)
    num_transactions = IntegerField(4)

    # TODO


class SendDataMessage(SendDataMessageBase):
    code = EnumField({
        subfunction.code.value: subfunction
        for subfunction in [
            SendReportsDataHeaderMessage,
            SendReconciliationDataAmountsMessage,
            # TODO
        ]
    })

    @classmethod
    def unpack(cls, data):
        self = super(SendDataMessage, cls).unpack(data)

        return self.code.unpack(data)


class TransferAmountMessage(BBSMessage):
    type = ConstantField(b'\x51')
    timestamp = DateTimeField()  # not used
    id_no = TextField(6)  # not used
    seq_no = TextField(4)  # TODO
    operator_id = TextField(4)
    mode = EnumField({
        b'\x30': None,
    })
    transfer_type = EnumField({
        b'\x30': 'EFT Authorisation',
        b'\x31': 'Return of Goods',
        b'\x32': 'Reversal',
        b'\x33': 'Purchase with Cashback',
        b'\x34': 'PRE Authorisation',
        b'\x35': 'Adjustment',
        b'\x36': 'Balance Inquiry',
        b'\x37': 'Complete Receipt',
        b'\x38': 'Deposit',
        b'\x39': 'Cash Withdrawal',
        b'\x3a': 'Load e-purse card',
        b'\x3b': 'Merchandise Purchase',
        b'\x3c': 'Merchandise Reversal',
        b'\x3d': 'Merchandise Correction',
    })

    amount = PriceField(11)
    unused_type = EnumField({b'\x30': None})
    cashback_amount = PriceField(11)
    top_up_type = EnumField({
        b'\x30': True,
        b'\x31': False,
    })
    art_amount = PriceField(11)

    # TODO DATA, ART#


class TransferCardDataMessage(BBSMessage):
    type = ConstantField(b'\x52')
    block = EnumField({b'\x30': None})
    track = EnumField({
        b'\x32': 'Track 2',
        b'\x33': 'Track 1',
        b'\x40': 'Manual',
    })

    # TODO DATA and FS


class AdministrationMessage(BBSMessage):
    type = ConstantField(b'\x53')
    timestamp = DateTimeField()
    id_no = TextField(6)
    seq_no = TextField(4)
    opt = TextField(4)

    # TODO single character keyboard input
    adm_code = EnumField({
        b'\x30\x30': 'not used',
        b'\x30\x39': 'not used',
        # SEND from ECR should be mapped by ITU to perform RECONCILIATION
        # function.
        b'\x31\x30': 'SEND',
        # KLAR, validation key. Refer to the NOTE for details
        b'\x31\x31': 'KLAR',
        # AVBRYT, cancellation key. Refer to the NOTE for details.
        b'\x31\x32': 'AVBRYT',
        # FEIL, correction key.
        b'\x31\x33': 'FEIL',
        # ANNUL from ECR should be mapped by ITU to perform REVERSAL
        # transaction.
        b'\x31\x34': 'ANNUL',
        b'\x31\x35': 'Balance Inquiry transaction',
        b'\x31\x36': 'X-report',
        b'\x31\x37': 'Z-report',
        b'\x31\x38': 'send Offline Transactions to HOST',
        b'\x31\x39': 'Turnover report',
        b'\x31\x3A': 'print of stored EOT transactions',
        b'\x31\x3B': 'not used',
        b'\x31\x3C': 'not used',
        b'\x31\x3D': 'not used',
        b'\x31\x3E': 'not used',
    })

    fs = ConstantField(b'\x1C')


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
