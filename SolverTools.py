
SLVR_UNKNOWN         = 0 #(VS Normal Text) [NO CONTENT]
SLVR_COMMENT         = 1 #Solver Comment [NO CONTENT]
SLVR_PREPROC         = 2 #Solver Preprocessor Directive [SPAN: W/HASH, CONTENT: PREPROC NAME]
SLVR_STRING          = 3 #Solver String [SPAN: QUOTS, CONTENT: INSIDE]
SLVR_SECTION_NAME    = 4 #Solver Section Title [SPAN: BRACKETS, CONTENT: NAME]
SLVR_ITEM_NAME       = 5 #Solver Item Name
SLVR_ITEM_VALUE      = 6 #Solver Item Value
SLVR_VARIABLE        = 7 #Solver Variable
SLVR_LINECONT        = 8 #Line continuation [NO CONTENT, FOR VS SHOULD BE CHANGED TO WHTEVER WAS BEFORE]
SLVR_LINECHUNK       = 9
SLVR_MACRONAME       = 10
SLVR_TEXT            = 11
SLVR_BROKEN_FIRST    = 12
SLVR_BROKEN_STRING   = SLVR_BROKEN_FIRST + SLVR_STRING
SLVR_BROKEN_SECTION  = SLVR_BROKEN_FIRST + SLVR_SECTION_NAME
SLVR_BROKEN_VARIABLE = SLVR_BROKEN_FIRST + SLVR_VARIABLE

SOLVER_TOKEN_NAME = {
    SLVR_UNKNOWN         : '<unknown>',
    SLVR_COMMENT         : 'comment',
    SLVR_PREPROC         : 'preprocessor directive',
    SLVR_STRING          : 'string',
    SLVR_SECTION_NAME    : 'section name',
    SLVR_ITEM_NAME       : 'item name',
    SLVR_ITEM_VALUE      : 'item value',
    SLVR_VARIABLE        : 'variable',
    SLVR_LINECONT        : 'line continuation',
    SLVR_LINECHUNK       : 'unparsed text',
    SLVR_MACRONAME       : 'macro name',
    SLVR_TEXT            : 'text',
    SLVR_BROKEN_STRING   : 'unfinished string',
    SLVR_BROKEN_SECTION  : 'unfinished section name',
    SLVR_BROKEN_VARIABLE : 'unfinshed variable'
    }

class Multiline:
    def __init__(self, _file, _lineno):
        self.tokens     = None
        self.line       = 0
        self.tokenstart = 0
        self.linelen    = 0
        self.cont_pos   = -1
        self.cont       = False
        self.file       = _file
        self.lineno     = _lineno
        self.lasttype   = SLVR_LINECHUNK

    def Next(self):
        if self.tokenstart >= self.linelen:
            self.line = self.file.readline()
            self.lineno += 1
            if not self.line: return False
            if not self.tokens: self.tokens = []

            self.tokenstart = 0
            self.linelen = len(self.line)
            self.cont_pos = self.line.rfind('\\')
            self.cont = self.cont_pos > -1 and self.line[self.cont_pos+1:].strip() == ''
            if self.cont: self.linelen = self.cont_pos
            while self.linelen and self.line[self.linelen-1] == '\n': self.linelen = self.linelen-1
            #print self.lineno, self.line[:self.linelen]
        return True

    def Push(self, size, toktype):
        #print self.lineno, self.tokenstart, size, toktype, "["+self.line[self.tokenstart:self.tokenstart+size]+"]"
        self.tokens.append((self.lineno, self.tokenstart, size, toktype, self.line[self.tokenstart:self.tokenstart+size]))
        self.tokenstart = self.tokenstart + size
        if toktype != SLVR_LINECONT: self.lasttype = toktype

    def ClearLine(self, stop):
        if stop > self.tokenstart:
            self.Push(stop - self.tokenstart, SLVR_LINECHUNK)

    def HandleContinuation(self):
        if self.lasttype == SLVR_COMMENT:
            self.Push(self.linelen - self.tokenstart, SLVR_COMMENT)
            return True
        elif self.lasttype == SLVR_BROKEN_STRING:
            quot = self.line.find('"', self.tokenstart)
            if quot > -1:
                self.Push(quot - self.tokenstart + 1, SLVR_STRING)
            else:
                self.Push(self.linelen, SLVR_BROKEN_STRING)
                return True
        return False

    def HandleString(self, string):
        comment = self.line.find('//', self.tokenstart, string)

        # LINE CHUNK:
        linechunk = string
        if comment > -1: linechunk = comment
        self.ClearLine(linechunk)

        if comment > -1:
            self.Push(self.linelen - comment, SLVR_COMMENT)
        else:
            quot = self.line.find('"', string+1)
            if quot < 0:
                self.Push(self.linelen - string, SLVR_BROKEN_STRING)
            else:
                self.Push(quot - string + 1, SLVR_STRING)
                return False
        return True

    def Parse(self):
        while self.Next():
            #------------------------------------------------------
            # CONTINUATION, the next line
            #------------------------------------------------------
            line_read = self.HandleContinuation()
            if not line_read:
                line_read = True
                #------------------------------------------------------
                # STRINGS:
                #------------------------------------------------------
                string = self.line.find('"', self.tokenstart)
                if string > -1:
                    line_read = self.HandleString(string)
                    if not line_read and self.line[self.tokenstart:].lstrip() == '':
                        line_read = True #actualy, it's read
                else:
                    #------------------------------------------------------
                    # COMMENTS:
                    #------------------------------------------------------
                    comment = self.line.find('//', self.tokenstart)
                    if comment > -1:
                        # LINE CHUNK:
                        self.ClearLine(comment)
                        self.Push(self.linelen - comment, SLVR_COMMENT)

                if line_read:
                    #------------------------------------------------------
                    # LINE CHUNK:
                    #------------------------------------------------------
                    self.ClearLine(self.linelen)

            if line_read:
                #------------------------------------------------------
                # CONTINUATION:
                #------------------------------------------------------
                if not self.cont: return self
                self.Push(1, SLVR_LINECONT)
        # end while

        if not self.line and not self.tokens: return False
        return self

class Grammar:
    def __init__(self):
        self.tokens    = []
        self.lineno    = 0
        self.file      = 0

    def PushEx(self, start, length, toktype, content):
        #print self.lineno, start, length, toktype, "["+content+"]"
        self.tokens.append((self.lineno, start, length, toktype, content))

    def Push(self, token): self.tokens.append(token)

    def Token(self, start, length, toktype, content):
        return (self.lineno, start, length, toktype, content)

    def ParseMultiline(self):
        tokens = Multiline(self.file, self.lineno)
        return tokens.Parse()

    def ParseDirectiveSimple(self, code, hash_pos, line_start, line_end, token):
        cmd_pos = code.find(token, hash_pos)
        if cmd_pos < 0: return (False, -1, 0)
        if code[hash_pos+1:cmd_pos].lstrip() != '': return (False, -1, 0)
        cmd_len = len(token)
        self.PushEx(hash_pos+line_start, cmd_pos+cmd_len-hash_pos+1, SLVR_PREPROC, token)
        return (True, cmd_pos, cmd_len)

    def ParseDirective(self, code, hash_pos, line_start, line_end, token):
        found, cmd_pos, cmd_len = self.ParseDirectiveSimple(code, hash_pos, line_start, line_end, token)
        if not found: return False
        rest = code[cmd_pos+cmd_len:]
        if rest.lstrip() != '':
            self.PushEx(cmd_pos+cmd_len+line_start, line_end-cmd_pos+cmd_len+1, SLVR_LINECHUNK, rest)
        return True

    def ParseDirectiveMValue(self, code, hash_pos, line_start, line_end, token):
        found, cmd_pos, cmd_len = self.ParseDirectiveSimple(code, hash_pos, line_start, line_end, token)
        if not found: return False
        rest = code[cmd_pos+cmd_len:]
        tok_pos = cmd_pos+cmd_len+len(rest) - len(rest.lstrip())
        ws_space = code.find(' ', tok_pos)
        ws_tab = code.find('\t', tok_pos)
        if ws_space < 0 or (ws_tab > -1 and ws_tab < ws_space): ws_space = ws_tab
        if ws_space > -1:
            self.PushEx(tok_pos + line_start, ws_space - tok_pos + 1, SLVR_MACRONAME, code[tok_pos:ws_space])
            self.PushEx(ws_space + line_start, line_end - ws_space+1, SLVR_TEXT, code[ws_space:].strip())
        else:
            self.PushEx(tok_pos + line_start, line_end - tok_pos + 1, SLVR_MACRONAME, code[tok_pos:])
            self.PushEx(line_end + line_start, 0, SLVR_TEXT, "")
        return True

    def ParseDirectiveMName(self, code, hash_pos, line_start, line_end, token):
        found, cmd_pos, cmd_len = self.ParseDirectiveSimple(code, hash_pos, line_start, line_end, token)
        if not found: return False
        rest = code[cmd_pos+cmd_len:]
        tok_pos = cmd_pos+cmd_len+len(rest) - len(rest.lstrip())
        ws_space = code.find(' ', tok_pos)
        ws_tab = code.find('\t', tok_pos)
        if ws_space < 0 or (ws_tab > -1 and ws_tab < ws_space): ws_space = ws_tab
        if ws_space > -1:
            self.PushEx(tok_pos + line_start, ws_space - tok_pos + 1, SLVR_MACRONAME, code[tok_pos:ws_space])
            ws = code[ws_space:]
            if ws.lstrip() != '': #here a LINECHUNK can be returned...
                self.PushEx(ws_space + line_start, line_end - ws_space+1, SLVR_LINECHUNK, code[ws_space:])
        else:
            self.PushEx(tok_pos + line_start, line_end - tok_pos + 1, SLVR_MACRONAME, code[tok_pos:])
        return True

    def Parse(self, _in):
        self.tokens = []
        self.linestart = 0
        self.lineno = 0
        self.file = _in
        while True:
            code = self.ParseMultiline()
            if not code: break

            #lastline = None
            copy = False
            broken_section = False
            broken_item = False
            value_copy = False
  
            variables_in_name = []
            variables_in_value = []

            if not len(code.tokens):
                #print "no tokens..."
                self.lineno += 1

            for token in code.tokens:
                #if lastline == None:
                #    lastline = token[0]
                #    print "\n-----  ", lastline, "  ------------------------------------\n"

                #print token[0], token[1], token[2], token[3], "("+token[4]+")"

                self.lineno = token[0]

                if token[3] == SLVR_LINECONT:
                    self.PushEx(token[1], token[2], token[3], token[4])
                    continue

                if token[3] == SLVR_LINECHUNK:
                    code = token[4]
                    #------------------------------------------------------
                    # CONTINUED ACTIONS:
                    #------------------------------------------------------
                    #print copy, broken_section, broken_item, value_copy, code
                    #******* COPY REST OF LINE *************
                    if copy:
                        self.PushEx(token[1], token[2], token[3], code)
                        continue
                    #******* SLVR_BROKEN_SECTION *************
                    elif broken_section:
                        right = code.find(']', bracket)
                        if right < 0:
                            self.PushEx(token[1], token[2], SLVR_BROKEN_SECTION, code.strip())
                        else:
                            self.PushEx(token[1], right+1, SLVR_SECTION_NAME, code[:right].strip())
                            broken_section = False
                            copy = True
                        continue
                    #******* BROKEN ITEM NAME *************
                    elif broken_item:
                        eq = code.find('=')
                        if eq < 0:
                            self.PushEx(token[1], token[2], SLVR_ITEM_NAME, code.strip())
                            #...search for variables...
                            continue
                        else:
                            string = code[:eq]
                            oth = string.lstrip()
                            left = len(string) - len(oth)
                            oth = string.rstrip()
                            right = len(string) - len(oth)
                            self.PushEx(token[1]+left, eq-(left+right), SLVR_ITEM_NAME, code[:eq].strip())

                            eq = eq + 1
                            string = code[eq:]
                            oth = string.lstrip()
                            left = len(string) - len(oth)
                            oth = string.rstrip()
                            right = len(string) - len(oth)
                            self.PushEx(token[1]+eq+left, token[2]-eq-(left+right), SLVR_ITEM_VALUE, code[eq:].strip())
                            broken_item = False
                            value_copy = True
                            continue
                    #******* BROKEN ITEM VALUE *************
                    elif value_copy:
                        oth = code.lstrip()
                        left = len(code) - len(oth)
                        oth = code.rstrip()
                        right = len(code) - len(oth)
                        self.PushEx(token[1]+left, token[2]-(left+right), SLVR_ITEM_VALUE, code.strip())
                        continue

                    #------------------------------------------------------
                    # PREPROCESSING DIRECTIVES:
                    #------------------------------------------------------
                    hash_pos = code.find('#')
                    #print "?>", code
                    if hash_pos > -1 and code[:hash_pos].lstrip() == '':
                        if code[hash_pos+1:].lstrip() == '': #null directive
                            self.PushEx(hash_pos+token[1], len(code) - hash_pos + 8, SLVR_PREPROC, "")
                        elif self.ParseDirective      (code, hash_pos, token[1], token[2], "include"): pass
                        elif self.ParseDirective      (code, hash_pos, token[1], token[2], "import"):  pass
                        elif self.ParseDirective      (code, hash_pos, token[1], token[2], "error"):   pass
                        elif self.ParseDirectiveMValue(code, hash_pos, token[1], token[2], "define"):  pass
                        elif self.ParseDirectiveMName (code, hash_pos, token[1], token[2], "undef"):   pass
                        elif self.ParseDirectiveMName (code, hash_pos, token[1], token[2], "ifdef"):   pass
                        elif self.ParseDirectiveMName (code, hash_pos, token[1], token[2], "ifndef"):  pass
                        elif self.ParseDirective      (code, hash_pos, token[1], token[2], "if"):      pass
                        elif self.ParseDirective      (code, hash_pos, token[1], token[2], "elif"):    pass
                        elif self.ParseDirective      (code, hash_pos, token[1], token[2], "else"):    pass
                        elif self.ParseDirective      (code, hash_pos, token[1], token[2], "endif"):   pass
                        copy = True
                        continue
                    else:
                        #------------------------------------------------------
                        # SECTION TITLE:
                        #------------------------------------------------------
                        bracket = code.find('[')
                        if bracket > -1 and code[:bracket].lstrip() == '':
                            right = code.find(']', bracket)
                            if right < 0:
                                self.PushEx(bracket+token[1], token[2]-bracket, SLVR_BROKEN_SECTION, code[bracket+1:token[2]].lstrip())
                                broken_section = True
                            else:
                                self.PushEx(bracket+token[1], right-bracket+1, SLVR_SECTION_NAME, code[bracket+1:right].strip())
                                copy = True
                            continue
                        else:
                            #------------------------------------------------------
                            # NAME AND VALUE:
                            #------------------------------------------------------
                            eq = code.find('=')
                            if eq < 0:
                                self.PushEx(token[1], token[2], SLVR_ITEM_NAME, code[:token[2]].lstrip())
                                #...search for variables...
                                broken_item = True
                                continue
                            else:
                                string = code[:eq]
                                oth = string.lstrip()
                                left = len(string) - len(oth)
                                oth = string.rstrip()
                                right = len(string) - len(oth)
                                self.PushEx(token[1]+left, eq-(left+right), SLVR_ITEM_NAME, code[:eq].strip())

                                eq = eq + 1
                                string = code[eq:]
                                oth = string.lstrip()
                                left = len(string) - len(oth)
                                oth = string.rstrip()
                                right = len(string) - len(oth)
                                self.PushEx(token[1]+eq+left, token[2]-eq-(left+right), SLVR_ITEM_VALUE, code[eq:].strip())

                                value_copy = True
                                continue
                            
                    self.PushEx(token[1], token[2], token[3], token[4])
                    pass
                else:
                    self.PushEx(token[1], token[2], token[3], token[4])

        return self.Postprocess()

    def Postprocess(self):
        ret = self.tokens
        self.tokens = []
        self.file = 0
        return ret
