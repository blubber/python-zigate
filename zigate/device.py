from .cluster import core



class Device:

    def __init__(self, manager=None, nwk_address=None, ieee_address=None, endpoints=None):
        assert nwk_address or ieee_address

        self.manager = manager
        self.nwk_address = nwk_address
        self.ieee_address = ieee_address
        self.endpoints = endpoints or []
        self._clusters = {}

    def get_cluster(self, cluster_type, endpoint):
        return self._clusters[(cluster_type, endpoint)]

    def add_cluster(self, cluster_type, endpoint):
        cluster = None
        Cluster = core.lookup(cluster_type)
        if Cluster:
            name = Cluster.__name__.lower()
            if not hasattr(self, name):
                cluster = Cluster(self, endpoint)
                self._clusters[(cluster.__type__, cluster.endpoint)] = cluster
                setattr(self, name, cluster)

        return cluster
