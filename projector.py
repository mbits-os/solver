# Builds vcproj file based on configuration.
# Usage: projector.py [config-file] [opt:output-name]
# If output-name is not given, value from Project.Name is taken
# and .vcproj extension is added
# Example: projector.py zephyr-vcproj.conf zephyr-ex.vcproj

from os import path
from IniReader import *
from xml.dom import minidom
import sys, uuid

vs_vcver={"8":"8.00", "9":"9.00", "10":"10.00"}

vs_magic_secs = ("CharacterSet",
                 "WholeProgramOptimization")

vs_cpptools  = ("VCCustomBuildTool",
                "VCXMLDataGeneratorTool",
                "VCWebServiceProxyGeneratorTool",
                "VCMIDLTool",
                "VCCLCompilerTool",
                "VCManagedResourceCompilerTool",
                "VCResourceCompilerTool",
                "VCPreLinkEventTool",
                "VCLinkerTool",
                "VCALinkTool",
                "VCManifestTool",
                "VCXDCMakeTool",
                "VCBscMakeTool",
                "VCFxCopTool",
                "VCAppVerifierTool")

vs_deptools  = ("VCCustomBuildTool",
                "VCXMLDataGeneratorTool",
                "VCWebServiceProxyGeneratorTool",
                "VCMIDLTool",
                "VCCLCompilerTool",
                "VCManagedResourceCompilerTool",
                "VCResourceCompilerTool",
                "VCPreLinkEventTool",
                "VCLinkerTool",
                "VCALinkTool",
                "VCXDCMakeTool",
                "VCBscMakeTool",
                "VCCodeSignTool")

vs_utiltools = ("VCCustomBuildTool",
                "VCMIDLTool")

vs_pretool   = "VCPreBuildEventTool"
vs_posttool  = "VCPostBuildEventTool"

vs_templates = {
    #__main__
    "__main__": """<?xml version="1.0" encoding="windows-1250"?>
<VisualStudioProject
	ProjectType="Visual C++"
	Version="{vcver}"
	Name="{name}"
	ProjectGUID="{guid}"
	RootNamespace="{name}"
	Keyword="Win32Proj"
	TargetFrameworkVersion="0"
	>
	<Platforms>
{print_platforms!c}	</Platforms>
	<ToolFiles>
{print_tools!c}	</ToolFiles>
	<Configurations>
{print_configurations!c}	</Configurations>
	<References>
	</References>
	<Files>
{print_files!c}	</Files>
	<Globals>
	</Globals>
</VisualStudioProject>
""",
    "platform": '		<Platform\n			Name="{platform}"\n		/>\n',
    "tool":     '		<ToolFile\n			RelativePath="{tool}"\n		/>\n',

    # CONFIGURATION
    "configuration": """		<Configuration
			Name="{vconfig}"
			ConfigurationType="{ct_type}"
{print_params!c}			>
{print_conf_tools!c}		</Configuration>
""",
    "propsheets": '			InheritedPropertySheets="{value}"\n',
    "magic.CharacterSet": '			CharacterSet="{value}"\n',
    "magic.WholeProgramOptimization": '			WholeProgramOptimization="{value}"\n',
    # TOOLS
    "tool_node": """{indent}<Tool
	{indent}Name="{tool}"
{print_attrs!c}{indent}/>
""",
    "tool_attr": """	{indent}{attr}
""",
    "deploy_tools": """			<DeploymentTool
				ForceDirty="-1"
				RemoteDirectory=""
				RegisterOutput="0"
				AdditionalFiles=""
			/>
			<DebuggerTool
			/>
""",
    # NODES:
    "filter_node": """{indent}<Filter
	{indent}Name="{name}"
	{indent}>
{print_children!c}{indent}</Filter>
""",
    "file_node": """{indent}<File
	{indent}RelativePath="{name}"
	{indent}>
{print_file_configs!c}{indent}</File>
""",
    "file_conf": """{indent}<FileConfiguration
	{indent}Name="{config}"
{print_conf_attrs!c}	{indent}>
{print_vcproj_attrs!c}{indent}</FileConfiguration>
""",
    "file_conf_attr": """	{indent}{attr}
""",
}

def relative_a(vcproj, filename):
    vsp = os.path.abspath(Location(vcproj, 0).path()).replace("\\", "/").split("/")
    #print vsp, filename
    while len(vsp) and len(filename) and vsp[0].lower() == filename[0].lower():
        vsp = vsp[1:]
        filename = filename[1:]

    l = len(vsp)
    vsp = []
    for i in range(0, l): vsp.append("..")
    filename = vsp + filename
    tmp = os.path.join(*filename)
    if tmp != os.path.abspath(tmp) and len(tmp) and tmp[0] != '.':
        return ["."] + filename
    return filename

class ToolPrinter:
    def __init__(self, depth, tool, attrs):
        self.indent = "\t" * depth
        self.tool = tool
        self.attrs = attrs

    def print_tool(self, out, templates):
        PrintTemplate(out, templates, "tool_node", self)
    def print_attrs(self, out, templates):
        for attr in self.attrs:
            PrintTemplate(out, templates, "tool_attr", self, attr=attr)
        
class FileNode:
    def __init__(self, name, props):
        self.name = name
        self.props = props
        for i in range(0, len(self.props)):
            prop = self.props[i].split("=", 1)
            for j in range(0, len(prop)): prop[j] = prop[j].strip()
            self.props[i] = prop

    def write(self, out, depth, configurations, platforms, templates):
        self.indent = "\t" * depth
        self.c_configs = configurations
        self.c_platforms = platforms
        self.c_depth = depth + 1
        PrintTemplate(out, templates, "file_node", self, indent=self.indent)

    def write_conf(self, out, config, common_attrs, compiler_attrs, templates):
        self.common_attrs = common_attrs
        self.vc_attrs = compiler_attrs
        PrintTemplate(out, templates, "file_conf", self, indent=self.indent+"\t", config=config)

    def print_file_configs(self, out, templates):
        pch = 0
        confs = []
        for prop in self.props:
            if prop[0] == "pch":
                if is_true(prop[1]): pch = 1
            elif prop[0] == "conf":
                confs.append(prop[1])

        c = []
        for conf in confs:
            (configuration, platform) = conf.split("|")
            if configuration == "*" and platform == "*":
                #we have 'conf' property, but the set
                #of unavailable confs is empty
                c = []
                break
            elif configuration == "*":
                for config in self.c_configs:
                    c.append(config + "|" + platform)
            elif platform == "*":
                for pltfrm in self.c_platforms:
                    c.append(configuration + "|" + pltfrm)
        confs = c

        if pch:
            for config in self.c_configs:
                for pltfrm in self.c_platforms:
                    self.write_conf(out, config+"|"+pltfrm, [], ['UsePrecompiledHeader="1"'], templates)
        if len(confs):
            for config in self.c_configs:
                for pltfrm in self.c_platforms:
                    c = config+"|"+pltfrm
                    if c not in confs:
                        self.write_conf(out, c, ['ExcludedFromBuild="true"'], [], templates)

    def print_conf_attrs(self, out, templates):
        for attr in self.common_attrs:
            PrintTemplate(out, templates, "file_conf_attr", self, indent=self.indent+"\t\t", attr=attr)

    def print_vcproj_attrs(self, out, templates):
        if len(self.vc_attrs):
            ToolPrinter(self.c_depth + 1, 'VCCLCompilerTool', self.vc_attrs).print_tool(out, templates)

class FilterNode:
    def __init__(self, name):
        self.name = name
        self.files = {}
        self.nodes = {}

    def get_name(self): return self.name
    
    def get_filter(self, path):
        current = self
        for item in path:
            if item in ("", "."): continue
            it = item.lower()
            if not current.nodes.has_key(it):
                current.nodes[it] = FilterNode(item)
            current = current.nodes[it]
        return current

    def append_file(self, fname, vcproj, source, line, lstrip):
        if not fname: return
        err = Location(source, line)
        fname_props = fname.split("[", 1)
        if len(fname_props) == 2 and fname[-1] != "]": err.Error("']' expected")
        if len(fname_props) == 1 and fname[-1] == "]": err.Error("'[' expected")
        fname_props[0] = fname_props[0].replace("\\", "/")
        props = []
        if len(fname_props) == 2: props = fname_props[1][:-1].split(",")
        path = fname_props[0].split('/')
        if len(path) == 0: err.Error("path expected")

        path = relative_a(vcproj, path)
        filename = os.path.join(*path)

        leaf = path[-1].lower()
        path = path[:-1] #cut the file node
        if lstrip:
            #err.Warn("lstrip: %s" % lstrip)
            #err.Warn("path: %s" % path)
            while len(lstrip) and len(path) and lstrip[0].lower() == path[0].lower():
                lstrip = lstrip[1:]
                path = path[1:]
        else:
            while len(path) > 0 and (path[0] == "." or path[0] == ".."): path = path[1:]

        node = self.get_filter(path)

        node.files[leaf] = FileNode(filename, props)

    def raw_append_file(self, node):
        self.files.append(node)

    def write(self, out, depth, confs, platforms, templates):
        self.c_depth = depth
        self.c_confs = confs
        self.c_platforms = platforms

        if self.name == "":
            self.print_children(out, templates)
        else:
            self.indent = "\t" * depth
            self.c_depth += 1
            PrintTemplate(out, templates, "filter_node", self)

    def write_children(self, out, children, templates):
        keys = children.keys()
        keys.sort()
        for key in keys: children[key].write(out, self.c_depth, self.c_confs, self.c_platforms, templates)

    def print_children(self, out, templates):
        self.write_children(out, self.files, templates)
        self.write_children(out, self.nodes, templates)

class ProjectProgram(IniProgram):
    def __init__(self):
        IniProgram.__init__(self)
        self.cleanup()

    def cleanup(self):
        self.configs   = []
        self.platforms = []
        self.tools     = [] #tool files
        self.usertools = [] #tools inside tool files
        self.preftools = {} #hash for props taken from vsprops
        self.guid      = 0
        self.name      = 0
        self.props_sec = 0
        self.confs_sec = 0
        self.magic_secs = {}
        self.files_sec = 0

    def read_config(self):
        project_sec    = self.get_section("Project", kReq)
        self.configs   = self.get_array(project_sec, "Configs")
        self.platforms = self.get_array(project_sec, "Platforms")
        self.guid      = self.get_optional_item (project_sec, "GUID")
        self.name      = self.get_item (project_sec, "Name", "Project name missing").value
        if not self.guid:
            self.no_guid_fname = project_sec.fname
            self.no_guid_line = project_sec.lineno

        self.tools = []
        tools = self.get_optional_item(project_sec, "Tools")
        if tools:
            tools = tools.value.split(";")
            for tool in tools:
                if tool: self.tools.append(tool)

        self.props_sec = self.get_section("Props", kReq)
        self.confs_sec = self.get_section("ConfigurationType", kReq)
        for magic in vs_magic_secs:
            self.magic_secs[magic] = self.get_section(magic, kOpt)
        self.files_sec = self.get_section("Files", kOpt)

        self.find_user_tools()

    def append_defines(self, _ctx):
        if "project" not in _ctx.sections: return
        project = _ctx.sections["project"]
        if "name" not in project.items: return
        self.append_define("Name", project.items["name"].value)

    def write_out(self, out):
        #VS sorts configs/platforms only in sln, not vcproj
        #self.configs.sort(lambda x,y: cmp(x.lower(), y.lower()))
        #self.platforms.sort(lambda x,y: cmp(x.lower(), y.lower()))

        if not self.guid:
            (title, guid) = VCProjInfo().get(self.output_filename)

            loc = Location(self.no_guid_fname, self.no_guid_line)
            if guid == 0:
                vcproj_guid = ("{%s}" % uuid.uuid1()).upper()
                loc.Warn("invening Project.GUID %s" % vcproj_guid)
            else:
                vcproj_guid = guid.upper()
                loc.Message("info: reusing Project.GUID %s" % vcproj_guid)
        else:
            vcproj_guid = self.guid.value

        self.outloc = Location(self.output_filename, 1)
        PrintTemplate(out, vs_templates, "__main__", self, guid=vcproj_guid, vcver = vs_vcver[self.vstudio])
        self.outloc = None

    def get_optional_config(self, section, name):
        if not section: return None

        universal = 0
        left = 0
        right = 0
        key = self.c_config + "|" + self.c_platform
        lkey = self.c_config + "|*"
        rkey = "*|" + self.c_platform
        lfile = ""
        lline = 0
        rfile = ""
        rline = 0
        for item in section.items:
            item = section.items[item]
            if item.name == key: return item.value
            elif item.name == "*|*": universal = item.value
            elif item.name == lkey:
                left = item.value
                lfile = item.fname
                lline = item.lineno
            elif item.name == rkey:
                right = item.value
                rfile = item.fname
                rline = item.lineno
        if left != 0:
            if right != 0:
                PrintMessage(lfile, lline, "error: ", "both %s and %s %s present" % (lkey, rkey, name))
                PrintMessage(rfile, rline, "",        "compare the other definition", 1)
                sys.exit(1)
            return left
        if right != 0: return right
        if universal != 0: return universal
        return None
    
    def update_filename(self):
        fname = self.name + ".vcproj"
        if self.input_filename:
            fname = path.join(path.dirname(self.input_filename), fname)
        self.output_filename = fname

    def get_config_type(self):
        ct = self.get_optional_config(self.confs_sec, "ConfigurationType")
        if ct == None: return "1" #default to an EXE project
        return ct

    def get_config_props(self):
        keys = [ "*|*", self.c_config + "|*", "*|" + self.c_platform, self.c_config + "|" + self.c_platform ]
        props = []
        for prop in self.props_sec.index:
            prop = self.props_sec.items[prop]
            for key in keys:
                if prop.name == key:
                    for f in prop.value.split(";"):
                        props.append(os.path.join(*relative_a(self.output_filename, os.path.abspath(f).replace("\\", "/").split("/"))))
        return props

    def find_user_tools(self):
        self.usertools = []
        for tool in self.tools: self.find_user_rules(tool)
        #self.usertools.sort()

    def find_user_rules(self, tool):
        try:
            dom = minidom.parse(tool)
        except:
            return

        local = []
        for rule in dom.getElementsByTagName("CustomBuildRule"):
            name = rule.getAttribute("Name")
            if name: local.append(name)
        local.reverse()
        self.usertools += local

    def write_user_settings(self, out, templates, settings):
        attrs = []
        tool = settings["Name"]
        keys = settings.keys()
        keys.remove("Name")
        keys.sort()
        for key in keys:
            attrs.append('%s="%s"' % (key, settings[key]))
        ToolPrinter(3, tool, attrs).print_tool(out, templates)

    def get_user_tools(self, prop):
        if not self.preftools.has_key(prop):
            self.preftools[prop] = self.get_user_tools_from_vsprops(prop)
        return self.preftools[prop]

    def get_user_tools_from_vsprops(self, prop):
        try:
            dom = minidom.parse(prop)
        except:
            return []

        tools = []
        for tool in dom.getElementsByTagName("Tool"):
            name = tool.getAttribute("Name")
            settings = {}
            if name not in self.usertools: continue
            for i in range(0, tool.attributes.length):
                attr = tool.attributes.item(i)
                settings[attr.nodeName]=attr.nodeValue
            if len(settings) > 1:
                tools.append(settings)

        return tools

    #####################################################################################################
    #=============================================
    # TEMPLATE COMMANDS
    def print_platforms(self, out, templates):
        for platform in self.platforms:
            PrintTemplate(out, templates, "platform", self, platform=platform)

    def print_tools(self, out, templates):
        for tool in self.tools:
            tool = Location(self.output_filename, 0).relpath(tool)
            PrintTemplate(out, templates, "tool", self, tool=tool)

    def print_configurations(self, out, templates):
        for config in self.configs:
            for platform in self.platforms:
                self.c_config = config
                self.c_platform = platform
                self.c_ct = self.get_config_type()
                self.c_props = self.get_config_props()

                PrintTemplate(out, templates, "configuration", self, vconfig="%s|%s" % (config, platform), ct_type=self.c_ct)

    def print_params(self, out, templates):
        if len(self.c_props):
            PrintTemplate(out, templates, "propsheets", self, value=";".join(self.c_props))

        for magic in self.magic_secs:
            value = self.get_optional_config(self.magic_secs[magic], magic)
            if value != None:
                PrintTemplate(out, templates, "magic." + magic, self, value=value)
    
    def print_conf_tools(self, out, templates):
        deployable = self.c_platform.lower() not in vs_desktop_platforms
        
        if int(self.c_ct) < 10:
            if deployable: vs_tools = vs_deptools
            else: vs_tools = vs_cpptools
        else: vs_tools = vs_utiltools

        tools = {}
        tools[vs_pretool] = {"Name" : vs_pretool}
        tools[vs_posttool] = {"Name" : vs_posttool}
        for tool in vs_tools: tools[tool] = {"Name" : tool}

        if len(self.usertools):
            for tool in self.usertools:
                tools[tool] = {"Name" : tool}

            #copy settings from property files (for user tools)
            for prop in self.c_props:
                defs = self.get_user_tools(prop)
                for settings in defs:
                    tool = settings["Name"]
                    #this below will overwrite with the oldest
                    #this is not aligend with MSes algorithm
                    #(for one, settings can be merged into one)
                    for key in settings.keys():
                        tools[tool][key] = settings[key]
                        #next pass-es are for IDLE to indent next line properly
                        pass
                    pass
                pass
            pass

        if deployable: tools["VCCLCompilerTool"]["ExecutionBucket"]="7"

        #write all the tools:
        #order is: pre - custom (sorted?) - predef - post - remote
        #custom order seems to be: same as tool file nodes, reverse rules per file
        self.write_user_settings(out, templates, tools[vs_pretool])
        for key in self.usertools:
            self.write_user_settings(out, templates, tools[key])
        for key in vs_tools:
            self.write_user_settings(out, templates, tools[key])
        self.write_user_settings(out, templates, tools[vs_posttool])

        if deployable:
            PrintTemplate(out, templates, "deploy_tools", self)
    
    def print_files(self, out, templates):
        root = FilterNode("")
        if self.files_sec != 0:
            for fltr in self.files_sec.items:
                fltr = self.files_sec.items[fltr]
                fltr_name = fltr.name.split(";", 1)
                lstrip = None
                if len(fltr_name) > 1:
                    lstrip = os.path.abspath(os.path.join(fltr.path(), fltr_name[1].strip()))
                    lstrip = relative_a(self.output_filename, lstrip.replace("\\", "/").split("/"))
                fltr_name = fltr_name[0].strip()
                if fltr_name == "__root__": current = root
                else: current = root.get_filter(fltr_name.replace("\\", "/").split("/"))
                for fname in fltr.value.split(";"): current.append_file(fname, self.output_filename, fltr.fname, fltr.lineno, lstrip)
        #root.raw_append_file(FileNode(self.input_filename, []))
        root.write(out, 2, self.configs, self.platforms, templates)

    # /TEMPLATE COMMANDS
    #=============================================

if __name__=="__main__": sys.exit(ProjectProgram().main("Project", sys.argv))
