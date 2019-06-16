# coding=utf-8
from __future__ import absolute_import

from io import StringIO

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
        self.children = list()
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

    def __hash__(self):
        code = hash(self.name)

        for child in self.children:
            code = code * 37 + hash(child)

        return code

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False

        if self.name != other.name:
            return False

        if len(self.children) != len(other.children):
            return False

        else:
            return self.children == other.children

    def __ne__(self, other):
        return not self.__eq__(other)

    def __repr__(self):
        return 'Node[%s, %d children]' % (self.name, len(self.children))

    @property
    def is_leaf(self):
        return len(self.children) == 0

    def to_string(self, sb=None):
        is_root = False
        if sb is None:
            is_root = True
            sb = StringIO()

        if self.is_leaf:
            sb.write(self.name)
        else:
            sb.write('( ')
            sb.write(self.name)

            for child in self.children:
                sb.write(' ')
                child.to_string(sb)

            sb.write(' )')

        if is_root:
            return sb.getvalue()


def pdf_to_ast(grammar, lf_node):
    if lf_node.name.startswith('obj'):
        # obj = Objective(id name, expr* hdr)
        prod = grammar.get_prod_by_ctr_name('Objective')

        id_field = RealizedField(prod['id'], value=lf_node.name)

        hdr_ast_nodes = []
        for hdr_node in lf_node.children:
            hdr_ast_node = pdf_to_ast(grammar, hdr_node)
            hdr_ast_nodes.append(hdr_ast_node)
        hdr_field = RealizedField(prod['hdr'], hdr_ast_nodes)

        ast_node = AbstractSyntaxTree(prod, [id_field, hdr_field])

    elif lf_node.name in ['Type', 'SubType', 'Size', 'Length', 'Kids', 'Parent', 'Count', 'Limits', 'Range', 'Filter', 'Domain', 'FuncType'] :
        # expr -> Apply(pred predicate, expr* arguments)
        prod = grammar.get_prod_by_ctr_name('Apply')

        pred_field = RealizedField(prod['predicate'], value=lf_node.name)

        arg_ast_nodes = []
        for arg_node in lf_node.children:
            arg_ast_node = pdf_to_ast(grammar, arg_node)
            arg_ast_nodes.append(arg_ast_node)
        arg_field = RealizedField(prod['arguments'], arg_ast_nodes)

        ast_node = AbstractSyntaxTree(prod, [pred_field, arg_field])

    elif lf_node.name.startswith('S'):
        # expr = Variable(var_type type, var variable)
        prod = grammar.get_prod_by_ctr_name('Variable')

        var_type_field = RealizedField(prod['type'], value='string')

        var_field = RealizedField(prod['variable'], value=lf_node.name[1:])

        ast_node = AbstractSyntaxTree(prod, [var_type_field, var_field])

    elif lf_node.name.startswith('I'):
        # expr = Variable(var_type type, var variable)
        prod = grammar.get_prod_by_ctr_name('Variable')

        var_type_field = RealizedField(prod['type'], value='string')

        var_field = RealizedField(prod['variable'], value=int(lf_node.name[1:]))

        ast_node = AbstractSyntaxTree(prod, [var_type_field, var_field])

    elif lf_node.name.startswith('R'):
        # expr = Reference(id ref)
        prod = grammar.get_prod_by_ctr_name('Reference')

        var = 'obj' + lf_node.name[1:]

        ast_node = AbstractSyntaxTree(prod, RealizedField(prod['ref'], value=var))

    return ast_node


def ast_to_pdf(lf_node):
    sb = StringIO()
    constructor_name = lf_node.production.constructor.name
    if constructor_name == 'Object':
        name = lf_node['name']
        sb.write(' (')
        sb.write(name)
    elif constructor_name == 'Apply':
        predicate = lf_node['predicate'].value
        sb.write(predicate)
        sb.write(' (')

        sb.write(' )')
    elif constructor_name == 'Variable':
        var_type = lf_node['var_type'].value

    return sb.getvalue()


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
        lf, offset = parse_pdf_expr(line, 0)
        ast_tree = pdf_to_ast(grammar, lf)
        ast_tree.sanity_check()
        """
        actions = transition_system.get.actions(ast_tree)
        new_lf = ast_to_pdf(ast_tree)
        assert lf == new_lf
        """

        print(ast_tree.to_string())