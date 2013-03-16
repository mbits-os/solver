import sys
import os
from os import path
from SolverTools import *
from Expression import *
import glob
from traceback import extract_tb

#########################################################################################################
#  ConfigFile.RunGrammar

class RunGrammar(Grammar):
    "RunGrammar: implementation of SolverTools.Grammar.Postprocess for scripts"

    def Postprocess(self):
        ret = []
        prev_token_type = SLVR_UNKNOWN
        prev_line = 0
        prev_start = 0
        prev_len = 0
        value = ''
        seen_cont = False
        
        for token in self.tokens:
            if prev_line == 0: prev_line = token[0]

            if token[3] == SLVR_COMMENT: continue
            elif token[3] == SLVR_LINECONT: seen_cont = True; continue
            
            if seen_cont:
                cur_line = prev_line
                seen_cont = False
            else:
                cur_line = token[0]

            if prev_line != cur_line:
                if prev_token_type != SLVR_UNKNOWN:
                    if prev_token_type == SLVR_STRING:
                        value = value[1:-1]
                    ret.append((prev_line, prev_start, prev_len, prev_token_type, value))
                prev_token_type = SLVR_UNKNOWN
                prev_line = cur_line
                value = ''
            if prev_token_type == token[3]:
                value = value + token[4]
                prev_start = 0
                prev_len = 0
            elif prev_token_type == token[3] + SLVR_BROKEN_FIRST:
                prev_token_type = token[3]
                value = value + token[4]
                prev_start = 0
                prev_len = 0
            else:
                if prev_token_type != SLVR_UNKNOWN:
                    if prev_token_type == SLVR_STRING:
                        value = value[1:-1]
                    ret.append((prev_line, prev_start, prev_len, prev_token_type, value))
                prev_start = token[1]
                prev_len = token[2]
                prev_token_type = token[3]
                value = token[4]
            pass
        if prev_token_type != SLVR_UNKNOWN:
            if prev_token_type == SLVR_STRING:
                value = value[1:-1]
            ret.append((prev_line, prev_start, prev_len, prev_token_type, value))

        return ret

#########################################################################################################
#  Output messages compatible with Visual Studio
#

def PrintOut(string): sys.stdout.write(string)
def PrintMessage(fname, line, kind, message, indent):
    _indent = ''
    if indent: _indent = "\t"*indent
    PrintOut("%s%s(%s): %s%s\n" % (_indent, fname, line, kind, message))
def PrintError(fname, line, message, indent = 0):   PrintMessage(fname, line, "error: ", message, indent);  sys.exit(2)
def PrintWarning(fname, line, message, indent = 0): PrintMessage(fname, line, "warning: ", message, indent)
def PrintExc(fname, line):
    msg, trace = sys.exc_info()[1:]
    frames = extract_tb(trace)
    out = []
    for tb_file, tb_line, tb_fn, tb_text in frames:
        m = "\n    %s(%s): see in %s" % (tb_file, tb_line, tb_fn)
        if tb_text is not None:
            m = m + "\n        %s" % tb_text
        out.append(m)
    PrintError(fname, line, "%s%s\n" % (msg, "".join(out)))

#########################################################################################################
#  Generic field info

kAtomic = 0
kMulti = 1
kMergeable = 2
kFilelist = 3

fields = {
    "project": {
        "configs": kMergeable,
        "platforms": kMergeable,
        "tools": kFilelist
        },
    "props": kMergeable,
    "files": kMergeable,
    "solution": {
        "configs": kMergeable,
        "platforms": kMergeable
        },
    "projects": kMulti,
    "files": kFilelist,
    "props": kFilelist
    }

def field_kind(section, item):
    section = section.lower()
    item = item.lower()
    if section in fields:
        sec = fields[section]
        if type(sec) == int:
            return sec
        if item in sec:
            return sec[item]
    return kAtomic

def rewrite_field(section, item, value, loc):
    if field_kind(section, item) == kAtomic:
        return value
    v = []
    if field_kind(section, item) == kFilelist:
        #print "rewrite:", loc.path(), value
        for i in value.split(";"):
            if i.strip() == "":
                v.append("")
                continue

            elem = i.split("[", 1)
            for p in loc.filelist(elem[0].strip()):
                if len(elem)>1: p += "["+elem[1]
                #print "   ", p
                v.append(p)
        #print ";".join(v)
    else:
        for i in value.split(";"):
            v.append(i.strip())
    return ";".join(v)

def merge_fields(section, field, v1, v2, fname1, fname2):
    fk = field_kind(section, field)
    if fk < kMergeable:
        return None
    v1 = v1.split(";")
    v2 = v2.split(";")
    for v in v2:
        if v not in v1:
            v1.append(v)
    return ";".join(v1)



#########################################################################################################
#  ConfigFile.Location

class Location:
    """Location

Base class for all file position aware classes. Allows to
1)  get list of files, relative to position of its source
    and with respect to multifile declaration
2)  get the absolute directory name of the file this location
    refers to
3) "rise" errors and flag warnings w/out any clutter connected to
    filename/line number
"""
    def __init__(self, fname, lineno):
        self.fname = fname
        self.lineno = lineno

    def __str__(self): return "['%s', %s]" % (self.fname, self.lineno)
    def __repr__(self): return "<%s: '%s', %s>" % (self.__class__.__name__, self.fname, self.lineno)

    def path(self):
        "returns absolute directory, in which this Location file resides"
        x = path.abspath(self.fname)
        if os.path.isdir(x): return x
        return os.path.dirname(x)

    def relpath(self, path):
        path = os.path.abspath(path).replace('\\', '/').split('/')
        here = self.path().replace('\\', '/').split('/')
        mlen = len(path)
        if mlen > len(here): mlen = len(here)
        ptr = 0
        while ptr < mlen:
            if path[ptr].lower() != here[ptr].lower(): break
            ptr += 1

        out = []
        for i in range(ptr, len(here)): out.append("..")
        out += path[ptr:]
        path = os.path.join(*out)
        if path != os.path.abspath(path) and len(path) and path[0] != '.':
            path = os.path.join(".", path)
        return path

    def filelist(self, mask):
        root = self.path()
        ret = glob.glob(path.join(root, mask))
        for i in range(0, len(ret)):
            ret[i] = path.abspath(ret[i])
        if not len(ret) and mask.find("*") < 0 and mask.find("?") < 0: ret = [ mask ]
        return ret

    def Message(self, msg, indent = 0): PrintMessage(self.fname, self.lineno, "", msg, indent)
    def Error(self, msg, indent = 0):   PrintError  (self.fname, self.lineno,     msg, indent)
    def Warn(self, msg, indent = 0):    PrintWarning(self.fname, self.lineno,     msg, indent)
    def PrintExc(self, msg):            PrintExc    (self.fname, self.lineno)

#########################################################################################################
#  ConfigFile.Field

class Field(Location):
    def __init__(self, loc, name, value):
        Location.__init__(self, loc.fname, loc.lineno)
        self.name = name
        self.value = value

    def __str__(self): return "(['%s', %s], '%s', '%s')" % (self.fname, self.lineno, self.name, self.value)
    def __repr__(self): return "<%s: '%s', %s, '%s', '%s'>" % (self.__class__.__name__, self.fname, self.lineno, self.name, self.value)

    def merge(self, section, other):
        value = merge_fields(section, self.name, self.value, other.value, self.path(), other.path())
        if value == None:
            other.Warn("Ignoring non-mergable item")
            self.Message("See original instantion", 1)
            return
        self.value = value

    def print_field(self, flen):
        print "{0:{1}} = {2} // {3} {4}".format(self.name, flen, self.value, os.path.basename(self.fname), self.lineno)

#########################################################################################################
#  ConfigFile.Section

class Section(Location):
    def __init__(self, loc, name):
        Location.__init__(self, loc.fname, loc.lineno)
        self.name = name
        self.items = {}
        self.index = []

    def __str__(self): return "(['%s', %s], '%s', %s)" % (self.fname, self.lineno, self.name, str(self.items))
    def __repr__(self): return "<%s: '%s', %s, '%s', %s>" % (self.__class__.__name__, self.fname, self.lineno, self.name, str(self.items))

    def append(self, field):
        name = field.name.lower()
        if not name in self.index:
            self.index.append(name)
        self.items[name] = field

    def merge(self, other, merging = True):
        for item in other.items:
            it = other.items[item]
            if item not in self.items: self.append(it)
            elif merging: self.items[item].merge(self.name, it)
            else:
                it.Warn("Ignoring repeated item")
                self.items[item].Message("See original definition")

    def print_sec(self):
        #print "\n//%s %s\n[%s]" % (self.fname, self.lineno, self.name)
        print "\n\n[%s]" % (self.name)
        ilen = 0
        for item in self.index:
            if ilen < len(item): ilen = len(item)
        for item in self.index:
            self.items[item].print_field(ilen)

#########################################################################################################
#  ConfigFile.Macros

class Macros:
    def __init__(self):
        self.macros = {}

    def __str__(self): return str(self.macros)
    def __repr__(self): return "<%s: %s>" % (self.__class__.__name__, str(self))

    def add_macro(self, name, value, loc):
        if name.lower() in self.macros:
            prev = self.macros[name.lower()]
            loc.Warn("Redefining existing macro %s" % name)
            Location(prev[1], prev[2]).Message("See previous definition", 1)
        value = self.resolve(value)
        self.macros[name.lower()] = (value, loc.fname, loc.lineno)
        #print "add_macro:", name, value#, self

    def remove_macro(self, name, loc):
        if name.lower() in self.macros: del self.macros[name.lower()]
        else: loc.Warn("Undefining nonexisting macro %s" % name)
        #print "remove_macro:", name#, self.macros

    def resolve(self, value):
        pos = 0
        enter = False
        #v = value
        while pos <= len(value):
            left = value.find("$(", pos)
            if left < 0: break
            right = value.find(")", left+1)
            if right < 0: break
            key = value[left+2:right].lower()
            if key not in self.macros:
                pos = left + 2
                continue
            val = self.macros[key][0]
            value = value[:left] + val + value[right+1:]
            pos = left + len(val)
        #if v != value:
        #    print v, value
        return value

    # preproc expression evaluation
    def value(self, name):
        if name.lower() in self.macros: return self.macros[name.lower()][0]
        return 0

    def defined(self, name):
        if name.lower() in self.macros: return 1
        return 0

#########################################################################################################
#  ConfigFile.FileContext

class FileContext(PreprocessorSource):
    def __init__(self, fname, macros, default_session):
        self.fname    = fname
        self.macros   = macros
        self.includes = []
        self.imports  = []
        self.sections = {}
        self.current  = None
        self.loc      = Location(fname, 1) #updated by 'program' inside parse_file
        self.depth    = 1
        self.if_stack = []
        self.default_session = default_session

    #================================================================================
    # ~~~~ Location mimicking ~~~~
    def Error(self, msg): self.ErrorEx(self.loc, msg)
    def Warn(self, msg):  self.WarnEx(self.loc, msg)

    def ErrorEx(self, loc, msg):
        loc.Error(msg)
        sys.exit(2)

    def WarnEx(self, loc, msg):
        loc.Error(msg)
        return None
    # ~~~~ /Location mimicking ~~~

    #================================================================================
    # ~~~~ PreprocessorSource ~~~~
    def has_source(self):
        return self.tok_id < len(self.line)
    def pop_block(self):
        tok = self.Token(SLVR_LINECHUNK, SLVR_STRING)
        #print "(%r, %r)" % (tok[0] != SLVR_LINECHUNK, tok[1])
        return (tok[0] != SLVR_LINECHUNK, tok[1])
    #`def Error' comes from Location-like interface elsewhere in FileContext
    # ~~~~ /PreprocessorSource ~~~~

    #================================================================================
    # ~~~~ Tokenizer ~~~~~
    def TokenEx(self, opt, *args):
        if not len(args):
            if self.tok_id < len(self.line) and not opt:
                return self.Error("Expected newline, got %s" % self.TokenName(self.line[self.tok_id][0]))
            return None
        if self.tok_id >= len(self.line):
            if opt: return None
            return self.Error("Expected %s, got newline" % self.TokenName(args[0]))

        if self.line[self.tok_id][0] not in args:
            if opt: return None
            self.Error("Expected %s, got %s" % (\
                self.TokenName(args[0]), \
                self.TokenName(self.line[self.tok_id][0])))

        tid = self.tok_id
        self.tok_id = self.tok_id + 1
        return self.line[tid]

    def TokenName(self, tokid): return SOLVER_TOKEN_NAME[tokid]
    def Token(self, *args): return self.TokenEx(False, *args)
    def TokenOpt(self, *args): return self.TokenEx(True, *args)
    # ~~~~ /Tokenizer ~~~~~

    #================================================================================
    # ~~~~ Parser ~~~~~
    def parse_file(self, loc = None):
        f = open(self.loc.fname, 'rU') #on exception, pass it to IniReader

        tokens = RunGrammar().Parse(f)
        program = {}
        for token in tokens:
            if token[0] in program.keys():
                program[token[0]].append((token[3], token[4]))
            else:
                program[token[0]] = [(token[3], token[4])]

        k = program.keys()
        k.sort()

        self.current = None

        for lineno in k:
            self.loc.lineno = lineno
            self.line = program[lineno]
            self.tok_id = 0

            if self.preproc_disabled_block(): continue

            tok = self.Token(SLVR_SECTION_NAME, SLVR_ITEM_NAME, SLVR_PREPROC)
            if   tok[0] == SLVR_PREPROC:      self.handle_preproc(tok[1])
            elif tok[0] == SLVR_SECTION_NAME: self.handle_section(tok[1])
            elif tok[0] == SLVR_ITEM_NAME:    self.handle_item(tok[1])

        # cleanup:
        self.preproc_ensure_closed()
        self.section_ensure_saved()

    #--------------------------------------------------------------------------------
    # FILE CONTENTS
    
    def handle_section(self, name):
        self.section_ensure_saved()
        self.current = Section(self.loc, name)
        
    def handle_item(self, name):
        if self.current == None:
            if self.default_session == None:
                self.loc.Warn("Ignoring item outside of any sections")
                return
            self.handle_section(self.default_session)

        value = self.TokenOpt(SLVR_ITEM_VALUE)
        if value == None: value = ""
        else: value = value[1]
        name = self.macros.resolve(name)
        value = self.macros.resolve(value)
        self.current.append(Field(self.loc, name, rewrite_field(self.current.name, name, value, self.loc)))

    def section_ensure_saved(self):
        if self.current != None:
            self.sections[self.current.name.lower()] = self.current

    #--------------------------------------------------------------------------------
    # PREPROCESOR

    def preproc_disabled_block(self):
        disabled = False
        if len(self.if_stack): disabled = not self.if_stack[-1][2]
        if disabled:
            tok = self.TokenOpt(SLVR_PREPROC)
            if tok and tok[1] in ("if", "ifdef", "ifndef", "elif", "else", "endif"):
                #print self.fname+"("+str(lineno)+"):", self.line
                self.handle_preproc(tok[1], False)
            return True
        #print self.fname+"("+str(lineno)+"):", self.line
        return False

    def preproc_ensure_closed(self):
        if not len(self.if_stack): return
        command, loc, exec_now, wait_for, enabled = self.if_stack[-1]
        loc.Error("Unexpected `#%s' without matching `#endif'" % command)

    def handle_preproc(self, command, enabled = True):
        if   command == "include": self.preproc_subcontext(True)
        elif command == "import":  self.preproc_subcontext(False)
        elif command == "define":  self.preproc_defundef(True)
        elif command == "undef":   self.preproc_defundef(False)
        elif command == "if":      self.preproc_if(command, True,  False, enabled)
        elif command == "ifdef":   self.preproc_if(command, False, False, enabled)
        elif command == "ifndef":  self.preproc_if(command, False, True,  enabled)
        elif command == "elif":    self.preproc_elif(enabled)
        elif command == "else":    self.preproc_else()
        elif command == "endif":   self.preproc_endif()
        elif command == "error":   self.preproc_error()

    def preproc_subcontext(self, include):
        name = self.Token(SLVR_STRING)[1]
        filelist = self.loc.filelist(name)
        self.Token()
        for fname in filelist:
            subctx = FileContext(Location(os.getcwd(),1).relpath(fname), self.macros)
            subctx.parse_file(self.loc)

            #this will move all the includes and imports all the way up to toplevel
            includes = subctx.includes
            imports = subctx.imports
            subctx.includes = []
            subctx.imports = []

            if include: self.includes.append(subctx)
            else: self.imports.append(subctx)

            self.includes += includes
            self.imports += imports

    def preproc_defundef(self, define):
        name = self.Token(SLVR_MACRONAME)
        value = None
        if define: value = self.TokenOpt(SLVR_TEXT)
        self.Token()
        if define:
            if value == None: value = (SLVR_TEXT, "")
            self.macros.add_macro(name[1], value[1], self.loc)
        else:
            self.macros.remove_macro(name[1], self.loc)

    def preproc_if(self, command, normal, negated, enabled):
        exec_now = False
        if enabled:
            if normal:
                exec_now = Expr().parse(self, self.macros).value()
            else:
                name = self.Token(SLVR_MACRONAME)
                self.Token()
                exec_now = self.macros.defined(name[1])
                if negated: exec_now = not exec_now

        self.if_stack.append([command, self.loc, exec_now, enabled, ["endif", "else"]])
        if enabled and not exec_now: self.if_stack[-1][4].append("elif")
        #command, loc, exec_now, enabled, wait_for = self.if_stack[-1]
        #print "IF(%r, %r, %r, %r, %r)" % (command, loc, exec_now, enabled, wait_for)

    def preproc_elif(self, enabled):
        if not len(self.if_stack): self.Error("Unexpected `#elif' without matching `#if'")
        command, loc, exec_now, enabled, wait_for = self.if_stack[-1]
        #print "ELIF(%r, %r, %r, %r, %r)" % (command, loc, exec_now, enabled, wait_for)
        if not enabled: return
        if "elif" not in wait_for:
            self.if_stack[-1] = [command, loc, not exec_now, not enabled, ["else", "endif"]]
            return
        if exec_now: return #this means we already executed at least once
        exec_now = Expr().parse(self, self.macros).value()
        self.if_stack[-1] = [command, loc, exec_now, enabled, ["else", "endif"]]

    def preproc_else(self):
        self.Token()
        if not len(self.if_stack): self.Error("Unexpected `#else' without matching `#if'")
        command, loc, exec_now, enabled, wait_for = self.if_stack[-1]
        #print "ELSE(%r, %r, %r, %r, %r)" % (command, loc, exec_now, enabled, wait_for)
        if "else" not in wait_for: self.Error("Unexpected `#else' without matching `#if'")
        if not enabled: return
        self.if_stack[-1] = [command, loc, not exec_now, enabled, ["endif"]]

    def preproc_endif(self):
        self.Token()
        if not len(self.if_stack): self.Error("Unexpected `#endif' without matching `#if'")
        #command, loc, exec_now, enabled, wait_for = self.if_stack[-1]
        #print "ENDIF(%r, %r, %r, %r, %r)" % (command, loc, exec_now, enabled, wait_for)
        self.if_stack.pop()

    def preproc_error(self):
        msg = ''
        while self.has_source():
            isstring, text = self.pop_block()
            if isstring: msg += '"%s"' % text
            else: msg += text
        self.Error("#error" + msg)

    # ~~~~ /Parser ~~~~~

    def handle_import(self, im, merging):
        for sec in im.sections:
            if sec in self.sections:
                self.sections[sec].merge(im.sections[sec], merging)
            else:
                self.sections[sec] = im.sections[sec]

    def handle_imports(self):
        for im in self.imports:
            self.handle_import(im, True)

        for inc in self.includes:
            self.handle_import(inc, False)

        self.imports = []
        self.includes = []

    def print_ctx(self):
        for sec in self.sections: self.sections[sec].print_sec()
