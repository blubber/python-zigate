from functools import singledispatch, update_wrapper
import logging
from select import select

from . import protocol as p
from .device import Device
from .protocol.response import NetworkStarted, MatchDescriptorResponse, ActiveEndpointsResponse


logger = logging.getLogger(__name__)


def methdispatch(func):
    dispatcher = singledispatch(func)
    def wrapper(*args, **kw):
        return dispatcher.dispatch(args[1].__class__)(*args, **kw)
    wrapper.register = dispatcher.register
    update_wrapper(wrapper, func)
    return wrapper


class Manager:

    def __init__(self):
        self._devices = []

    def reset(self):
        logger.info('Resetting Zigate')
        self.send(p.reset())

    def by_nwk_address(self, nwk_address):
        for d in self._devices:
            if d.nwk_address == nwk_address:
                return d

    def by_ieee_address(self, ieee_address):
        for d in self._devices:
            if d.ieee_address == ieee_address:
                return d

    def send(self, data):
        raise NotImplementedError()

    def receive(self, data):
        for r in p.receive(data):
            self.handle_response(r)

    def discover(self, nwk_address):
        logger.info('Initiating device discovery for 0x%04x', nwk_address)

        if not self.by_nwk_address(nwk_address):
            device = Device(nwk_address)
            self._devices.append(device)
            self.send(p.request_active_endpoints(nwk_address))

    @methdispatch
    def handle_response(self, response):
        logger.debug('Handle response %s', response)

    @handle_response.register(NetworkStarted)
    def _(self, response):
        self.send(p.match_descriptor_request(0xfffd, p.request.Profile.Any))

    @handle_response.register(MatchDescriptorResponse)
    def _(self, response):
        if response.status != 0:
            return

        nwk_address = response.address

        logger.info('Device 0x%04x matches decsriptor', nwk_address)

        self.discover(nwk_address)

    @handle_response.register(ActiveEndpointsResponse)
    def _(self, response):
        logger.debug('Active endpoints for 0x%04x: %s', response.address,
                ', '.join(str(_) for _ in response.endpoints))

        device = self.by_nwk_address(response.address)
        if device and response.endpoints:
            logger.info('Requesting cluster list from 0x%04x on %d endpoint(s)',
                    device.nwk_address, len(response.endpoints))

            device.endpoints = response.endpoints

            for endpoint in device.endpoints:
                self.send(p.list_clusters(device.nwk_address, endpoint))


class SerialManager(Manager):

    def __init__(self, serial):
        super().__init__()
        self.serial = serial

    def send(self, data):
        self.serial.write(data)
        self.serial.flush()

    def select_loop(self):
        while True:
            self.select(timeout=0.01)

    def select(self, timeout):
        r, _, e = select([self.serial], [], [self.serial], timeout)

        if e:
            raise RuntimeError('Serial error')

        if r:
            self.receive(self.serial.read(1))
