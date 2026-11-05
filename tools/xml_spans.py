"""Locate XML elements without reserializing namespaces, comments or formatting."""
from dataclasses import dataclass, field
from xml.parsers import expat


@dataclass
class Node:
    tag: str
    attrs: dict
    start: int
    open_end: int
    close_start: int = 0
    end: int = 0
    children: list = field(default_factory=list)

    def child(self, tag):
        matches = [n for n in self.children if n.tag == tag]
        if len(matches) != 1:
            raise ValueError(f'Expected one direct {tag}, found {len(matches)}')
        return matches[0]


def parse(text):
    data = text.encode('utf-8')
    parser = expat.ParserCreate()
    stack, nodes = [], []

    def token_end(start):
        quote = None
        for i in range(start, len(data)):
            value = data[i]
            if quote:
                if value == quote: quote = None
            elif value in (34, 39): quote = value
            elif value == 62: return i + 1
        raise ValueError('Unclosed XML token')

    def start(tag, attrs):
        at = parser.CurrentByteIndex
        node = Node(tag, attrs, at, token_end(at))
        if stack: stack[-1].children.append(node)
        nodes.append(node)
        stack.append(node)

    def end(tag):
        node = stack.pop()
        if data[node.start:node.open_end].rstrip().endswith(b'/>'):
            node.close_start = node.end = node.open_end
        else:
            node.close_start = parser.CurrentByteIndex
            node.end = token_end(node.close_start)

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.StartDoctypeDeclHandler = lambda *args: (_ for _ in ()).throw(ValueError('DTD is not supported'))
    parser.Parse(data, True)
    # Expat reports UTF-8 byte offsets; callers splice Python Unicode strings.
    offsets = {v for n in nodes for v in (n.start, n.open_end, n.close_start, n.end)}
    positions = {v: len(data[:v].decode('utf-8')) for v in offsets}
    for n in nodes:
        n.start, n.open_end, n.close_start, n.end = (positions[v] for v in (n.start, n.open_end, n.close_start, n.end))
    return nodes


def named(text, tag, name):
    matches = [n for n in parse(text) if n.tag == tag and n.attrs.get('name') == name]
    if len(matches) != 1:
        raise ValueError(f'Expected one {tag} named {name}, found {len(matches)}')
    return matches[0]
