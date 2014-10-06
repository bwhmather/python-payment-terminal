class BBSSession(object):
    def __init__(self, connection):
        super(BBSSession, self).__init__()
        self._connection = connection
        self._connection.set_current_session(self)

    def on_req_display_text(
            self, data, *,
            expects_input=False, prompt_customer=False):
        # TODO
        pass

    def on_req_reset_timer(self, data):
        # TODO
        pass

    def on_req_local_mode(self, data):
        # should be implemented by subclass
        raise NotImplementedError()

    def on_req_keyboard_input(self, data):
        # should be implemented by subclass
        raise NotImplementedError()

    def on_req_send_data(self, data):
        # should be implemented by subclass
        raise NotImplementedError()

    def unbind(self):
        pass
