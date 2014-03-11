import sys
sys.path.append("../solver")
from os import path
from IniReader import *
from xml.dom import minidom
import uuid
from files import FileList

def print_filter(out, files, name, root, keys, base = ""):
    if len(keys) == 0: return
    print >>out, "  <ItemGroup>"
    for k in keys:
        n = name
        if "assemble" in files.sec.items[k].value.split(";"): n = "CustomBuild"
        p = files.sec.items[k].name
        f = "\\".join(path.split(p)[0].split("/"))
        f = "%s%s" % (base, f)
        p = "%s%s" % (root, p)
        p = "\\".join(p.split("/"))
        if f == "":
            print >>out, """    <%s Include="%s" />""" % (n, p)
        else:
            print >>out, """    <%s Include="%s">
      <Filter>%s</Filter>
    </%s>""" % (n, p, f, n)
    print >>out, "  </ItemGroup>"

def print_file(out, files, name, root, keys):
    if len(keys) == 0: return
    print >>out, "  <ItemGroup>"
    for k in keys:
        n = name
        values = files.sec.items[k].value.split(";")
        vhash = {}
        for v in values:
            kk = v.split(":")
            if len(kk) > 1:
                if kk[0] in vhash.keys(): vhash[kk[0]].append(kk[1])
                else: vhash[kk[0]] = [kk[1]]

        if "assemble" in values: n = "CustomBuild"
        p = "%s%s" % (root, files.sec.items[k].name)
        p = "\\".join(p.split("/"))
        settings = []
        if k in files.cfiles or "pch:0" in values:
            settings.append("<PrecompiledHeader>NotUsing</PrecompiledHeader>")
        elif k in files.cppfiles and "pch:1" in values:
            settings.append("<PrecompiledHeader>Create</PrecompiledHeader>")

        if "assemble" in values:
            _p, _e = path.splitext(p)
            if _e == ".pl":
                settings.append("<Command Condition=\"'$(Platform)'=='Win32'\">perl &quot;%s&quot; win32 &gt; &quot;%s.asm&quot;</Command>" % (p, _p))
                settings.append("<Command Condition=\"'$(Platform)'=='x64'\">set ASM=ml64 /c /Cp /Cx /Zi\nperl &quot;%s&quot; masm &quot;%s.asm&quot;</Command>" % (p, _p))
                settings.append("<Outputs>%s.asm</Outputs>" % _p)
                #ASM=ml64 /c /Cp /Cx /Zi
            if _e == ".asm":
                settings.append("<Command Condition=\"'$(Platform)'=='Win32'\">ml /nologo /safeseh /Cp /coff /c /Cx /Zi &quot;/Fo$(IntDir)%s.obj&quot; &quot;%s&quot;</Command>" % (path.split(_p)[1], p))
                settings.append("<Command Condition=\"'$(Platform)'=='x64'\">ml64 /c /Cp /Cx /Zi &quot;/Fo$(IntDir)%s.obj&quot; &quot;%s&quot;</Command>" % (path.split(_p)[1], p))
                settings.append("<Outputs>$(IntDir)%s.obj</Outputs>" % path.split(_p)[1])

        _p = p
        if "exclude" in vhash.keys():
            mask = 0
            for b in vhash["exclude"]:
                c, p = b.split("|")
                if c == "*": mask = mask | 0x7
                if p == "*": mask = mask | 0x30

                if c == "Debug": mask = mask | 0x1
                if c == "Release": mask = mask | 0x6 #also always excluding PGOs
                if c == "PGO Release": mask = mask | 0x4
                if p == "Win32": mask = mask | 0x10
                if p == "x64": mask = mask | 0x20
            if mask == 0x37: settings.append("<ExcludedFromBuild>true</ExcludedFromBuild>")
            elif mask & 0xF == 0x7:
                if mask & 0xF0 == 0x10: settings.append("<ExcludedFromBuild Condition=\"'$(Platform)'=='Win32'\">true</ExcludedFromBuild>")
                if mask & 0xF0 == 0x20: settings.append("<ExcludedFromBuild Condition=\"'$(Platform)'=='x64'\">true</ExcludedFromBuild>")
            elif mask & 0xF0 == 0x30:
                if mask & 0xF == 0x1: settings.append("<ExcludedFromBuild Condition=\"'$(Configuration)'=='Debug'\">true</ExcludedFromBuild>")
                if mask & 0xF == 0x2: settings.append("<ExcludedFromBuild Condition=\"'$(Configuration)'=='Release'\">true</ExcludedFromBuild>")
                if mask & 0xF == 0x4: settings.append("<ExcludedFromBuild Condition=\"'$(Configuration)'=='PGO Release'\">true</ExcludedFromBuild>")
            else:
                if mask & 0xF == 0x1:
                    if mask & 0xF0 == 0x10: settings.append("<ExcludedFromBuild Condition=\"'$(Configuration)|$(Platform)'=='Debug|Win32'\">true</ExcludedFromBuild>")
                    if mask & 0xF0 == 0x20: settings.append("<ExcludedFromBuild Condition=\"'$(Configuration)|$(Platform)'=='Debug|x64'\">true</ExcludedFromBuild>")
                if mask & 0xF == 0x2:
                    if mask & 0xF0 == 0x10: settings.append("<ExcludedFromBuild Condition=\"'$(Configuration)|$(Platform)'=='Release|Win32'\">true</ExcludedFromBuild>")
                    if mask & 0xF0 == 0x20: settings.append("<ExcludedFromBuild Condition=\"'$(Configuration)|$(Platform)'=='Release|x64'\">true</ExcludedFromBuild>")
                if mask & 0xF == 0x4:
                    if mask & 0xF0 == 0x10: settings.append("<ExcludedFromBuild Condition=\"'$(Configuration)|$(Platform)'=='PGO Release|Win32'\">true</ExcludedFromBuild>")
                    if mask & 0xF0 == 0x20: settings.append("<ExcludedFromBuild Condition=\"'$(Configuration)|$(Platform)'=='PGO Release|x64'\">true</ExcludedFromBuild>")
        p = _p

        if len(settings) == 0: print >>out, """    <%s Include="%s" />""" % (n, p)
        else:
            print >>out, """    <%s Include="%s">""" % (n, p)
            for s in settings: print >>out, """      %s""" % s
            print >>out, """    </%s>""" % n
    print >>out, "  </ItemGroup>"

def print_filters(files, outname, root):
    if files.file_fresh(outname): return
    print outname
    out = open(outname, "w")
    dirs = {}
    for f in files.sec.items:
        base = ""
        #if f in files.includes: base = "Header Files\\"
        #elif (f in files.cfiles) or (f in files.cppfiles): base = "Source Files\\"
        #else: base = "Resource Files\\"
        p = path.split(files.sec.items[f].name)[0]
        while p != "":
            dirs["%s%s" % (base, "\\".join(p.split("/")))] = 1
            p = path.split(p)[0]

    print >>out, """<?xml version=\"1.0\" encoding=\"utf-8\"?>
    <Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
      <ItemGroup>"""
    #<Filter Include="Source Files">
    #  <UniqueIdentifier>{4FC737F1-C7A5-4376-A066-2A32D752A2FF}</UniqueIdentifier>
    #  <Extensions>cpp;c;cc;cxx;def;odl;idl;hpj;bat;asm;asmx</Extensions>
    #</Filter>
    #<Filter Include="Header Files">
    #  <UniqueIdentifier>{93995380-89BD-4b04-88EB-625FBE52EBFB}</UniqueIdentifier>
    #  <Extensions>h;hpp;hxx;hm;inl;inc;xsd</Extensions>
    #</Filter>
    #<Filter Include="Resource Files">
    #  <UniqueIdentifier>{67DA6AB6-F800-4c08-8B7A-83BB121AAD01}</UniqueIdentifier>
    #  <Extensions>rc;ico;cur;bmp;dlg;rc2;rct;bin;rgs;gif;jpg;jpeg;jpe;resx;tiff;tif;png;wav;mfcribbon-ms</Extensions>
    #</Filter>"""
    dirs = dirs.keys()
    dirs.sort()
    for d in dirs:
        print >>out, """    <Filter Include=\"%s\">
      <UniqueIdentifier>{%s}</UniqueIdentifier>
    </Filter>""" % (d, uuid.uuid1())
    print >>out, "  </ItemGroup>"
    print_filter(out, files, "None", root, files.datafiles)#, "Resource Files\\")
    print_filter(out, files, "ClCompile", root, files.cfiles + files.cppfiles)#, "Source Files\\")
    print_filter(out, files, "ClInclude", root, files.includes)#, "Header Files\\")
    print >>out, "</Project>"

def print_project(files, outname, root, bintype, basename, guid):
    if files.file_fresh(outname): return
    print outname
    out = open(outname, "w")
    bbasename = """..\..\%s\win32\%s""" % (basename, basename)
    print >>out, """<?xml version="1.0" encoding="utf-8"?>
<Project DefaultTargets="Build" ToolsVersion="12.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
  <ItemGroup Label="ProjectConfigurations">
    <ProjectConfiguration Include="Debug|Win32">
      <Configuration>Debug</Configuration>
      <Platform>Win32</Platform>
    </ProjectConfiguration>
    <ProjectConfiguration Include="Debug|x64">
      <Configuration>Debug</Configuration>
      <Platform>x64</Platform>
    </ProjectConfiguration>
    <ProjectConfiguration Include="Release|Win32">
      <Configuration>Release</Configuration>
      <Platform>Win32</Platform>
    </ProjectConfiguration>
    <ProjectConfiguration Include="Release|x64">
      <Configuration>Release</Configuration>
      <Platform>x64</Platform>
    </ProjectConfiguration>
  </ItemGroup>
  <PropertyGroup Label="Globals">
    <ProjectGuid>{%s}</ProjectGuid>
    <Keyword>Win32Proj</Keyword>
    <RootNamespace>%s</RootNamespace>
  </PropertyGroup>""" % (guid, basename)
    print >>out, """  <Import Project="$(VCTargetsPath)\Microsoft.Cpp.Default.props" />
  <PropertyGroup Label="Configuration">
    <ConfigurationType>%s</ConfigurationType>
    <PlatformToolset>CTP_Nov2013</PlatformToolset>
    <CharacterSet>Unicode</CharacterSet>
  </PropertyGroup>
  <PropertyGroup Condition="'$(Configuration))'=='Debug'" Label="Configuration">
    <UseDebugLibraries>true</UseDebugLibraries>
  </PropertyGroup>
  <PropertyGroup Condition="'$(Configuration)'=='Release'" Label="Configuration">
    <UseDebugLibraries>false</UseDebugLibraries>
    <WholeProgramOptimization>true</WholeProgramOptimization>
  </PropertyGroup>""" % bintype
    print >>out, """  <Import Project="$(VCTargetsPath)\Microsoft.Cpp.props" />
  <ImportGroup Label="ExtensionSettings">
  </ImportGroup>
  <ImportGroup Label="PropertySheets" Condition="'$(Configuration)|$(Platform)'=='Debug|Win32'">
    <Import Project="$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props" Condition="exists('$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props')" Label="LocalAppDataPlatform" />
  </ImportGroup>
  <ImportGroup Label="PropertySheets" Condition="'$(Configuration)|$(Platform)'=='Release|Win32'">
    <Import Project="$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props" Condition="exists('$(UserRootDir)\Microsoft.Cpp.$(Platform).user.props')" Label="LocalAppDataPlatform" />
  </ImportGroup>
  <ImportGroup Label="PropertySheets">
    <Import Project="$(SolutionDir)\..\solver\win32\$(Platform).props" Condition="exists('$(SolutionDir)\..\solver\win32\$(Platform).props')" />
    <Import Project="$(SolutionDir)\..\solver\win32\$(Configuration).props" Condition="exists('$(SolutionDir)\..\solver\win32\$(Configuration).props')" />
    <Import Project="$(SolutionDir)\..\solver\win32\$(Platform).$(Configuration).props" Condition="exists('$(SolutionDir)\..\solver\win32\$(Platform).$(Configuration).props')" />
    <Import Project="$(SolutionDir)\solution.props" Condition="exists('$(SolutionDir)\solution.props')" />
    <Import Project="$(SolutionDir)\solution.$(Platform).props" Condition="exists('$(SolutionDir)\solution.$(Platform).props')" />
    <Import Project="$(SolutionDir)\solution.$(Configuration).props" Condition="exists('$(SolutionDir)\solution.$(Configuration).props')" />
    <Import Project="$(SolutionDir)\solution.$(Platform).$(Configuration).props" Condition="exists('$(SolutionDir)\solution.$(Platform).$(Configuration).props')" />"""
    print >>out, """    <Import Project="$(SolutionDir)\%s.props" Condition="exists('$(SolutionDir)\%s.props')" />
    <Import Project="$(SolutionDir)\%s.$(Platform).props" Condition="exists('$(SolutionDir)\%s.$(Platform).props')" />
    <Import Project="$(SolutionDir)\%s.$(Configuration).props" Condition="exists('$(SolutionDir)\%s.$(Configuration).props')" />
    <Import Project="$(SolutionDir)\%s.$(Platform).$(Configuration).props" Condition="exists('$(SolutionDir)\%s.$(Platform).$(Configuration).props')" />""" % (
      bbasename, bbasename, bbasename, bbasename, bbasename, bbasename, bbasename, bbasename
      )
    print >>out, """    <Import Project="$(SolutionDir)\%s.props" Condition="exists('$(SolutionDir)\%s.props')" />
    <Import Project="$(SolutionDir)\%s.$(Platform).props" Condition="exists('$(SolutionDir)\%s.$(Platform).props')" />
    <Import Project="$(SolutionDir)\%s.$(Configuration).props" Condition="exists('$(SolutionDir)\%s.$(Configuration).props')" />
    <Import Project="$(SolutionDir)\%s.$(Platform).$(Configuration).props" Condition="exists('$(SolutionDir)\%s.$(Platform).$(Configuration).props')" />""" % (
      basename, basename, basename, basename, basename, basename, basename, basename
      )
    print >>out, """
  </ImportGroup>
  <PropertyGroup Label="UserMacros" />"""
    print_file(out, files, "None", root, files.datafiles)
    print_file(out, files, "ClCompile", root, files.cfiles + files.cppfiles)
    print_file(out, files, "ClInclude", root, files.includes)
    print >>out, """  <Import Project="$(VCTargetsPath)\Microsoft.Cpp.targets" />
  <ImportGroup Label="ExtensionTargets">
  </ImportGroup>
</Project>"""

    
def create_project(root, base, bintype, guid):
    files = FileList()
    predef = Macros()
    predef.add_macro("WIN32", "", Location("<command-line>", 0))
    #predef.add_macro("EXTERNAL_OPENSSL", "", Location("<command-line>", 0))
    files.read(predef, "%s%s/%s.files" % (root, base, base))
    tmp = []
    for k in files.datafiles:
        f = files.sec.items[k]
        if "assemble" not in f.value.split(";"): continue
        tmp.append(k)
        files.cppfiles.append(k)
        _p, ext = path.splitext(f.name)
        if ext.lower() == ".asm": continue
        _p += ".asm"
        files.sec.append(Field(f, _p, f.value))
        files.cppfiles.append(_p.lower())
    for k in tmp: files.datafiles.remove(k)

    print_filters(files, "%s.vcxproj.filters" % base, root)
    print_project(files, "%s.vcxproj" % base, root, bintype, base, guid)

create_project(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
