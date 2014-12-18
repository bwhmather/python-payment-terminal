from collections import OrderedDict

import logging
log = logging.getLogger('payment_terminal')

from .fields import (
    BBSField, DelimitedField,
    ConstantField, EnumField,
    IntegerField, PriceField,
    TextField, FormattedTextField,
    DateTimeField,
)


class BBSMessageMeta(type):
    def __new__(mcls, cls, bases, d):
        fields = OrderedDict()

        # inherit fields from first base class with `_fields` attribute
        for base in bases:
            if hasattr(base, '_fields'):
                fields.update(base._fields)
                break

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
        return b''.join(
            field.pack(getattr(self, name))
            for name, field in self._fields.items()
        )

    @classmethod
    def unpack_fields(cls, data):
        fields = OrderedDict()

        offset = 0
        for name, field in cls._fields.items():
            fields[name], size = field.unpack(data[offset:])
            offset += size

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
    is_response = False


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

    sub_type = EnumField({b'\x20': 'formatted'})

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
        b'\x30': 'pin_based',
        # transaction is signature based
        b'\x31': 'signature_based',
        # no CVM. Only amount is verified by cardholder
        b'\x32': 'not_verified',
        # transaction is a Loyalty Transaction. Used for data capture
        # transactions. No accounts are debited or credited
        b'\x32': 'loyalty_transaction',
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
    is_response = True

    text = TextField()

    # XXX how are you supposed to parse this
    delimiter = EnumField({
        b'0': 'enter',
        b'9': 'escape',
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

        fields['header'], size = cls.type.read(data)

        text_data = data[size:-cls.delimiter.size]
        fields['text'], size = cls.text.unpack(text_data)

        delimiter_data = data[-cls.delimiter.size:]
        fields['delimiter'], size = cls.delimiter.unpack(delimiter_data)


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
        b'\x30': 'eft_authorisation',
        b'\x31': 'return_of_goods',
        b'\x32': 'reversal',
        b'\x33': 'purchase_with_cashback',
        b'\x34': 'pre_authorisation',
        b'\x35': 'adjustment',
        b'\x36': 'balance_inquiry',
        b'\x37': 'complete_receipt',
        b'\x38': 'deposit',
        b'\x39': 'cash_withdrawal',
        b'\x3a': 'load_epurse_card',
        b'\x3b': 'merchandise_purchase',
        b'\x3c': 'merchandise_reversal',
        b'\x3d': 'merchandise_correction',
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
        b'\x32': 'track_2',
        b'\x33': 'track_1',
        b'\x40': 'manual',
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
        b'\x30\x30': 'not_used',
        b'\x30\x39': 'not_used',
        # SEND from ECR should be mapped by ITU to perform RECONCILIATION
        # function.
        b'\x31\x30': 'send',
        # KLAR, validation key. Refer to the NOTE for details
        b'\x31\x31': 'ready',
        # AVBRYT, cancellation key. Refer to the NOTE for details.
        b'\x31\x32': 'cancel',
        # FEIL, correction key.
        b'\x31\x33': 'error',
        # ANNUL from ECR should be mapped by ITU to perform REVERSAL
        # transaction.
        b'\x31\x34': 'reverse',
        b'\x31\x35': 'balance_inquiry_transaction',
        b'\x31\x36': 'x_report',
        b'\x31\x37': 'z_report',
        b'\x31\x38': 'send_offline_transactions',
        b'\x31\x39': 'turnover_report',
        b'\x31\x3A': 'print_eot_transactions',
        b'\x31\x3B': 'not_used',
        b'\x31\x3C': 'not_used',
        b'\x31\x3D': 'not_used',
        b'\x31\x3E': 'not_used',
    })

    fs = ConstantField(b'\x1C')


class DeviceAttributeRequestMessage(BBSMessage):
    type = ConstantField(b'\x60')


class DeviceAttributeMessage(BBSMessage):
    type = ConstantField(b'\x61')


class StatusMessage(BBSMessage):
    type = ConstantField(b'\x62')
    is_response = True


class ResponseMessage(BBSMessage):
    type = ConstantField(b'\x5b')
    is_response = True

    code = EnumField({
        # OK. The Receiver has received and processed the data correctly
        b'\x30\x30': 'success',
        # Not OK. The receiver is not able to process the received data
        b'\x30\x33': 'failure',
        # Not OK. Shall be treated as if H3033 is received
        b'\x30\x34': 'failure',
        b'\x30\x35': 'failure',
        b'\x30\x36': 'failure',
        b'\x30\x37': 'failure',
        b'\x30\x38': 'failure',
        b'\x30\x39': 'failure',
        # ECR display busy, ITU may try again once
        b'\x31\x31': 'display_busy',
        # ECR printer busy, ITU may try again once
        b'\x31\x32': 'printer_busy',
        # ECR printer out of function.
        # If the ECR sends H3133, the ITU must interrupt the current
        # transaction, and wait for the next 'Bank-Mode' initiation from the
        # ECR
        b'\x31\x33': 'printer_broken'
    })

    endcode = ConstantField(b'\x5d')


_ITU_MESSAGE_TYPES = {
    DisplayTextMessage,
    PrintTextMessage,
    ResetTimerMessage,
    LocalModeMessage,
    KeyboardInputRequestMessage,
    SendDataMessage,
    DeviceAttributeRequestMessage,
    StatusMessage,
}


class ITUMessage(BBSMessage):
    type = EnumField({
        subtype.type.value: subtype
        for subtype in _ITU_MESSAGE_TYPES
    })


def unpack_itu_message(data):
    header = ITUMessage.unpack(data)
    return header.type.unpack(data)


_ECR_MESSAGE_TYPES = {
    KeyboardInputMessage,
    SendDataMessage,
    TransferAmountMessage,
    AdministrationMessage,
    DeviceAttributeMessage,
}


class ECRMessage(BBSMessage):
    type = EnumField({
        subtype.type.value: subtype
        for subtype in _ECR_MESSAGE_TYPES
    })


def unpack_ecr_message(data):
    header = ECRMessage.unpack(data)
    return header.type.unpack(data)
