from decimal import Decimal


_UNDEFINED = object()


class BBSField(object):
    def __init__(self, size=None, default=_UNDEFINED):
        self.size = size
        if default is not _UNDEFINED:
            self.default = default

    def pack(self, value):
        """ Takes the value of a field and returns its binary representation

        :param value:
            A value of the type represented by the field

        :returns:
            A byte string representing the serialized value

        :raises ValueError:
            If ``value`` is invalid
        """
        raise NotImplementedError()

    def unpack(self, data):
        """ Reads the value of a field from a bytes object

        :param data:
            A bytes object from which to unpack the field

        :returns:
            A tuple of the parsed value and the number of bytes consumed

        :raises ValueError:
            If data does not match expected format
        """
        raise NotImplementedError()


class DelimitedField(BBSField):
    def __init__(self, inner, *, delimiter, optional=False, **kwargs):
        if len(delimiter) != 1:
            raise ValueError("only single character delimiters are supported")

        size = inner.size
        if size is not None:
            size += 1

        super(DelimitedField, self).__init__(size=size, **kwargs)

        self._inner = inner
        self._delimiter = delimiter
        self._optional = optional

    def pack(self, value):
        if value is None and self._optional:
            inner = b''
        else:
            inner = self._inner.pack(value)
        return inner + self._delimiter

    def unpack(self, data):
        end = data.find(self.delimiter)
        if end == -1:
            raise ValueError("could not find delimiter")

        value, size = self._inner.unpack(data[:end])

        if size != end:
            raise ValueError("inner field did not consume delimited data")

        return value, size + len(self._delimiter)


class TextField(BBSField):
    def pack(self, value):
        data = value.encode('ascii')

        if self.size is not None:
            # pad with spaces
            data = data + (self.size - len(data)) * b' '

            if len(data) != self.size:
                raise ValueError("string too long")

        return data

    def unpack(self, data):
        if self.size is not None:
            data = data[:self.size]
            if len(data) != self.size:
                raise ValueError("read data does not match expected size")

        return data.decode('ascii'), len(data)


class FormattedTextField(BBSField):
    # TODO inherit from TextField
    def pack(self, commands):
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

        return bytes(text)

    def unpack(self, data):
        text = data.decode('ascii')

        commands = []

        for message in text.split('\f'):
            # ignore trailing message and doubled up form feeds
            if not len(message):
                continue

            partitions = (p for p in message.split('\x0e') if len(p))

            # cut between partitions but not at beginning and end
            commands.append(('write', next(partitions)))
            for partition in partitions:
                commands.append('cut-partial')
                commands.append(('write', partition))

            commands.append('cut-through')

            return commands, len(data)


class IntegerField(BBSField):
    def __init__(self, size, **kwargs):
        super(IntegerField, self).__init__(size=size, **kwargs)

    def pack(self, integer):
        string = ('{:0' + str(self.size) + 'd}').format(integer)
        if len(string) != self.size:
            raise ValueError()

        return string.encode('ascii')

    def unpack(self, data):
        subdata = data[:self.size]
        if len(subdata) != self.size:
            raise ValueError("not enough data")

        string = subdata.decode('ascii')

        return int(string), self.size


class PriceField(BBSField):
    def __init__(self, size=11, **kwargs):
        super(PriceField, self).__init__(size=size, **kwargs)

    def pack(self, decimal):
        string = str(decimal)

        if self.size is not None:
            string = " " * (self.size - len(string)) + string

            if len(string) != self.size:
                raise ValueError("probably too much money")

        return string.encode('ascii')

    def unpack(self, data):
        subdata = data[:self.size]
        if len(subdata) != self.size:
            raise ValueError("not enough data")

        string = subdata.decode('ascii')

        if not string.isnumeric():
            raise ValueError("price data is not a positive integer")

        return Decimal(string) / 10000, self.size


class EnumField(BBSField):
    def __init__(self, values, *, size=None, default=_UNDEFINED, **kwargs):
        keys = iter(values.keys())
        if size is None:
            size = len(next(keys))
        for value in keys:
            if len(value) != size:
                raise ValueError("Enum value sizes do not match")

        # if only one value, set it as the default
        if default is _UNDEFINED and len(values) == 1:
            default = next(iter(values.values()))

        super(EnumField, self).__init__(size=size, default=default, **kwargs)

        self._from_enum = values
        self._to_enum = {value: key for key, value in values.items()}

    def pack(self, value):
        return self._to_enum[value]

    def unpack(self, data):
        subdata = data[:self.size]
        if len(subdata) != self.size:
            raise ValueError("not enough data")

        return self._from_enum[subdata], self.size


class ConstantField(BBSField):
    # TODO ConstantField is really a special case of enum
    # wasn't sure if I wanted to keep the interface for enum or use the value
    # attribute of constant for deciding what the type of a message was.
    default = None

    def __init__(self, value):
        super(ConstantField, self).__init__(len(value))
        self.value = value

    def pack(self, ignored):
        return self.value

    def unpack(self, data):
        subdata = data[:self.size]
        if len(subdata) != self.size:
            raise ValueError("not enough data")

        if subdata != self.value:
            raise ValueError("expected %r, got %r" % (self.value, data))

        return None, self.size


class DateTimeField(BBSField):
    # TODO
    pass
