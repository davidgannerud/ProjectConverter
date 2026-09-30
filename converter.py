# -*- coding: utf-8 -*-

""" Entry point for project conversion
    @file
"""

import os
import argparse
import cmake
import ewpproject
import uvprojxproject

def find_file(path, fileext):
    """ Find file with extension in path. Prefers a match directly in
        `path` over one in a subdirectory, since project files sitting
        deeper in the tree (e.g. IDE-specific subfolders) are otherwise
        picked arbitrarily and can silently shadow the intended one.
        @param path Root path of the project
        @param fileext File extension to find
        @return File name
    """
    matches = []
    for root, dirs, files in os.walk(path):
        for file in files:
            if file.endswith(fileext):
                matches.append(os.path.join(root, file))

    if not matches:
        return ''

    # Sort by directory depth (shallowest first), then alphabetically
    # for a deterministic choice among files at the same depth.
    matches.sort(key=lambda p: (p.count(os.sep), p))

    if len(matches) > 1:
        print('Warning: multiple {} files found, using \'{}\':'.format(
            fileext, matches[0]))
        for match in matches:
            print('  ' + match)

    return matches[0]

if __name__ == '__main__':
    """ Parses params and calls the right conversion"""

    parser = argparse.ArgumentParser()
    parser.add_argument("format", choices=("ewp", "uvprojx"))
    parser.add_argument("path", type=str, help="Root directory of project")
    parser.add_argument("--config", type=str, default="Debug",
                         help="Name of the EWP build configuration to convert (default: Debug)")
	#"--ewp", help="Search for *.EWP file in project structure", action='store_true')
    #parser.add_argument("--uvprojx", help="Search for *.UPROJX file in project structure", action='store_true')
    args = parser.parse_args()

    if os.path.isdir(args.path):
        if args.format == 'ewp':
            print('Looking for *.ewp file in ' + args.path)
            filename = find_file(args.path, '.ewp')
            if len(filename):
                print('Found project file: ' + filename)
                project = ewpproject.EWPProject(args.path, filename, args.config)
                project.parseProject()
                project.displaySummary()
                cmakefile = cmake.CMake(project.getProject(), args.path)
                cmakefile.populateCMake()
            else:
                print('No project *.ewp file found')
        elif args.format == 'uvprojx':
            print('Looking for *.uvprojx file in ' + args.path)
            filename = find_file(args.path, '.uvprojx')
            if len(filename):
                print('Found project file: ' + filename)
                project = uvprojxproject.UVPROJXProject(args.path, filename)
                project.parseProject()
                project.displaySummary()

                cmakefile = cmake.CMake(project.getProject(), args.path)
                cmakefile.populateCMake()
            else:
                print('No project *.uvprojx file found')
        else:
            print ('No format specified')
    else:
        print('Not a valid file path')
