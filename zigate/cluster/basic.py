import struct

from .core import Attribute, Cluster


def unpack_string(data):
    return data.decode('utf-8')

def struct_unpack(fmt):
    st = struct.Struct(fmt)
    def _(data):
        return st.unpack(data)[0]
    return _


class Basic(Cluster):
    __type__ = 0x0

    zcl_version = Attribute(0x0, unpack=struct_unpack('!B'))
    application_version = Attribute(0x1, unpack=struct_unpack('!B'))
    stack_version = Attribute(0x2, unpack=struct_unpack('!B'))
    hardware_version = Attribute(0x3, unpack=struct_unpack('!B'))
    manufacturer = Attribute(0x4)
    model = Attribute(0x5)
    date_code = Attribute(0x6)
    power_source = Attribute(0x7)
    location = Attribute(0x10)
    environment = Attribute(0x11)
    enabled = Attribute(0x12)
    alarm_mask = Attribute(0x13)
    disable_local_config = Attribute(0x14)
    build_id = Attribute(0x4000)

