from enum import Enum
import functools
import itertools
import logging
from operator import xor
import struct


logger = logging.getLogger(__name__)


class ZigateType(Enum):
    Coordinator = 0
    Router = 1
    LegacyRouter = 2


class OnOff(Enum):
    Off = 0
    On = 1
    Toggle = 2


class Profile(Enum):
    ZHA = 0x10
    Any = 0xffff


class Command:

    def __init__(self, type_, fmt=None, raw=False):
        assert not (raw and fmt), 'Raw commands cannot use built-in struct formatting'

        self.type = type_
        self.raw = raw
        if fmt:
            self.struct = struct.Struct(fmt)
        else:
            self.struct = None

    def __call__(self, func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            rv = func(*args, **kwargs)

            if self.struct:
                try:
                    data = self.struct.pack(*rv)
                except TypeError:
                    data = self.struct.pack(rv)
            elif self.raw:
                data = rv
            else:
                data = bytearray()

            return prepare(self.type, data)

        return wrapper


def prepare(type_, data):
    length = len(data)

    checksum = functools.reduce(xor, itertools.chain(
            type_.to_bytes(2, 'big'),
            length.to_bytes(2, 'big'),
            data), 0)

    message = struct.pack('!HHB%ds' % length, type_, length, checksum, data)
    encoded_message = _encode(message)

    logger.debug('Prepared command 0x%04x, data=0x%s -> 0x%s',
            type_, message.hex(), encoded_message.hex())

    return encoded_message


@Command(0x11)
def reset():
    logger.info('Preparing reset command')


@Command(0x15)
def get_devices_list():
    logger.info('Getting list of authenticated devices')


@Command(0x21, '!I')
def set_channels(channels=None):
    channels = channels or [11, 14, 15, 19, 20, 24, 25]
    mask = functools.reduce(lambda acc, x: acc ^ 2 ** x, channels, 0)

    logger.info('Setting channels to %s', channels)

    return mask


@Command(0x23, '!B')
def set_type(type_=ZigateType.Coordinator):
    logger.info('Setting type to %s', type_)
    return type_.value


@Command(0x24)
def start_network():
    logger.info('Starting network')


@Command(0x46, '!HHBB')
def match_descriptor_request(address, profile=Profile.ZHA):
    return address, profile.value, 0, 0


@Command(0x49, '!HBB')
def permit_joins(seconds=254):
    assert 0 < seconds < 255, 'Seconds must be a value between 0 and 254 (inclusive)'
    logger.info('Permitting joins for %ds' % seconds)
    return (0xfffc, seconds, 0)


@Command(0x71, '!BHBB')
def identify(address, address_mode=0x01, src_endpoint=0xff, dst_endpoint=0xff):
    logger.info('Request identification from 0x%0x', address)
    return address_mode, address, src_endpoint, dst_endpoint


@Command(0x92, '!BHBBB')
def set_on_off(address, action=OnOff.Toggle, address_fashion=0x02, src_endpoint=0x01, dst_endpoint=0x01):
    logger.info('Setting ON / OFF state with %s on 0x%0x', action, address)
    return address_fashion, address, src_endpoint, dst_endpoint, action.value


@Command(0xc0, '!BHBBHH')
def set_color(address, temp, transition=0x0, address_fashion=0x02, src=0x01, dst=0x01):
    assert 0 <= temp < 65535
    assert 0 <= transition < 65535

    logger.info('Setting color temperature to %d on 0x%0x', temp, address)

    return address_fashion, address, src, dst, temp, transition


@Command(0x45, '!H')
def request_active_endpoints(address):
    logger.info('Requesting active endpoints from 0x%04x', address)
    return address


@Command(0x43, '!HB')
def list_clusters(address, endpoint):
    logger.info('List clusters from 0x%0x:%d', address, endpoint)
    return address, endpoint


@Command(0x0081, '!BHBBBBB')
def set_level(address, level):
    return 0x02, address, 0x01, 0x01, 0x01, level, 0x00


def _encode(data):
    encoded = bytearray([0x01])
    for b in data:
        if b < 0x10:
            encoded.extend([0x02, 0x10 ^ b])
        else:
            encoded.append(b)
    encoded.append(0x03)
    return encoded
