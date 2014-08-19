from abc import ABCMeta


class Terminal(metaclass=ABCMeta):
    def shutdown(self):
        pass
