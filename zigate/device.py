

class Device:

    def __init__(self, nwk_address=None, ieee_address=None, endpoints=None):
        assert nwk_address or ieee_address
        self.nwk_address = nwk_address
        self.ieee_address = ieee_address
        self.endpoints = endpoints or []
