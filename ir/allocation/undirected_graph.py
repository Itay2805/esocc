from typing import List, Set, Dict


class UndirectedGraph:
    """
    Used as an inference graph during register allocation.
    """

    class Node:

        def __init__(self):
            self.value = 0
            self.nodes: Set[int] = set()

        def __repr__(self):
            return f'Node({repr(self.value)}, {repr(self.nodes)})'

        def clone(self):
            n = UndirectedGraph.Node()
            n.value = self.value
            n.nodes = set(self.nodes)
            return n

    def __init__(self):
        self.nodes: List[UndirectedGraph.Node] = []
        self.node_map: Dict[int, UndirectedGraph.Node] = {}

    def get_nodes(self):
        return self.nodes

    def __len__(self):
        return len(self.nodes)

    def add_node(self, val):
        """
        Inserts a new lone node.
        """
        assert val not in self.node_map, "node already exists"
        
        n = UndirectedGraph.Node()
        n.value = val

        self.nodes.append(n)
        self.node_map[val] = n

    def add_edge(self, a, b):
        """
        Links between two nodes.
        """
        assert a in self.node_map, "cannot find node"
        assert b in self.node_map, "cannot find node"

        first = self.node_map[a]
        second = self.node_map[b]

        first.nodes.add(second.value)
        second.nodes.add(first.value)

    def remove_node(self, xid):
        """
        Removes a specified node along with its edges.
        """
        del self.node_map[xid]

        for n in self.nodes:
            if n.value == xid:
                for other in self.nodes:
                    if other.value != xid and xid in other.nodes:
                        other.nodes.remove(xid)

                self.nodes.remove(n)
                break

    def clear(self):
        """
        Removes all edges and nodes.
        """
        self.nodes.clear()
        self.node_map.clear()

    def has_less_k(self, k) -> bool:
        """
        Checks whether the graph contains a node of degree less than K.
        """
        for n in self.nodes:
            if len(n.nodes) < k:
                return True

        return False

    def find_less_k(self, k: int) -> int:
        """
        Returns a node of degree less than K.
        """
        for n in self.nodes:
            if len(n.nodes) < k:
                return n.value

        assert False, "node not found"

    def get_node(self, xid) -> Node:
        """
        Returns the node associated with the specified ID.
        """
        assert xid in self.node_map, "node not found"
        return self.node_map[xid]
