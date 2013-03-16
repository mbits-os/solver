# Builds vcproj file based on configuration.
# Usage: projector.py [config-file] [opt:output-name]
# If output-name is not given, value from Project.Name is taken
# and .vcproj extension is added
# Example: projector.py zephyr-vcproj.conf zephyr-ex.vcproj

from os import path
from IniReader import *
from xml.dom import minidom
import sys, uuid

c_ext = (
    ".c"
    )

cpp_ext = (
    ".cc", ".cpp", ".cxx"
    )

h_ext = (
    ".h", ".hh", ".hxx", ".hpp"
    )

class FileList:
    def __init__(self):
        self.inputs     = [] #list of all include files to mtime check
        self.cfiles     = []
        self.cppfiles   = []
        self.includes   = []
        self.datafiles  = []
        self.sec = None

    def read(self, predefs, fname, loc = None, ignoreIO = False):
        self.inputs = [fname]
        macros = Macros()
        for k in predefs.macros: macros.macros[k] = predefs.macros[k]
        macros.add_macro("__configfile__", "3", Location("<predefined>", 0))

        _ctx = FileContext(fname, macros, "filelist")
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

        _macros = Macros()
        self.sec = None
        for sec in _ctx.sections:
            if sec.lower() != "filelist": continue
            sec = _ctx.sections[sec]

            self.sec = Section(sec, sec.name)
            for idx in sec.index:
                fld = sec.items[idx]
                _fld = Field(fld, \
                             _macros.resolve(fld.name),\
                             _macros.resolve(fld.value))

                ext = path.splitext(_fld.name.lower())[1]
                if ext in c_ext:     self.cfiles.append(_fld.name.lower())
                elif ext in cpp_ext: self.cppfiles.append(_fld.name.lower())
                elif ext in h_ext:   self.includes.append(_fld.name.lower())
                else:                self.datafiles.append(_fld.name.lower())

                self.sec.append(_fld)
                pass
            pass

        del _macros
    def file_fresh(self, output_filename):
        try:
            to = os.path.getmtime(output_filename)
            for i in self.inputs:
                if os.path.getmtime(i) > to: return False
            return True #no update needed
        except:
            #some access was broken - huge chance,
            #it's because output desn't exsits yet
            return False

    def print_list(self, name, keys):
        print name
        for k in keys:
            print self.sec.items[k].name, self.sec.items[k].value
        print ""

if __name__=="__main__":
    m = Macros()
    m.add_macro("WIN32", "", Location("<command-line>", 0))
    l = FileList()
    l.read(m, "../core.files")
    l.print_list("C files", l.cfiles)
    l.print_list("C++ files", l.cppfiles)
    l.print_list("H files", l.includes)
    l.print_list("Other files", l.datafiles)
