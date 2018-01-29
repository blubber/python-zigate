import struct

from .core import Attribute, Cluster


def unpack_string(data):
    return data.decode('utf-8')

def struct_unpack(fmt):
    st = struct.Struct(fmt)
    def _(data):
        return st.unpack(data)[0]
    return _


class OnOff(Cluster):
    __type__ = 0x6

    on_off = Attribute(0x0, unpack=struct_unpack('!?'))
    global_scene_control = Attribute(0x4000, unpack=struct_unpack('!?'))
    on_time = Attribute(0x4001, unpack=struct_unpack('!H'))
    off_wait_time = Attribute(0x4002, unpack=struct_unpack('!H'))
