# -*- coding: utf-8 -*-

""" Module for converting EWP project format file
    @file
"""

import os
from lxml import objectify

# IAR path variable used for compiler-installation-specific headers
# ($TOOLKIT_DIR$/inc/...). These are not available/relevant when
# building with a GCC based toolchain, so includes referencing it are
# filtered out rather than emitted as broken paths.
TOOLKIT_DIR_VAR = '$TOOLKIT_DIR$'
PROJ_DIR_VAR = '$PROJ_DIR$'


class EWPProject(object):
    """ Class for converting EWP project format file
    """

    def __init__(self, path, xmlFile, configName='Debug'):
        self.project = {}
        self.path = path
        self.xmlFile = xmlFile
        self.configName = configName
        xmltree = objectify.parse(xmlFile)
        self.root = xmltree.getroot()

        # $PROJ_DIR$ in IAR refers to the directory containing the .ewp
        # file itself, which may differ from the project root (path)
        # passed on the command line (e.g. when the .ewp lives in a
        # sub-folder such as 'EWARM'). Compute the CMake expression that
        # reproduces that directory relative to where CMakeLists.txt is
        # generated (self.path), so generated paths stay relocatable
        # instead of being baked in as absolute host paths.
        ewpDir = os.path.dirname(os.path.abspath(xmlFile))
        rel = os.path.relpath(ewpDir, os.path.abspath(path))
        if rel in ('.', ''):
            self.projDirExpr = '${CMAKE_CURRENT_SOURCE_DIR}'
        else:
            self.projDirExpr = '${CMAKE_CURRENT_SOURCE_DIR}/' + rel.replace(os.path.sep, '/')

    def _allConfigurations(self):
        """ Return all <configuration> elements in the project, in
            document order.
            @return List of lxml elements
        """
        configs = [c for c in self.root.getchildren() if c.tag == 'configuration']
        if not configs:
            raise ValueError('No <configuration> found in project file')
        return configs

    def _resolvePath(self, value):
        """ Normalize an IAR path/state string into a portable, forward
            slash separated path with IAR path variables replaced by
            their CMake equivalent.
            @param value Raw text value from the EWP file
            @return Resolved path string, or None if it references a
                    path variable that cannot be resolved (e.g. the IAR
                    toolkit installation directory)
        """
        s = str(value).replace('\\', '/')

        if TOOLKIT_DIR_VAR in s:
            return None

        s = s.replace(PROJ_DIR_VAR, self.projDirExpr)
        return s

    def parseProject(self):
        """ Parses EWP project file for project settings
        """
        # Use the .ewp file name for the project name rather than the
        # build configuration name (e.g. 'Debug'/'Release'), which would
        # otherwise become the CMake project/executable name.
        self.project['name'] = os.path.splitext(os.path.basename(self.xmlFile))[0]
        self.project['chip'] = ''

        # The build configuration passed via --config (default 'Debug')
        # only selects which configuration CMAKE_BUILD_TYPE defaults to
        # in the generated CMakeLists.txt; every configuration found in
        # the project is parsed so Debug/Release defines can both be
        # emitted, switched at CMake configure time.
        self.project['default_config'] = self.configName

        # File/group entries are shared across configurations and live
        # at the root of the document, not nested under <configuration>.
        # Files are collected per top-level IAR <group> so the generated
        # CMakeLists.txt can mirror that organization instead of dumping
        # everything into one flat list. Nested subgroups are flattened
        # into their nearest top-level ancestor group; files outside any
        # group are collected under groupsOrder key None.
        groups = {}
        groupsOrder = []
        self.searchGroups(self.root, groups, groupsOrder)
        self.project['groups'] = [
            {'name': name, 'files': groups[name]} for name in groupsOrder
        ]

        self.project['incs'] = []
        skippedIncs = []

        # Defines are collected per configuration (e.g. Debug vs.
        # Release commonly differ, e.g. DEBUG/NDEBUG), then split into
        # defines common to every configuration and defines unique to
        # each one, so the generated CMakeLists.txt can apply the
        # per-config ones conditionally on CMAKE_BUILD_TYPE.
        definesByConfig = {}
        configOrder = []

        for configuration in self._allConfigurations():
            configName = str(configuration.name)
            configOrder.append(configName)
            defs = []

            for element in configuration.getchildren():
                if element.tag == 'settings':
                    for e in element.data.getchildren():
                        if e.tag == 'option':
                            if e.name.text == 'OGChipSelectEditMenu':
                                if not self.project['chip']:
                                    self.project['chip'] = str(e.state)
                            elif e.name.text == 'CCDefines':
                                for d in e.getchildren():
                                    if d.tag == 'state' and d.text != None:
                                        defs.append(d.text)
                            elif e.name.text == 'CCIncludePath2':
                                for d in e.getchildren():
                                    if d.tag == 'state' and d.text != None:
                                        resolved = self._resolvePath(d.text)
                                        if resolved is None:
                                            skippedIncs.append(str(d.text))
                                        elif resolved not in self.project['incs']:
                                            self.project['incs'].append(resolved)

            definesByConfig[configName] = defs

        # A define is "common" only if every configuration defines it;
        # order follows the first configuration that declares it.
        commonDefines = []
        for defs in definesByConfig.values():
            for d in defs:
                if d not in commonDefines and all(d in other for other in definesByConfig.values()):
                    commonDefines.append(d)

        self.project['defines_common'] = commonDefines
        self.project['defines_by_config'] = {
            name: [d for d in definesByConfig[name] if d not in commonDefines]
            for name in configOrder
        }
        # Kept for backward compatibility with callers that expect a
        # flat list (e.g. displaySummary / the default config's view).
        self.project['defs'] = definesByConfig.get(
            self.configName, definesByConfig[configOrder[0]])

        if skippedIncs:
            print('Skipped {} include path(s) referencing {} '
                  '(IAR toolchain specific, not usable with GCC):'.format(
                      len(skippedIncs), TOOLKIT_DIR_VAR))
            for inc in skippedIncs:
                print('  ' + inc)

    def displaySummary(self):
        """ Display summary of parsed project settings
        """
        print('Project Name:' + self.project['name'])
        print('Project chip:' + self.project['chip'])
        print('Project includes: ' + ' '.join(self.project['incs']))
        print('Project defines (common): ' + ' '.join(self.project['defines_common']))
        for name, defs in self.project['defines_by_config'].items():
            print('Project defines ({}): {}'.format(name, ' '.join(defs)))
        allFiles = [f for group in self.project['groups'] for f in group['files']]
        print('Project srcs: ' + ' '.join(allFiles))

    def searchGroups(self, xml, groups, groupsOrder, currentGroup=None):
        """ Recursively walk <group> elements collecting source files,
            bucketed by the nearest enclosing top-level group name.
        @param xml XML file with project settings configuration
        @param groups Dict mapping group name (or None for ungrouped
                       root-level files) to the list of files in it
        @param groupsOrder List recording the order in which group
                            names (including None) were first seen
        @param currentGroup Name of the nearest enclosing top-level
                             group, or None if not inside one yet
        """
        for element in xml.getchildren():
            if element.tag == 'group':
                name = str(element.name) if hasattr(element, 'name') else 'Group'
                # Nested subgroups are flattened into their nearest
                # top-level ancestor group rather than creating their
                # own CMake variable.
                nextGroup = currentGroup if currentGroup is not None else name
                self.searchGroups(element, groups, groupsOrder, nextGroup)
            elif element.tag == 'file':
                name = str(element.name)
                resolved = self._resolvePath(name)
                if resolved is None:
                    print('Skipped file referencing {} (IAR toolchain '
                          'specific): {}'.format(TOOLKIT_DIR_VAR, name))
                    continue

                if currentGroup not in groups:
                    groups[currentGroup] = []
                    groupsOrder.append(currentGroup)
                groups[currentGroup].append(resolved)

    def getProject(self):
        """ Return parsed project settings stored as dictionary
        @return Dictionary containing project settings
        """
        return self.project
