import io
from collections import OrderedDict
from datetime import datetime

import logging
log = logging.getLogger('nm_payment')

from .fields import (
    BBSField, DelimitedField,
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


class BBSMessageBase(object):
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
        buf = io.BytesIO()
        for name, field in self._fields.items():
            field.write(getattr(self, name), buf)
        return buf.getvalue()

    @classmethod
    def unpack_fields(cls, data):
        fields = OrderedDict()

        buf = io.BytesIO(data)
        for name, field in cls._fields.items():
            fields[name] = field.read(buf)

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


class BBSMessage(BBSMessageBase, metaclass=BBSMessageMeta):
    pass


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
        # indicates transaction OK
        b'\x20': 'success',
        # indicates transaction/operation rejected
        b'\x21': 'failure',
    })

    acc = EnumField({
        # indicates standard update of accumulator
        b'\x20': 'standard',
        # indicates transaction is finalised as Offline transaction
        b'\x22': 'offline',
        # indicates no update of accumulator
        b'\x30': 'none',
    })

    # 2 digit issuer number is indicating the card issuer. Used if the
    # transaction was accepted. As long as the data is available, the data
    # shall be sent regardless if transaction is rejected or accepted.
    issuer_id = IntegerField(2)

    # Variable field lenght, Max. 19 digit if present. The Primary Account
    # Number from the card holder. The PAN shall not be sent if some parts of
    # the card number is replaced with "*" in the printout. The PAN field is of
    # restricted use, due to security regulations
    pan = DelimitedField(TextField(19), optional=True, delimiter=b';')

    # 14 byte numeric data. Timestamp in format YYYYMMDDHHMMSS. The timestamp
    # shall be the same data as received from the Host to the terminal in the
    # response message
    timestamp = DelimitedField(DateTimeField(), delimiter=b';')

    # Cardholder Verification Method
    ver_method = DelimitedField(EnumField({
        # transaction is PIN based, also to be used if reversal transaction
        b'\x30': 'pin based',
        # transaction is signature based
        b'\x31': 'signature based',
        # no CVM. Only amount is verified by cardholder
        b'\x32': 'not verified',
        # transaction is a Loyalty Transaction. Used for data capture
        # transactions. No accounts are debited or credited
        b'\x32': 'loyalty transaction',
    }), delimiter=b';')

    # 3 byte, numeric data. The current session number received from the HOST.
    # The session number is uncertain in case that the transaction is an
    # Offline transaction.  This number is changed on reconciliation.
    session_num = DelimitedField(IntegerField(3), delimiter=b';')

    # 12 byte, Alphanumeric data (H20-H7F). The STAN_AUTH and the TIMESTAMP
    # will identify the transaction.
    #   * On-line: The STAN (System Trace Audit Number) is the 6 first bytes,
    #     and the Authorisation Code is the 6 last bytes.
    #   * Off-line: STAN=9xxxx9 where x is the message number for the actual
    #     transaction AUTH = <H20H20H20H20H20H20>
    stan_auth = DelimitedField(TextField(12), delimiter=b';')

    # 4 bytes numeric data (H30 .. H39). This is the customer number if the
    # transaction was Pre-Auth transaction. Must be used as reference in
    # Transfer Amount - Adjustment transaction.
    seq_no = DelimitedField(IntegerField(4), delimiter=b';')

    # 11 bytes numeric data (H30 .. H39). Normally not used. Only used in
    # Restaurant or Hotel environmet where TIP is added to the purchase amount
    # on the ITU. Used in the Purchase or Adjustment transaction.
    tip = DelimitedField(PriceField(), optional=True, delimiter=b';')


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
        super(KeyboardInputMessage, self).__init__(text=text, **kwargs)

    @classmethod
    def unpack_fields(cls, data):
        # currently special cased because of fixed size `delimiter` field
        # following variable length `text` field.
        # TODO yuck yuck yuck
        fields = OrderedDict()

        fields['header'] = cls.type.read(data)

        text_data = data[cls.type.size:-cls.delimiter.size]
        fields['text'] = cls.text.read(io.BytesIO(text_data))

        delimiter_data = data[:-cls.delimiter.size]
        fields['delimiter'] = cls.delimiter.read(io.BytesIO(delimiter_data))


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


class DeviceAttributeRequestMessage(BBSMessage):
    # TODO
    pass


class DeviceAttributeMessage(BBSMessage):
    # TODO
    pass


class StatusMessage(BBSMessage):
    # TODO
    pass
