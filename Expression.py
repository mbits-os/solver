OP_UNKNOWN = 0
OP_NUMBER  = 1
OP_STRING  = 2
OP_NAME    = 3
OP_LPAREN  = 4
OP_RPAREN  = 5
OP_NEG     = 6
OP_LT      = 7
OP_GT      = 8
OP_LE      = 9
OP_GE      = 10
OP_EQ      = 11
OP_NE      = 12
OP_ANDS    = 13
OP_PIPES   = 14
OP_END     = 15
OP_ANY     = 16

tok_name = {
    OP_UNKNOWN : "unknown",
    OP_NUMBER  : "number",
    OP_STRING  : "string",
    OP_NAME    : "identifier",
    OP_LPAREN  : "(",
    OP_RPAREN  : ")",
    OP_NEG     : "!",
    OP_LT      : "<",
    OP_GT      : ">",
    OP_LE      : "<=",
    OP_GE      : ">=",
    OP_EQ      : "==",
    OP_NE      : "!=",
    OP_ANDS    : "&&",
    OP_PIPES   : "||",
    OP_END     : "endline",
    OP_ANY     : "identifier, number or string",
    None       : "(null)"
    }

class Not:
    def __init__(self, expr):
        self.expr = expr
        
    def value(self): return not self.expr.value()
    def __str__(self): return "!%s" % self.expr

class Paren:
    def __init__(self, expr):
        self.expr = expr

    def value(self): return self.expr.value()
    def __str__(self): return "(%s)" % self.expr

class Macro:
    def __init__(self, name, source):
        self.name = name
        self.source = source

    def value(self):
        val = self.source.value(self.name)
        if not val: return 0 # int(val)
        return val

    def __str__(self): return self.name
    
class Defined:
    def __init__(self, name, source):
        self.name = name
        self.source = source

    def value(self):
        return self.source.defined(self.name)
    def __str__(self): return "defined(%s)" % self.name

class Number:
    def __init__(self, val):
        self.val = val

    def value(self): return self.val
    def __str__(self): return "%s" % self.val

class String:
    def __init__(self, val):
        self.val = val

    def value(self): return self.val
    def __str__(self): return '"%s"' % self.val

class Lt:
    def __init__(self, left, right):
        self.left = left
        self.right = right

    def value(self): return self.left.value() < self.right.value()
    def __str__(self): return '[%s < %s]' % (self.left, self.right)

class Gt:
    def __init__(self, left, right):
        self.left = left
        self.right = right

    def value(self): return self.left.value() > self.right.value()
    def __str__(self): return '[%s > %s]' % (self.left, self.right)

class Le:
    def __init__(self, left, right):
        self.left = left
        self.right = right

    def value(self): return self.left.value() <= self.right.value()
    def __str__(self): return '[%s <= %s]' % (self.left, self.right)

class Ge:
    def __init__(self, left, right):
        self.left = left
        self.right = right

    def value(self): return self.left.value() >= self.right.value()
    def __str__(self): return '[%s >= %s]' % (self.left, self.right)

class Eq:
    def __init__(self, left, right):
        self.left = left
        self.right = right

    def value(self): return self.left.value() == self.right.value()
    def __str__(self): return '[%s == %s]' % (self.left, self.right)

class Ne:
    def __init__(self, left, right):
        self.left = left
        self.right = right

    def value(self): return self.left.value() != self.right.value()
    def __str__(self): return '[%s != %s]' % (self.left, self.right)

class And:
    def __init__(self, left, right):
        self.left = left
        self.right = right

    def value(self):
        if not self.left.value(): return 0
        return self.right.value()
    def __str__(self): return '[%s && %s]' % (self.left, self.right)

class Or:
    def __init__(self, left, right):
        self.left = left
        self.right = right

    def value(self):
        if self.left.value(): return 1
        return self.right.value()
    def __str__(self): return '[%s || %s]' % (self.left, self.right)

class Expr:
    def parse(self, source, macros):
        self.source = source
        self.macros = macros
        self.source.source_cleanup()
        ex = self._or()
        self.source.ensure(OP_END)
        #print ex, "=", ex.value()
        return ex

    def _expr(self):
        tok = self.source.peek()
        if tok == OP_NEG:
            self.source.next()
            return Not(self._expr())
        if tok == OP_LPAREN:
            self.source.next()
            expr = self._or()
            self.source.ensure(OP_RPAREN)
            return Paren(expr)
        if tok == OP_NAME:
            self.source.next()
            if self.source.value() == "defined":
                self.source.ensure(OP_LPAREN)
                self.source.ensure(OP_NAME)
                macro = self.source.value()
                self.source.ensure(OP_RPAREN)
                return Defined(macro, self.macros)
            else:
                return Macro(self.source.value(), self.macros)
        if tok == OP_STRING:
            self.source.next()
            return String(self.source.value())
        if tok == OP_NUMBER:
            self.source.next()
            return Number(self.source.value())
        self.source.ensure(OP_ANY)

    def _rel(self):
        left = self._expr()
        while 1:
            op = self.source.peek()
            if op not in (OP_LT, OP_GT, OP_LE, OP_GE):
                return left
            op = self.source.next()
            #print left, tok_name[op], "..."
            if op == OP_LT: left = Lt(left, self._expr())
            if op == OP_GT: left = Gt(left, self._expr())
            if op == OP_LE: left = Le(left, self._expr())
            if op == OP_GE: left = Ge(left, self._expr())

    def _eq(self):
        left = self._rel()
        while 1:
            op = self.source.peek()
            if op not in (OP_EQ, OP_NE):
                return left
            op = self.source.next()
            #print left, tok_name[op], "..."
            if op == OP_EQ: left = Eq(left, self._rel())
            if op == OP_NE: left = Ne(left, self._rel())

    def _and(self):
        left = self._eq()
        while 1:
            op = self.source.peek()
            if op != OP_ANDS:
                return left
            op = self.source.next()
            #print left, tok_name[op], "..."
            left = And(left, self._eq())

    def _or(self):
        left = self._and()
        while 1:
            op = self.source.peek()
            if op != OP_PIPES:
                return left
            op = self.source.next()
            #print left, tok_name[op], "..."
            left = Or(left, self._and())

class TokenSource:
    def __init__(self):
        self._token = None
        self._value = 0

    def source_cleanup(self):
        self._token = None
        self._value = 0

    def value(self): return self._value

    def peek(self):
        #print "peek:", tok_name[self._token]
        if self._token == None:
            self._token, self._value = self.read()
            #print "peek: (after)", tok_name[self._token]
        return self._token

    def next(self):
        tok = self._token
        self._token = None
        #if self._value:
        #    print "next: consumed ", tok_name[tok], self._token, self._value
        #else:
        #    print "next: consumed ", tok_name[tok], self._token
        return tok

    def ensure(self, tok):
        #print "ensure ", tok_name[tok], tok_name[self._token]
        if self.peek() != tok:
            if self._token in (OP_NAME, OP_STRING, OP_NUMBER, OP_UNKNOWN):
                self.Error("Expected %s, got %s `%s'" % (tok_name[tok], tok_name[self._token], self._value))
            self.Error("Expected %s, got %s" % (tok_name[tok], tok_name[self._token]))
        self.next()
    
class PreprocessorSource(TokenSource):
    def __init__(self):
        TokenSource.__init__(self)
        self.block = ''

    def source_cleanup(self):
        TokenSource.source_cleanup(self)
        self.block = ''

    def oper(self, op, *ops):
        i = 0
        while i < len(self.block) and i < len(op):
            #print "oper:", self.block[i], op[i]
            if self.block[i] != op[i]:
                self.block = self.block[i:]
                if i: return (ops[i-1], op[:i])
                return None
            i = i+1
        self.block = self.block[i:]
        if op[i:] == '': return (ops[-1], op)
        return (ops[i-1], op[:i])
    
    def read(self):
        while 1:
            self.block = self.block.lstrip()
            if self.block != '': break
            if not self.has_source():
                return (OP_END, 0)

            isstring, code = self.pop_block()
            if isstring: return (OP_STRING, code)
            self.block = code

        op = self.oper('(', OP_LPAREN)
        if op != None: return op
        op = self.oper(')', OP_RPAREN)
        if op != None: return op
        op = self.oper('<=', OP_LT, OP_LE)
        if op != None: return op
        op = self.oper('>=', OP_GT, OP_GE)
        if op != None: return op
        op = self.oper('!=', OP_NEG, OP_NE)
        if op != None: return op
        op = self.oper('==', OP_UNKNOWN, OP_EQ)
        if op != None: return op
        op = self.oper('||', OP_UNKNOWN, OP_PIPES)
        if op != None: return op
        op = self.oper('&&', OP_UNKNOWN, OP_ANDS)
        if op != None: return op

        if self.block[0].isdigit():
            i = 1
            while i < len(self.block) and self.block[i].isdigit(): i += 1
            name = self.block[:i]
            self.block = self.block[i:]
            return (OP_NUMBER, name)

        if self.block[0].isalnum() or self.block[0] == '_':
            i = 1
            while i < len(self.block) and (self.block[i].isalnum() or self.block[i] == '_'): i += 1
            name = self.block[:i]
            self.block = self.block[i:]
            return (OP_NAME, name)

        return (OP_UNKNOWN, self.block[0])

if __name__=="__main__":
    class ToolsSource(PreprocessorSource):
        def __init__(self, source):
            PreprocessorSource.__init__(self)
            self.source = source

        def has_source(self): return len(self.source)
        def pop_block(self):
            pair = self.source[0]
            self.source = self.source[1:]
            return pair
        def Error(self, msg): raise Exception(msg)

    class Macros:
        def __init__(self, values):
            self.values = values

        def value(self, macro):
            if macro.lower() not in self.values:
                return 0
            return self.values[macro.lower()]

        def defined(self, macro):
            if macro.lower() not in self.values:
                return 0
            return 1

    m = Macros({"__arch__":"ARMV4I", "__vs__":"3", "num": "6"})
    try:
        e = Expr().parse(ToolsSource([(0, '(__arch__ == '), (1, 'ARMV4I'), (0,' || 0) && defined(__vs__) && num == 6')]), m)
        print e, "=", e.value()
    except Exception, ex:
        print ex
    expr = And(And(Paren(Or(Eq(Macro('__arch__', None), String('ARMV4I')), Number(0))), Defined('__vs__', m)), Eq(Macro("num", m), Number(6)))
    print expr
