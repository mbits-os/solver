from ConfigFile import \
     PrintOut, PrintMessage, PrintError, PrintWarning, PrintExc, \
     Location, Field, Section, FileContext, Macros

import sys, os, tempfile, shutil, getopt
from xml.parsers.expat import ParserCreate
from string import Formatter


kOpt = 0
kReq = 1

#list of well-known platforms, that will not deploy
#lower-case, please
vs_desktop_platforms = (
    "win32", "x64", "ia64"
    )

def PrintTemplate(out, templates, name, host, *args, **kwargs):
    for t in Formatter().parse(str(templates[name])):
        #print
        #print t
        #print
        out.write(t[0])
        if t[1] != None:
            try:
                if isinstance(t[1], (int, long)):
                    val = args[t[1]]
                else:
                    val = kwargs[t[1]]
            except:
                if isinstance(t[1], (int, long)):
                    val = host[t[1]]
                else:
                    val = getattr(host, t[1])

            conv = t[3]
            if conv == None: conv = 's'
            if conv == 's': val = str(val)
            elif conv == 'r': val = repr(val)
            elif conv == 'c':
                val(out, templates)
                val = ''
            out.write(val)

def is_true(value):
    prop = value.lower().strip()
    return prop == "1" or prop == "yes" or prop == "true"

class IniProgram:
    force = 0
    skip = 0
    input_filename = 0
    output_filename = 0
    inputs = [] #list of all include files to mtime check
    default_section_name = None

    def __init__(self):
        pass

    def other_updated(self): return False

    def set_output(self, fname):
        self.output_filename = fname

    def set_default_section(self, name):
        self.default_section_name = name

    def read(self, vstudio, mask, fname, loc = None, ignoreIO = False):
        self.input_filename = fname
        self.inputs = [fname]
        self.loc = Location(fname, 1)

        self.mask = mask
        self.vstudio = vstudio
        self.translation = { "ver": vstudio, "_ver": '_'+vstudio, "ver0": vstudio, "_ver0": '_'+vstudio }
        if len(vstudio) == 1:
            self.translation["ver0"] = '0' + vstudio; self.translation["_ver0"] = '_0' + vstudio

        macros = Macros()
        for k in self.predefs.macros: macros.macros[k] = self.predefs.macros[k]
        macros.add_macro("__configfile__", "3", Location("<predefined>", 0))
        macros.add_macro("__vs__", vstudio, Location("<predefined>", 0))
        _ctx = FileContext(fname, macros, self.default_section_name)
        try:
            _ctx.parse_file()
        except IOError, err:
            if ignoreIO:
                if loc: loc.Warn("Could not open %s" % fname)
                else: PrintWarning("<command line>", 0, "Could not open %s" % fname)
                raise
            elif loc: PrintExc(loc.fname, loc.lineno)
            else: PrintExc("<command line>", 0)
        except SystemExit, err:
            raise
        except:
            PrintExc(_ctx.fname, 1)

        for f in _ctx.imports:  self.inputs.append(f.fname)
        for f in _ctx.includes: self.inputs.append(f.fname)

        _ctx.handle_imports()

        self._macros = Macros()
        self.append_defines(_ctx)

        self.sections = {}
        for sec in _ctx.sections:
            sec = _ctx.sections[sec]
            _sec = Section(sec, sec.name)
            for idx in sec.index:
                fld = sec.items[idx]
                _fld = Field(fld, \
                             self._macros.resolve(fld.name),\
                             self._macros.resolve(fld.value))
                sec.append(_fld)
            self.sections[sec.name.lower()] = sec
        del self._macros

        self.read_config()

    def append_defines(self, _ctx): #overridable
        pass

    def append_define(self, name, value):
        self._macros.add_macro(name, value, Location(self.input_filename, 1))

    def get_section(self, name, opt):
        _name = str(name).lower()
        if _name in self.sections: return self.sections[_name]
        if opt == kOpt: return None
        self.loc.Error("Could not find section '%s'" % name)

    def get_item(self, sec, name, errmsg = None, opt = kReq):
        _name = name
        name = name.lower()
        if name in sec.items: return sec.items[name]
        if opt == kOpt: return None
        if type(errmsg) not in (str, unicode):
            errmsg = "%s:%s item missing" % (sec.name, _name)
        self.loc.Error(errmsg)

    def get_array(self, sec, name, errmsg = None):
        if type(errmsg) not in (str, unicode):
            errmsg = "%s:%s list missing" % (sec.name, name)

        return self.get_item(sec, name, errmsg).value.split(";")

    def get_optional_item(self, sec, name): return self.get_item(sec, name, opt=kOpt)

    def write(self):
        if self.output_filename == 0: self.update_filename()
        if self.output_filename == 0: return []

        orig_output_name = self.output_filename
        updated = []

        path, fname = os.path.split(orig_output_name)
        name, ext = fname.rsplit(".", 1)
        fname = os.path.join(path, self.mask.format(name=name, **self.translation) + "." + ext)
        self.output_filename = fname
        if self.write_one(): updated.append(fname)
        self.output_filename = 0
        return updated

    def same_content(self, left, right):
        try:
            l = open(left, 'rb')
            r = open(right, 'rb')
            while 1:
                lline = l.readline()
                rline = r.readline()
                if not lline:
                    if rline: return False
                    return True
                if lline != rline: return False
        except:
            return False

    def write_one(self):
        if not self.force:
            try:
                to = os.path.getmtime(self.output_filename)
                older = True
                for i in self.inputs:
                    if os.path.getmtime(i) > to: older = False; break
                if older: return False #no update needed
            except:
                #some access was broken - huge chance,
                #it's because output desn't exsits yet
                pass

        _loc = Location(self.input_filename, 1)
        _loc.Message("building %s" % os.path.basename(self.output_filename))

        tmp = tempfile.mkstemp('',\
                               os.path.basename(self.output_filename)+'.tmp-',\
                               os.path.dirname(self.output_filename))
        out = open(tmp[1], 'w')

        self.write_out(out)

        out.close()
        if os.path.exists(self.output_filename):
            if self.skip and self.same_content(self.output_filename, tmp[1]):
                _loc.Message("output not changed, skipping")
                os.close(tmp[0])
                os.remove(tmp[1])
                return False

            bak = tempfile.mkstemp('',\
                                   os.path.basename(self.output_filename)+'.back-',\
                                   os.path.dirname(self.output_filename))
            os.close(bak[0])
            shutil.copyfile(self.output_filename, bak[1])
        os.close(tmp[0])
        shutil.move(tmp[1], self.output_filename)
        return True

    def usage(self, argv, reason=0):
        if reason:
            PrintOut("%s\n" % reason)
        PrintOut(\
            "usage:\n    "+os.path.basename(argv[0])+""" [options] config

options:
    (h)elp
    (o)utput
    (f)orce
    (s)kip
    (d)ef    macro to be added to predefined list
    vs       [comma separated, allowed values: 8,9,10]
    mask     should contain {name} and one of {ver}, {_ver},
             {ver0} and {_ver0}                              [def=${name}${_0ver}]
             {ver} will be empty, if vs has only one version
             {_ver} will also be empty, but if the version is to be used,
             it will have underscore prepended to version
             {ver0} and {_ver0} are the same as {ver} and {ver0},
             but will create 08 and _08 instead of 8 and _8 (to be used,
             when vs also contains 10)
""")

    def main(self, kind, argv, loc = None, ignoreIO = False):
        try:
            opts, args = getopt.getopt(argv[1:], \
                                       "ho:fsd:", \
                                       ["help", "output=", "force", "skip",
                                        "D=", "def=", "mellow", "vs=", "mask="])
        except getopt.GetoptError, err:
            self.usage(argv, str(err))
            return 2

        mellow = 0
        vs = ["9"]
        vs2 = None
        mask2 = None
        self.predefs = Macros()
        for o, a in opts:
            if o in ("-h", "--help"):
                self.usage(argv)
                return 0
            elif o in ("-o", "--output"): self.set_output(a)
            elif o in ("-f", "--force"):  self.force = 1
            elif o in ("-s", "--skip"):   self.skip = 1
            elif o == "--mellow":         mellow = 1
            elif o == "--mask":           mask2 = a
            elif o == "--vs":
                if vs2 == None: vs2 = []
                vs2 += a.split(",")
            elif o in ("-d", "--D", "--def"):
                d = a.split("=", 1)
                value=''
                name = d[0].strip()
                d = d[1:]
                if len(d): value = d[0].strip()
                self.predefs.add_macro(name, value, Location("<command-line>", 0))

        if vs2 != None: vs = vs2

        #print self.predefs

        if len(args) == 0:
            self.usage(argv, "input missing")
            return 2
        elif len(args) > 1 and self.output_filename:
            self.usage(argv, "to many inputs")
            return 2

        if mask2 != None:
            mask = mask2
            mask2 = None
        else:
            if len(vs) == 1: mask = "{name}"
            else: mask = "{name}{_ver0}"

        re = []
        for arg in args:
            for studio in vs:
                try:
                    self.read(studio, mask, arg, loc, ignoreIO)
                    updated = self.write()
                    for u in updated: re.append(u)
                except IOError, err:
                    if not ignoreIO: raise

        if not mellow:
            for r in re:
                PrintOut(\
                    "%s: warning: %s '%s' has been updated and must be reloaded\n" %\
                    (self.input_filename, kind, r))
        if len(re) or self.other_updated(): return 1
        return 0

class VCProjInfo:
    class BailExpat(Exception):
        def __init__(self): pass

    def __init__(self):
        self.name = ""
        self.guid = 0
        
    def expat_se(self, name, attrs):
        assert name == "VisualStudioProject"
        self.guid = attrs["ProjectGUID"]
        self.name = attrs["Name"]
        raise VCProjInfo.BailExpat()

    def get(self, vcproj):
        try:
            f = open(vcproj)
        except:
            return (None, 0)

        p = ParserCreate()
        p.StartElementHandler = self.expat_se
        try:
            p.ParseFile(f)
        except VCProjInfo.BailExpat:
            pass
        except:
            return (None, 0)
        
        f.close()
        return (self.name, self.guid)

class CSProjInfo:
    class BailExpat(Exception):
        def __init__(self): pass

    def __init__(self):
        self.name = ""
        self.guid = 0
        self.text = ""
        
    def expat_se(self, name, attrs):
        self.text = ""

    def expat_ee(self, name):
        if name == "PropertyGroup":
            raise CSProjInfo.BailExpat()
        elif name == "AssemblyName":
            self.name = self.text
        elif name == "ProjectGuid":
            self.guid = self.text

    def expat_cd(self, text):
        self.text += text

    def get(self, csproj):
        try:
            f = open(csproj)
        except:
            return (None, 0)

        p = ParserCreate()
        p.StartElementHandler = self.expat_se
        p.EndElementHandler = self.expat_ee
        p.CharacterDataHandler = self.expat_cd
        try:
            p.ParseFile(f)
        except CSProjInfo.BailExpat:
            pass
        except:
            return (None, 0)
        
        f.close()
        return (self.name, self.guid)
