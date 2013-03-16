# for calling run the script w/out any arguments or with -h/--help

from os import system, path
from IniReader import *
import uuid
import sys
import projector

vs_templates = {
    #__main__
    "__main__":      """Microsoft Visual Studio Solution File, Format Version {slnver}
# Visual Studio {vsver}
{print_declarations!c}Global
	GlobalSection(SolutionConfigurationPlatforms) = preSolution
{print_configurations!c}	EndGlobalSection
	GlobalSection(ProjectConfigurationPlatforms) = postSolution
{print_connections!c}	EndGlobalSection
	GlobalSection(SolutionProperties) = preSolution
		HideSolutionNode = FALSE
	EndGlobalSection
{print_nested_projects!c}EndGlobal
""",
    # STRUCTURE TEMPLATES
    "declaration":    """Project("{print_projtype!c}") = "{title}", "{print_projpath!c}", "{guid}"
{print_dependency_block!c}EndProject
""",
    "dependencies":   """	ProjectSection(ProjectDependencies) = postProject
{print_dependencies!c}	EndProjectSection
""",
    "dependency":     "\t\t{guid} = {guid}\n",
    # SOLUTION CONFIGURATIONS:
    "configuration":  "\t\t{config}|{platform} = {config}|{platform}\n",
    "connection":     "\t\t{guid}.{config}|{platform}.{verb} = {vconfig}|{vplatform}\n",
    # NESTED PROJECTS
    "nested_frame":   """	GlobalSection(NestedProjects) = preSolution
{print_nested_list!c}	EndGlobalSection
""",
    "nested_project": "\t\t{child} = {parent}\n"
    }

vs_verb = ("ActiveCfg", "Build.0", "Deploy.0")
vs_slnver={"8":"9.00", "9":"10.00", "10":"11.00"}
vs_vsver={"8":"2005", "9":"2008", "10":"2010"}

def find_sln_guid(output_filename, project_class, name, project):
    try:
        f = open(output_filename, 'r')
    except:
        return 0

    mask = 'Project("%s") = "%s", "%s", "' % (project_class, name, project)
    l_mask = len(mask)
    #print "find_sln_guid(%r, %r, %r, %r)" % (output_filename, project_class, name, project)
    #print "find_sln_guid", output_filename, "["+mask+"]", l_mask
    while 1:
        line = f.readline()
        if not line: break
        if line[:6] == "Global": break
        #print line[:-1]
        if line[:l_mask] != mask: continue
        f.close()
        return line[l_mask:].split('"')[0]
    f.close()
    return 0

class ProjectInfo(Location):
    #ProjectInfo(fname, line, name, mask, translations, expand[, proj, conf, folder, *deps])
    def __init__(self, fname, line, name, mask, translations, expand, *argv):

        Location.__init__(self, fname, line)
        self.name   = name
        argc = len(argv)

        self.outproj= ""
        self.conf   = ""
        self.folder = ""

        if argc > 0: self.outproj = argv[0]
        if argc > 1: self.conf    = argv[1]
        if argc > 2: self.folder  = argv[2]
        self.dependencies = argv[3:]

        if argc > 0 and expand:
            path, fname = os.path.split(self.outproj)
            name, ext = fname.rsplit(".", 1)
            self.outproj = os.path.join(path, mask.format(name=name, **translations) + "." + ext)
            self.outproj = os.path.abspath(os.path.join(self.path(), self.outproj))

        self.guid   = 0
        self.title  = 0
        self.ignore = False

    def update_dependencies(self, others):
        deps = []
        for dep in self.dependencies:
            if dep == "": continue
            clsid = others.get(dep, 0)
            if clsid == 0: self.Error("could not resolve '%s' dependency" % dep)
            if clsid == "{00000000-0000-0000-0000-000000000000}":
                self.Warn("%s dependency will be dropped" % dep)
                clsid = 0
            if clsid: deps.append(clsid)
        self.dependencies = deps

    def configure(self, force, skip, predefs, vs): return 0

    def update_folder(self, others):
        if not self.folder: return
        for fld in others:
            if fld.name == self.folder:
                self.folder = fld.guid
                return
        self.folder = ""

    def find_sln_guid(self, output_filename, collapse=True):
        if collapse: guid = find_sln_guid(output_filename, self.project_class(), self.title, \
                                          Location(output_filename, 1).relpath(self.outproj))
        else: guid = find_sln_guid(output_filename, self.project_class(), self.title, self.outproj)
        if guid == 0:
            self.guid = ("{%s}" % uuid.uuid1()).upper()
            self.Warn("inventing Project.GUID %s for project '%s'" % (self.guid, self.name))
        else:
            self.guid = guid.upper()
            self.Message("info: reusing Project.GUID %s for project '%s'" %\
                         (self.guid, self.name))

    #=============================================
    # TEMPLATE COMMANDS
    def print_projtype(self, out, templates): out.write(self.project_class())
    def print_projpath(self, out, templates):
        # solution should have set the output location
        # before calling template with this method
        out.write(self.outloc.relpath(self.outproj));
    def print_dependency_block(self, out, templates):
        if not len(self.dependencies): return
        PrintTemplate(out, templates, "dependencies", self);
    def print_dependencies(self, out, templates):
        for dep in self.dependencies:
            PrintTemplate(out, templates, "dependency", self, guid=dep);
    def print_nested_list(self, out, templates):
        if self.folder:
            PrintTemplate(out, templates, "nested_project", self, child=self.guid, parent=self.folder);
    # /TEMPLATE COMMANDS
    #=============================================

class VCProjectInfo(ProjectInfo):
    def __init__(self, fname, line, name, mask, translations, *argv):
        ProjectInfo.__init__(self, fname, line, name, mask, translations, True, *argv)

    def configure(self, force, skip, predefs, vs):
        if self.conf:
            args = ["projector.py", '--o', self.outproj]
            if force: args.append('--force')
            if skip: args.append('--skip')
            if vs != "":
                args.append('--vs')
                args.append(vs)
            for m in predefs.macros:
                args.append('--def')
                args.append('%s=%s' % (m, predefs.macros[m][0]))
            args.append(path.abspath(path.join(self.path(), self.conf)))
            #print " ".join(args)
            return projector.ProjectProgram().main("Project", args, self, True)

    def fetch_project_info(self, output_filename):
        (self.title, self.guid) = VCProjInfo().get(self.outproj)
        if self.title == None:
            self.Warn("file %s could not be parsed, project %s will be ignored" %\
                      (self.outproj, self.name))
            self.title  = "[unknown VC/C++ project]"
            self.guid   = "{00000000-0000-0000-0000-000000000000}"
            self.ignore = True
        return (self.name, self.guid)

    def project_class(self): return "{8BC9CEB8-8B4A-11D0-8D11-00A0C91BC942}"

#experimental
class VDDProjectInfo(ProjectInfo):
    def __init__(self, fname, line, name, mask, translations, *argv):
        ProjectInfo.__init__(self, fname, line, name, mask, translations, True, *argv)
        # VDDProjects don't have config (for now)
        self.conf = ""

    def find_ddp_title(self):
        try:
            f = open(self.outproj, 'r')
        except:
            return 0
        mask = '"ProjectName" = "8:'
        l_mask = len(mask)
        while 1:
            line = f.readline()
            if not line: break
            if line[:15] == '    "Hierarchy"': break
            if line[:l_mask] != mask: continue
            f.close()
            return line[l_mask:].split('"')[0]
        f.close()
        return 0

    def fetch_project_info(self, output_filename):
        name = self.find_ddp_title()
        if name == 0:
            self.Warn("file %s could not be parsed, project %s will be ignored" % (self.outproj, self.name))
            self.title  = "[unknown installer]"
            self.ignore = True
        else:
            self.title = name

        self.find_sln_guid(output_filename)
        return (self.name, self.guid)

    def project_class(self): return "{B900F1C2-3D47-4FEC-85B3-04AAF18C3634}"

    
#experimental
class CSProjectInfo(ProjectInfo):
    def __init__(self, fname, line, name, mask, translations, *argv):
        ProjectInfo.__init__(self, fname, line, name, mask, translations, True, *argv)
        # CSProjects don't have config (for now)
        self.conf = ""

    def fetch_project_info(self, output_filename):
        (self.title, self.guid) = CSProjInfo().get(self.outproj)
        if self.title == None:
            self.Warn("file %s could not be parsed, project %s will be ignored" %\
                      (self.outproj, self.name))
            self.title  = "[unknown CS project]"
            self.guid   = "{00000000-0000-0000-0000-000000000000}"
            self.ignore = True
        return (self.name, self.guid)

    def project_class(self): return "{FAE04EC0-301F-11D3-BF4B-00C04F79EFBC}"

class FolderInfo(ProjectInfo):
    def __init__(self, fname, line, name, parent):
        ProjectInfo.__init__(self, fname, line, name, "", {}, False, name, "", parent)
        self.guid   = ("{%s}" % uuid.uuid1()).upper()
        self.title  = name

    def fetch_project_info(self, output_filename):
        self.find_sln_guid(output_filename, False)
        return (self.name, self.guid)

    def project_class(self): return "{2150E333-8FDC-42A3-9474-1A3956D46DE8}"

    #=============================================
    # TEMPLATE COMMANDS
    def print_projpath(self, out, templates):
        out.write(self.title);
    # /TEMPLATE COMMANDS
    #=============================================

def CreateProjectInfo(fname, line, name, mask, translations, *props):
    factory = (
        (VCProjectInfo,  ".vcproj"),
        (CSProjectInfo,  ".csproj"),
        (VDDProjectInfo, ".vddproj")
        )

    ext = path.splitext(props[0])[1].lower()
    for ctor, proj_ext in factory:
        if ext == proj_ext:
            #print "Found:", ctor
            return ctor(fname, line, name, mask, translations, *props)
    return VCProject(fname, line, name, mask, translations, *props)

def cmp_nested(x, y):
    i = cmp(x[2], y[2])
    if i: return i
    return x[0]-y[0]

class SolutionProgram(IniProgram):
    def __init__(self):
        self.configs    = []
        self.platforms  = []
        self.projects   = []
        self.folders    = []
        self.conf_sec   = 0
        self.build_sec  = 0
        self.deploy_sec = 0
        self.printed_folders = {}
        self.updated = False
        
    def read_config(self):
        solution_sec   = self.get_section("Solution", kReq)
        self.configs   = self.get_array(solution_sec, "Configs")
        self.platforms = self.get_array(solution_sec, "Platforms")

        self.folders    = []
        folders_sec = self.get_section("Folders", kOpt)
        if folders_sec:
            for folder in folders_sec.items:
                folder = folders_sec.items[folder]
                self.folders.append(FolderInfo(folder.fname, folder.lineno, folder.name, folder.value))
        
        self.projects   = []
        projects_sec = self.get_section("Projects", kReq)
        for project in projects_sec.items:
            project = projects_sec.items[project]
            self.projects.append(CreateProjectInfo(project.fname, project.lineno, project.name, self.mask, self.translation, *(project.value.split(";"))))

        self.conf_sec   = self.get_section("Configurations", kOpt)
        self.build_sec  = self.get_section("Build", kOpt)
        self.deploy_sec = self.get_section("Deploy", kOpt)

    def update_projects(self):
        others = {}
        for project in self.projects: self.updated = project.configure(self.force, self.skip, self.predefs, self.vstudio) or self.updated
        for project in self.projects: m = project.fetch_project_info(self.output_filename); others[m[0]] = m[1]
        for folder  in self.folders:  folder.fetch_project_info(self.output_filename);
        for project in self.projects: project.update_dependencies(others)
        for project in self.projects: project.update_folder(self.folders)
        for folder  in self.folders:  folder.update_folder(self.folders)

    def update_filename(self):
        self.output_filename = self.input_filename.rsplit(".", 1)[0] + ".sln"

    def write_out(self, out):
        self.update_projects()
        self.configs.sort(lambda x,y: cmp(x.lower(), y.lower()))
        self.platforms.sort(lambda x,y: cmp(x.lower(), y.lower()))
        self.outloc = Location(self.output_filename, 1)
        PrintTemplate(out, vs_templates, "__main__", self, slnver = vs_slnver[self.vstudio], vsver = vs_vsver[self.vstudio])
        self.outloc = None

    #=============================================
    #
    # PROJECT.CONFIG|PLATFORM
    #
    #=============================================
    def getPCP(self, project, config, platform):
        keys = ("%s.%s|%s" % (project, config, platform),
                "%s.%s|%s" % (project, config, "*"),
                "%s.%s|%s" % (project, "*", platform),
                "%s.%s|%s" % (project, "*", "*"),
                "%s.%s|%s" % ("*", config, platform),
                "%s.%s|%s" % ("*", config, "*"),
                "%s.%s|%s" % ("*", "*", platform),
                "%s.%s|%s" % ("*", "*", "*"))

        vstrict = 0
        vleft   = 1
        vright  = 2
        vany    = 3
        voffset = 4
        files     = ["", "", "", "", "", "", "", ""]
        lines     = [0, 0, 0, 0, 0, 0, 0, 0]
        overrides = [0, 0, 0, 0, 0, 0, 0, 0]

        if self.conf_sec:
            for i in range(0, len(keys)):
                key = keys[i].lower()
                if key in self.conf_sec.items:
                    conf = self.conf_sec.items[key]
                    files[i] = conf.fname
                    lines[i] = conf.lineno
                    overrides[i] = conf.value

        debug = {}
        for i in range(0, len(keys)):
            if overrides[i]: debug[keys[i]] = overrides[i]

        #this series of multi-ifs should find most obvious matches
        if overrides[vstrict]:          override = overrides[vstrict]
        elif overrides[vleft] and overrides[vright]:
            override = self.mergePCP(vleft, vright, overrides, files, lines)
        elif overrides[vleft]:          override = overrides[vleft]
        elif overrides[vright]:         override = overrides[vright]
        elif overrides[vany]:           override = overrides[vany]
        elif overrides[vstrict+voffset]:override = overrides[vstrict+voffset]
        elif overrides[vleft+voffset] and overrides[vright+voffset]:
            override = self.mergePCP(vleft+voffset, vright+voffset, overrides, files, lines)
        elif overrides[vleft+voffset]:  override = overrides[vleft+voffset]
        elif overrides[vright+voffset]: override = overrides[vright+voffset]
        elif overrides[vany+voffset]:   override = overrides[vany+voffset]
        else:                           override = "*|*"
        
        (c, p) = override.split("|")
        c = c.strip()
        p = p.strip()

        #print "%s.%s|%s = %s %s" % (project, config, platform, override, debug)

        #less obvious matches should come out while filling
        #asterisks with anything left in overrides
        if c == '*':
            for o in overrides:
                if not o: continue
                (c0, p0) = o.split("|")
                c0 = c0.strip()
                if c0 == '*': continue
                #print "    ...[C] interesting (%s|%s)" % (c0, p0)
                p0 = p0.strip()
                if p0 != '*' and p0 != p: continue
                c = c0
                break

        if p == '*':
            for o in overrides:
                if not o: continue
                (c0, p0) = o.split("|")
                p0 = p0.strip()
                if p0 == '*': continue
                #print "    ...[P] interesting (%s|%s)" % (c0, p0)
                c0 = c0.strip()
                if c0 != '*' and c0 != c: continue
                p = p0
                break

        vconfig = config
        vplatform = platform

        if c != "*": vconfig = c
        if p != "*": vplatform = p
        
        #print "%s.[%s|%s] x [%s|%s] = [%s|%s]" % (project, config, platform, c, p, vconfig, vplatform)

        if self.build_sec: make_build = self.select_verb(keys, self.build_sec.items, True)
        else: make_build = True

        # deployment of the project is possible for non-desktops,
        # but this must be taken from the project that would be deployed itself
        #
        # after that, decision if user wants project not being deployed
        # comes from solution platform
        deploy_results = vplatform.lower() not in vs_desktop_platforms
        if deploy_results and self.deploy_sec:
            deploy_results = self.select_verb(keys, self.deploy_sec.items, make_build)
            
        #print "%s.%s|%s = %s|%s (%s, %s) %s" % (project, config, platform, vconfig, vplatform, make_build, deploy_results, debug)

        return (vconfig, vplatform, make_build, deploy_results)

    def mergePCP(self, vleft, vright, overrides, files, lines):
        # merge the left and right together, if possible
        (cl, pl) = overrides[vleft].split("|")
        cl = cl.strip()
        pl = pl.strip()
        (cr, pr) = overrides[vright].split("|")
        cr = cr.strip()
        pr = pr.strip()
        if (cl != "*" and cr != "*") or\
           (pl != "*" and pr != "*"):
            PrintMessage(files[vleft], lines[vleft],   "error: ", "cannot merge %s with %s" % (overrides[vleft], overrides[vright]))
            PrintMessage(files[vright], lines[vright], "",        "compare the other definition", 1)
            sys.exit(1)
        c = cl
        p = pl
        if c == "*": c = cr
        if p == "*": p = pr
        return "%s|%s" % (c, p)

    def select_verb(self, keys, items, def_val):
        overrides = [0, 0, 0, 0, 0, 0, 0, 0]
        for i in range(0, len(keys)):
            key = keys[i].lower()
            if key in items:
                if is_true(items[key].value):
                    overrides[i] = 2
                else:
                    overrides[i] = 1

        for override in overrides:
            if override: return override != 1

        return def_val
    #=============================================
    #
    # /PROJECT.CONFIG|PLATFORM
    #
    #=============================================

    #####################################################################################################
    #=============================================
    # TEMPLATE COMMANDS
    def print_declarations(self, out, templates):

        self.printed_folders = {}
        for project in self.projects: self.print_declaration(out, project, templates)
        for folder in self.folders:
            if folder.guid not in self.printed_folders:
                self.printed_folders[folder.guid] = 1
                self.print_declaration(out, folder, templates)

    def print_declaration(self, out, project, templates):
        if project.ignore: return
        if project.folder and project.folder not in self.printed_folders:
            self.printed_folders[project.folder] = 1
            for folder in self.folders:
                if project.folder == folder.guid:
                    self.print_declaration(out, folder, templates)
                    break
        project.outloc = self.outloc
        PrintTemplate(out, templates, "declaration", project);
        project.outloc = None

    def print_configurations(self, out, templates):
        #Config x Platform
        for config in self.configs:
            for platform in self.platforms:
                PrintTemplate(out, templates, "configuration", self, config=config, platform=platform);

    def print_connections(self, out, templates):
        #Project x Config x Platform
        for project in self.projects:
            if project.ignore: continue
            for config in self.configs:
                for platform in self.platforms:
                    vconfig, vplatform, make_build, deploy_results = \
                             self.getPCP(project.name, config, platform)
                    PrintTemplate(out, templates, "connection", self, \
                                  guid=project.guid, config=config, platform=platform, \
                                  vconfig=vconfig, vplatform=vplatform, verb=vs_verb[0])
                    if make_build:
                        PrintTemplate(out, templates, "connection", self, \
                                      guid=project.guid, config=config, platform=platform, \
                                      vconfig=vconfig, vplatform=vplatform, verb=vs_verb[1])
                    if deploy_results:
                        PrintTemplate(out, templates, "connection", self, \
                                      guid=project.guid, config=config, platform=platform, \
                                      vconfig=vconfig, vplatform=vplatform, verb=vs_verb[2])

    def print_nested_projects(self, out, templates):
        have_nested = False
        for item in self.projects:
            if not item.ignore and item.folder:
                have_nested = True
                break
        if not have_nested:
            for item in self.folders:
                if item.folder:
                    have_nested = True
                    break

        if have_nested:
            PrintTemplate(out, templates, "nested_frame", self);

    def print_nested_list(self, out, templates):
        _nested = []
        _id = 0
        for item in self.projects:
            if not item.ignore and item.folder: _nested.append((_id, item.guid, item.folder))
            _id += 1
        for item in self.folders:
            if item.folder: _nested.append((_id, item.guid, item.folder))
            _id += 1

        _nested.sort(cmp_nested)
        for rel in _nested:
            PrintTemplate(out, templates, "nested_project", self, child=rel[1], parent=rel[2])
        
    # /TEMPLATE COMMANDS
    #=============================================

if __name__=="__main__": sys.exit(SolutionProgram().main("Solution", sys.argv))
