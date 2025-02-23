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

        id_field = RealizedField(prod['name'], value=lf_node.name)

        hdr_ast_nodes = []
        for hdr_node in lf_node.children:
            hdr_ast_node = pdf_to_ast(grammar, hdr_node)
            hdr_ast_nodes.append(hdr_ast_node)
        hdr_field = RealizedField(prod['hdr'], hdr_ast_nodes)

        ast_node = AbstractSyntaxTree(prod, [id_field, hdr_field])

    elif lf_node.name in ['Type', 'SubType', 'Size', 'Length', 'Kids', 'Parent', 'Count', 'Limits',
                          'Range', 'Filter', 'Domain', 'FuncType', 'Pages', 'MediaBox', 'Resources'] :
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
        prod = grammar.get_prod_by_ctr_name('Variable')

        var_type_field = RealizedField(prod['type'], value='int')
        var_field = RealizedField(prod['variable'], value=lf_node.name[1:])

        ast_node = AbstractSyntaxTree(prod, [var_type_field, var_field])
    elif lf_node.name.startswith('H'):
        prod = grammar.get_prod_by_ctr_name('Variable')

        var_type_field = RealizedField(prod['type'], value='header')
        var_field = RealizedField(prod['variable'], value=lf_node.name[1:])

        ast_node = AbstractSyntaxTree(prod, [var_type_field, var_field])

    elif lf_node.name.startswith('R'):
        # expr = Reference(id ref)
        prod = grammar.get_prod_by_ctr_name('Reference')

        ref_var = 'obj' + lf_node.name[1:]
        ref_field = RealizedField(prod['ref'], value=ref_var)

        ast_node = AbstractSyntaxTree(prod, [ref_field])

    else:
        raise NotImplementedError

    return ast_node


def ast_to_pdf(asdl_ast):
    sb = StringIO()
    constructor_name = asdl_ast.production.constructor.name
    
    if constructor_name == 'Objective':
        name = asdl_ast['name'].value
        sb.write('( ')
        sb.write(name)
        for hdr in asdl_ast['hdr'].value:
            sb.write(' ')
            sb.write(ast_to_pdf(hdr))
        sb.write(' )')

    elif constructor_name == 'Apply':
        predicate = asdl_ast['predicate'].value
        sb.write('( ')
        sb.write(predicate)
        for arg in asdl_ast['arguments'].value:
            sb.write(' ')
            sb.write(ast_to_pdf(arg))
        sb.write(' )')

    elif constructor_name == 'Variable':
        var_type = asdl_ast['type'].value
        if var_type == 'int':
            var = 'I' + asdl_ast['variable'].value
        elif var_type == 'string':
            var = 'S' + asdl_ast['variable'].value
        elif var_type == 'header':
            var = 'H' + asdl_ast['variable'].value
        sb.write(var)

    elif constructor_name == 'Reference':
        ref = asdl_ast['ref'].value
        ref = 'R' + ref[3:]
        sb.write(ref)

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
        return ast_to_pdf(asdl_ast)# coding=utf-8
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

        id_field = RealizedField(prod['name'], value=lf_node.name)

        hdr_ast_nodes = []
        for hdr_node in lf_node.children:
            hdr_ast_node = pdf_to_ast(grammar, hdr_node)
            hdr_ast_nodes.append(hdr_ast_node)
        hdr_field = RealizedField(prod['hdr'], hdr_ast_nodes)

        ast_node = AbstractSyntaxTree(prod, [id_field, hdr_field])

    elif lf_node.name in ['Type', 'SubType', 'Size', 'Length', 'Kids', 'Parent', 'Count', 'Limits',
                          'Range', 'Filter', 'Domain', 'FuncType', 'Pages', 'MediaBox', 'Resources'] :
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
        prod = grammar.get_prod_by_ctr_name('Variable')

        var_type_field = RealizedField(prod['type'], value='int')
        var_field = RealizedField(prod['variable'], value=lf_node.name[1:])

        ast_node = AbstractSyntaxTree(prod, [var_type_field, var_field])
    elif lf_node.name.startswith('H'):
        prod = grammar.get_prod_by_ctr_name('Variable')

        var_type_field = RealizedField(prod['type'], value='header')
        var_field = RealizedField(prod['variable'], value=lf_node.name[1:])

        ast_node = AbstractSyntaxTree(prod, [var_type_field, var_field])

    elif lf_node.name.startswith('R'):
        # expr = Reference(id ref)
        prod = grammar.get_prod_by_ctr_name('Reference')

        ref_var = 'obj' + lf_node.name[1:]
        ref_field = RealizedField(prod['ref'], value=ref_var)

        ast_node = AbstractSyntaxTree(prod, [ref_field])

    else:
        raise NotImplementedError

    return ast_node


def ast_to_pdf(asdl_ast):
    sb = StringIO()
    constructor_name = asdl_ast.production.constructor.name
    
    if constructor_name == 'Objective':
        name = asdl_ast['name'].value
        sb.write('( ')
        sb.write(name)
        for hdr in asdl_ast['hdr'].value:
            sb.write(' ')
            sb.write(ast_to_pdf(hdr))
        sb.write(' )')

    elif constructor_name == 'Apply':
        predicate = asdl_ast['predicate'].value
        sb.write('( ')
        sb.write(predicate)
        for arg in asdl_ast['arguments'].value:
            sb.write(' ')
            sb.write(ast_to_pdf(arg))
        sb.write(' )')

    elif constructor_name == 'Variable':
        var_type = asdl_ast['type'].value
        if var_type == 'int':
            var = 'I' + asdl_ast['variable'].value
        elif var_type == 'string':
            var = 'S' + asdl_ast['variable'].value
        elif var_type == 'header':
            var = 'H' + asdl_ast['variable'].value
        sb.write(var)

    elif constructor_name == 'Reference':
        ref = asdl_ast['ref'].value
        ref = 'R' + ref[3:]
        sb.write(ref)

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

        actions = transition_system.get_actions(ast_tree)
        print(ast_tree.to_string())
        new_line = ast_to_pdf(ast_tree)
        print(new_line)

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

        actions = transition_system.get_actions(ast_tree)
        print(ast_tree.to_string())
        new_line = ast_to_pdf(ast_tree)
        print(new_line)
