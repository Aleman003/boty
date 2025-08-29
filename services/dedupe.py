from collections import OrderedDict

class LRUSet:
    def __init__(self, cap=5000):
        self.cap = cap
        self.d = OrderedDict()
    def add_if_new(self, key: str) -> bool:
        if not key:
            return True
        if key in self.d:
            self.d.move_to_end(key)
            return False
        self.d[key] = None
        if len(self.d) > self.cap:
            self.d.popitem(last=False)
        return True

dedupe = LRUSet(5000)
