import logging
import struct


_responses = {}
_receive_buffer = bytearray()
logger = logging.getLogger(__name__)


class Response:

    def __init__(self, type_, length, checksum, value, rssi):
        self.type = type_
        self.length = length
        self.checksum = checksum
        self.value = value
        self.rssi = rssi

    def __str__(self):
        return 'Response(tag=0x%04x, length=%d, checksum=0x%04x, value=0x%s, rssi=%d)' % (
                self.type, self.length, self.checksum, self.value.hex(), self.rssi)


def register(type_):
    assert type_ not in _responses, 'Duplicate response type 0x%04x' % type_

    def decorator(func):
        _responses[type_] = func
        return func

    return decorator


@register(0x8046)
class MatchDescriptorResponse(Response):

    def __init__(self, *args):
        super().__init__(*args)
        self.seq_nr, self.status, self.address, count = \
                struct.unpack('!BBHB', self.value[:5])

    def __str__(self):
        return '<MatchDesriptorResponse from 0x%04x, status=%s, value=0x%s>' % (
                self.address, self.status, self.value.hex())


@register(0x8000)
class Status(Response):

    def __init__(self, *args):
        super().__init__(*args)
        self.status, self.seq_nr, self.packet_type = \
                struct.unpack('!BBH', self.value[:4])
        self.info = self.value[4:]

    @property
    def ok(self):
        return self.status == 0

    def __str__(self):
        return 'Status %d (ok=%s), info=%s' % (self.status, self.ok, self.info)


@register(0x8043)
class ClusterResponse(Response):

    def __init__(self, *args):
        super().__init__(*args)

        self.in_clusters = self.out_clusters = []
        value = self.value

        _, _, _, _, _, self.profile, self.device_id, self.bit_fields, in_count = \
                struct.unpack('!BBHBBHHBB', value[:12])

        value = value[12:]

        if in_count:
            self.in_clusters = struct.unpack('!%dH' % in_count, value[:2 * in_count])
            value = value[2 * in_count:]

        out_count = value[0]
        value = value[1:]
        print(in_count, out_count)

        if out_count:
            self.out_clusters = struct.unpack('!%dH' % out_count, value[:2 * out_count])

    def __str__(self):
        in_clusters = ['0x%04x' % c for c in sorted(self.in_clusters)]
        out_clusters = ['0x%04x' % c for c in sorted(self.out_clusters)]

        return 'Clusters supported by 0x%0x, in=[%s], out=[%s]. Profile=0x%0x' % (
                0x00, ', '.join(in_clusters), ', '.join(out_clusters), self.profile)


@register(0x8003)
class ListClusters(Response):

    def __init__(self, *args):
        super().__init__(*args)

        self.endpoint, self.profile = struct.unpack('!BH', self.value[:3])

        self.clusters = self.value[3:]

    def __str__(self):
        clusters = ['0x%04x' % c for c in sorted(self.clusters)]

        return '\n\nClusters supported by 0x%0x=[%s], profile=0x%0x\n\n' % (
                self.endpoint, ', '.join(clusters), self.profile)


@register(0x8015)
class DevicesList(Response):

    def __init__(self, *args):
        super().__init__(*args)

        self.devices = []

        self.struct = struct.Struct('!BHQBB')

        for i in range(0, int((self.length - 1) / self.struct.size)):
            dev_id, nwk_address, ieee_address, power_source, link_quality = \
                    self.struct.unpack(self.value[i * self.struct.size:(i + 1) * self.struct.size])
            self.devices.append({'dev_id': dev_id, 'nwk_address': nwk_address, 'ieee_address': ieee_address, 'power_source': power_source, 'link_quality': link_quality})


    def __str__(self):
        return '<DevicesList %s>' % ', '.join('{ id=%d, nwk_address=0x%04x, ieee_address=0x%016x, power_source=%s, link_quality=%d }' % (dev['dev_id'], dev['nwk_address'], dev['ieee_address'], 'AC' if dev['power_source'] else 'battery', dev['link_quality']) for dev in self.devices)


@register(0x8024)
class NetworkStarted(Response):

    def __init__(self, *args):
        super().__init__(*args)

        self.status, self.nwk_address, self.ieee_address, self.channel = \
                struct.unpack('!BHQB', self.value)

    def __str__(self):
        return '<NetworkStarted status=%d, nwk_address=0x%04x, channel=%d, existing=%s' % (
                self.status, self.nwk_address, self.channel, self.status == 0)


@register(0x8045)
class ActiveEndpointsResponse(Response):

    def __init__(self, *args):
        super().__init__(*args)

        self.seq_nr, self.status, self.address, count = \
                struct.unpack('!BBHB', self.value[:5])

        self.endpoints = self.value[5:]

        assert len(self.endpoints) == count

    def __str__(self):
        return '<ActiveEndpointsResonse from=0x%04x, count=%d>' % (
                self.address, len(self.endpoints))



@register(0x8102)
class IndividualAttributeReport(Response):

    def __init__(self, *args):
        super().__init__(*args)

        attr_struct = struct.Struct('!BHBHHBBH')
        self.seq_nr, self.src_addr, self.endpoint, self.cluster_id, self.attr_enum, self.attr_status, self.atrr_data_type, self.attr_size = \
                attr_struct.unpack(self.value[:attr_struct.size])
        logger.debug("%s %s", attr_struct.size, len(self.value[attr_struct.size:]))
        self.data_byte_list = struct.unpack('!%ds' % self.attr_size, self.value[attr_struct.size:])

    def __str__(self):
        return '<IndividualAttributeReport attr_enum=%d, cluster_id=%d, src_addr=%x, data_byte_list=%s>' % (self.attr_enum, self.cluster_id, self.src_addr, self.data_byte_list)


def receive(data):
    global _receive_buffer

    _receive_buffer.extend(data)

    start_pos = _receive_buffer.find(0x01)
    end_pos = _receive_buffer.find(0x03)

    while end_pos > -1:
        if end_pos < start_pos:
            logger.warning('Malformed data received')
        else:
            part = _receive_buffer[start_pos:end_pos + 1]
            decoded = _decode(part)
            response = _unpack_raw_message(decoded)

            logger.debug('Received response %s', response)

            yield response

        _receive_buffer = _receive_buffer[end_pos + 1:]
        start_pos = _receive_buffer.find(0x01)
        end_pos = _receive_buffer.find(0x03)


def _decode(data):
    flip = False
    decoded = bytearray()
    for b in data[1:-1]:
        if flip:
            flip = False
            decoded.append(b ^ 0x10)
        elif b == 0x02:
            flip = True
        else:
            decoded.append(b)
    return decoded


def _unpack_raw_message(decoded):
    type_, length, checksum, value, rssi = \
            struct.unpack('!HHB%dsB' % (len(decoded) - 6), decoded)
    return _responses.get(type_, Response)(type_, length, checksum, value, rssi)
