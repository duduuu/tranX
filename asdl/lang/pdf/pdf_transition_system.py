# coding=utf-8
from __future__ import absolute_import

from collections import Iterable

from asdl.asdl import ASDLGrammar
from asdl.asdl_ast import RealizedField, AbstractSyntaxTree
from asdl.transition_system import GenTokenAction, TransitionSystem, ApplyRuleAction, ReduceAction

from common.registerable import Registrable

def parse_pdf_expr(s, offset):
    if s[offset] != '(':
        name = ''
        while offset < len(s) and s[offset] != ' ':
            name += s[offset]
            offset += 1

        node = Node(name)

        return node, offset

    else:
        offset += 2
        name = ''
        while s[offset] != ' ':
            name += s[offset]
            offset += 1

        node = Node(name)

        while True:
            if s[offset] != ' ':
                raise ValueError('malformed string')

            offset += 1
            if s[offset] == ')':
                offset += 1
                return node, offset
            else:
                child_node, offset = parse_pdf_expr(s, offset)

            node.add_child(child_node)


class Node(object):
    def __init__(self, name, children=None):
        self.name = name
        self.parent = None
        self.childeren = list()
        if children:
            if isinstance(children, Iterable):
                for child in children:
                    self.add_child(child)
            elif isinstance(children, Node):
                self.add_child(children)
            else:
                raise ValueError('Wrong type for child nodes')


def add_child(self, child):
    child.parent = self
    self.children.append(child)

def pdf_to_ast(grammar, lf_node):
    if lf_node.name.startswitch('obj'):
        # obj = Objective(id num, stmt* hdr)
        prod = grammar.get_prod_by_ctr_name('Obj')

        id_node = lf_node.name[:-3]
        id_field = RealizedField(prod['id'], id_node.name)

        hdr_ast_nodes = []
        for hdr_node in lf_node.children:
            hdr_ast_node = pdf_to_ast(grammar, hdr_node)
            hdr_ast_nodes.append(hdr_ast_node)
        hdr_field = RealizedField(prod['arguments'], hdr_ast_nodes)

        ast_node = AbstractSyntaxTree(prod, [id_field, hdr_field])

    elif lf_node.name in ['Type', 'SubType', 'Size', 'Length', 'Kids', 'Parent', 'Count', 'Limits', 'Range', 'Filter', 'Domain', 'FuncType'] :
        # stmt = Value(expr value)
        prod = grammar.get_prod_by_ctr_name(lf_node.name)

        value_node = lf_node.children
        value_field = RealizedField(prod['id'], value_node.name)

        ast_node = AbstractSyntaxTree(prod, value_field)

    elif lf_node.name.startswitch('S'):
        # expr = Str(string s)
        prod = grammar.get_prod_by_ctr_name('Str')

        var = lf_node.name[1:]

        ast_node = AbstractSyntaxTree(prod, RealizedField(prod['s'], value=var))

    elif lf_node.name.startswitch('I'):
        # expr = Integer(int i)
        prod = grammar.get_prod_by_ctr_name('Integer')

        var = int(lf_node.name[1:])

        ast_node = AbstractSyntaxTree(prod, RealizedField(prod['i'], value=var))

    elif lf_node.name.startswitch('['):
        # expr = Dict(expr* keys, expr* values)
        prod = grammar.get_prod_by_ctr_name('Dict')

        key_ast_nodes = []
        for key_node in lf_node.children:
            key_ast_node = pdf_to_ast(grammar, key_node)
            key_ast_nodes.append(key_ast_node)
        key_field = RealizedField(prod['values'], key_ast_nodes)

        value_ast_nodes = []
        for value_node in lf_node.children:
            value_ast_node = pdf_to_ast(grammar, value_node)
            value_ast_nodes.append(value_ast_node)
        value_field = RealizedField(prod['values'], value_ast_nodes)

        ast_node = AbstractSyntaxTree(prod, [key_field, value_field])

    elif lf_node.name.startswitch('R'):
        # expr = Reference(obj r)
        prod = grammar.get_prod_by_ctr_name('Reference')

        var = int(lf_node.name[1:])

        ast_node = AbstractSyntaxTree(prod, RealizedField(prod['r'], value=var))

    return ast_node


def ast_to_pdf(ast_tree):
    pass

def is_equal_ast(this_ast, other_ast):
    pass

@Registrable.register('pdf')
class PdfTransitionSystem(TransitionSystem):
    def tokenize_code(self, code, mode):
        return code.split(' ')

    def surface_code_to_ast(self, code):
        return pdf_to_ast(self.grammar, code)

    def ast_to_surface_code(self, asdl_ast):
        return ast_to_pdf(asdl_ast)

    def compare_ast(self, hyp_ast, ref_ast):
        return is_equal_ast(hyp_ast, ref_ast)

    def get_valid_continuation_types(self, hyp):
        pass

    def get_primitive_field_actions(self, realized_field):
        pass

if __name__ == '__main__':
    data_file = 'train.txt'
    grammar = ASDLGrammar.from_text(open('pdf_asdl.txt').read())
    transition_system = PdfTransitionSystem(grammar)

    for line in open(data_file):
        lf = parse_pdf_expr(line)
        ast_tree = pdf_to_ast(grammar, lf)
        ast_tree.sanity_check()
        """
        actions = transition_system.get.actions(ast_tree)
        new_lf = ast_to_pdf(ast_tree)
        assert lf == new_lf
        """

        print(ast_tree.to_string())