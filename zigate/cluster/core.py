import logging


from blinker import signal
from enum import Enum


logger = logging.getLogger(__name__)
_clusters = {}


class ClusterMeta(type):

    def __new__(cls, name, bases, attrs):
        klass =  type.__new__(cls, name, bases, attrs)

        if not (name == 'Cluster' and bases is tuple()):
            assert '__type__' in attrs, 'Specify Cluster.__type__'

            type_ = attrs['__type__']
            assert type_ not in _clusters, ('Cluster type 0x%04x already registered' % type_)

            _clusters[type_] = klass
            klass._attributes = {}
            klass._attribute_descriptors = {}

            for name, attr in attrs.items():
                if isinstance(attr, Attribute):
                    klass._attributes[attr.type] = None
                    klass._attribute_descriptors[attr.type] = attr

        return klass


class Cluster(metaclass=ClusterMeta):

    def __init__(self, device, endpoint):
        self._attributes = self.__class__._attributes.copy()
        self.device = device
        self.endpoint = endpoint
        self.attr_notify = signal('zigate_attr_notify')

    def set_attribute_value(self, attribute, value):
        try:
            unpack = self._attribute_descriptors[attribute].unpack
        except KeyError:
            unpack = lambda x: x

        unpacked = unpack(value)

        logger.debug('Setting cluster 0x%04x attribute 0x%04x = %r',
                self.__type__, attribute, unpacked)

        self._attributes[attribute] = unpacked
        self.attr_notify.send(self, attribute=attribute, value=unpacked)


class Attribute:

    def __init__(self, type_, pack=None, unpack=None):
        self.type = type_
        self.pack = pack or (lambda x: x)
        self.unpack = unpack or (lambda x: x)

    def __get__(self, instance, owner):
        try:
            return instance._attributes[self.type]
        except KeyError:
            raise AttributeError('Cluster has no attribute 0x%04x' % self.type)


def lookup(name):
    return _clusters.get(name)
