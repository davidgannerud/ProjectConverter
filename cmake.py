# -*- coding: utf-8 -*-

""" CMake generation module
    @file
"""

import os
import re
import platform
import datetime
from jinja2 import Environment, FileSystemLoader

# Templates (CMakeLists.txt, linker scripts, ...) always live in a
# 'templates' folder alongside this script, regardless of the current
# working directory or the target project path. Loading them via a
# relative '.' path previously meant that when the target project path
# matched the current working directory (the common case of running
# the converter from inside the project being converted), the
# generated CMakeLists.txt -- written to that same path -- silently
# overwrote and destroyed the Jinja2 template it was rendered from,
# breaking every subsequent run.
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')


# Chip name substring -> (mcpu flag, chip family). Family drives which
# family-specific assets (linker script, OpenOCD target) can be
# generated; families without a known linker script/OpenOCD target are
# still given a correct -mcpu flag, but family specific extras are
# skipped with a warning instead of emitting incorrect STM32 defaults.
CHIP_CORE_TABLE = [
    ('STM32F0', '-mcpu=cortex-m0', 'stm32'),
    ('STM32F1', '-mcpu=cortex-m3', 'stm32'),
    ('STM32F2', '-mcpu=cortex-m3', 'stm32'),
    ('STM32F3', '-mcpu=cortex-m4', 'stm32'),
    ('STM32F4', '-mcpu=cortex-m4', 'stm32'),
    ('STM32F7', '-mcpu=cortex-m7', 'stm32'),
    ('STM32L0', '-mcpu=cortex-m0plus', 'stm32'),
    ('STM32L1', '-mcpu=cortex-m3', 'stm32'),
    ('STM32L4', '-mcpu=cortex-m4', 'stm32'),
    ('MKL', '-mcpu=cortex-m0plus', 'kinetis'),
    ('MK0', '-mcpu=cortex-m0plus', 'kinetis'),
    ('MK2', '-mcpu=cortex-m4', 'kinetis'),
    ('MK6', '-mcpu=cortex-m4', 'kinetis'),
    ('MK7', '-mcpu=cortex-m7', 'kinetis'),
]

# Chip family -> OpenOCD target config name. Families without an entry
# here have no OpenOCD target generated.
OOCD_TARGET_BY_FAMILY = {
    'stm32': 'stm32f3x',
}

# Chip family -> linker script template name shipped with this
# converter. Families without an entry here get no linker script
# generated/linked; the user must supply one.
LINKER_SCRIPT_BY_FAMILY = {
    'stm32': 'STM32FLASH.ld',
}

SOURCE_EXTENSIONS = ('.c', '.cpp', '.cc', '.cxx')
HEADER_EXTENSIONS = ('.h', '.hpp', '.hxx')
ASM_EXTENSIONS = ('.s', '.asm', '.s79', '.msa')


class CMake (object):

    def __init__(self, project, path):

        self.path = path
        self.project = project
        self.context = {}

    def _resolveChip(self):
        """ Match the parsed chip name against the known chip table
            @return Tuple of (mcpu flag, family) or ('', None) if the
                    chip is not recognized
        """
        chip = self.project['chip']
        for prefix, core, family in CHIP_CORE_TABLE:
            if prefix in chip:
                return core, family

        print('WARNING: Unrecognized chip \'{}\'; no -mcpu flag, linker '
              'script or OpenOCD target could be determined. Please set '
              'these manually in the generated CMakeLists.txt.'.format(chip))
        return '', None

    def _makeGroupVar(self, name, used):
        """ Derive a unique CMake list variable name from a project
            group name, e.g. 'data' -> 'DATA_SOURCES'.
            @param name Raw group name (or None/'' for ungrouped files)
            @param used Dict tracking variable names already handed out,
                        updated in place to keep names unique
            @return Unique CMake variable name
        """
        label = name if name else 'Other'
        base = re.sub(r'[^0-9A-Za-z]+', '_', label).strip('_').upper()
        if not base:
            base = 'OTHER'
        if base[0].isdigit():
            base = '_' + base
        var = base + '_SOURCES'

        count = used.get(var, 0)
        if count:
            used[var] = count + 1
            var = '{}_{}'.format(var, count + 1)
        else:
            used[var] = 1
        return var

    def populateCMake (self):
        """ Generate CMakeList.txt file for building the project
        """

        # For debug run cmake -DCMAKE_BUILD_TYPE=Debug or Release
        cmake = {}
        #fpu = '-mfpu=fpv5-sp-d16 -mfloat-abi=softfp'
        fpu = ''

        core, family = self._resolveChip()

        cmake['version'] = '3.1'
        cmake['project'] = self.project['name']

        # Deduplicate includes while preserving order.
        cmake['incs'] = []
        for inc in self.project['incs']:
            if inc not in cmake['incs']:
                cmake['incs'].append(inc)

        # Files are grouped by their originating IAR/Keil project group
        # (e.g. 'data' -> DATA_SOURCES) instead of one flat SOURCES list,
        # so the generated CMakeLists.txt mirrors the project's own
        # organization. Only recognized source/header/assembly
        # extensions are kept; anything else is silently skipped, same
        # as the previous flat-list behavior.
        cmake['groups'] = []
        cmake['ass'] = []
        usedVars = {}
        for group in self.project.get('groups', []):
            files = []
            for file in group['files']:
                lower = file.lower()
                if lower.endswith(ASM_EXTENSIONS):
                    print('Assembly added ' + file)
                    cmake['ass'].append({'path': file})
                    files.append(file)
                elif lower.endswith(SOURCE_EXTENSIONS) or lower.endswith(HEADER_EXTENSIONS):
                    files.append(file)

            if not files:
                continue

            var = self._makeGroupVar(group['name'], usedVars)
            cmake['groups'].append({'name': group['name'] or 'Other', 'var': var, 'files': files})

        cmake['all_files'] = [f for g in cmake['groups'] for f in g['files']]

        cmake['cxx'] = 'false'

        cmake['c_flags'] = '-g -Wextra -Wshadow -Wimplicit-function-declaration -Wredundant-decls -Wmissing-prototypes -Wstrict-prototypes -fno-common -ffunction-sections -fdata-sections -MD -Wall -Wundef -mthumb ' + core + ' ' + fpu

        cmake['cxx_flags'] = '-Wextra -Wshadow -Wredundant-decls  -Weffc++ -fno-common -ffunction-sections -fdata-sections -MD -Wall -Wundef -mthumb ' + core + ' ' + fpu

        cmake['asm_flags'] = '-g -mthumb ' + core + ' ' + fpu #+ ' -x assembler-with-cpp'
        cmake['linker_flags'] = '-g -Wl,--gc-sections -Wl,-Map=' + cmake['project'] + '.map -mthumb ' + core + ' ' + fpu
        cmake['linker_path'] = ''

        linker_script = LINKER_SCRIPT_BY_FAMILY.get(family, '')
        if linker_script:
            self.linkerScript(linker_script, os.path.join(self.path, linker_script))
        else:
            print('WARNING: No linker script available for chip family '
                  '\'{}\'; CMakeLists.txt will not set one. Please add '
                  'one manually.'.format(family))
        cmake['linker_script'] = linker_script

        oocd_target = OOCD_TARGET_BY_FAMILY.get(family, '')
        if not oocd_target:
            print('WARNING: No OpenOCD target available for chip family '
                  '\'{}\'; the \'flash\' target will not be generated.'.format(family))
        cmake['oocd_target'] = oocd_target

        # Defines common to every build configuration are applied
        # unconditionally; defines unique to one configuration (e.g.
        # DEBUG vs. NDEBUG) are applied only when CMAKE_BUILD_TYPE
        # matches it. Project formats with only one configuration
        # (e.g. uVision) expose a flat 'defs' list instead and get no
        # per-config split.
        cmake['defines'] = list(self.project.get('defines_common', self.project.get('defs', [])))
        cmake['defines_by_config'] = self.project.get('defines_by_config', {})
        cmake['default_build_type'] = self.project.get('default_config', 'Debug')

        cmake['libs'] = []

        self.context['cmake'] = cmake

        abspath = os.path.abspath(os.path.join(self.path,'CMakeLists.txt'))
        self.generateFile('CMakeLists.txt', abspath)

        print ('Created file CMakeLists.txt [{}]'.format(abspath))

#    def generateFile (self, pathSrc, pathDst='', author='Pegasus', version='v1.0.0', licence='licence.txt', template_dir='../PegasusTemplates'):
    def generateFile (self, pathSrc, pathDst='', author='Pegasus', version='v1.0.0', licence='licence.txt', template_dir=TEMPLATE_DIR):
        
        if (pathDst == ''):
            pathDst = pathSrc
            
        self.context['file'] = os.path.basename(str(pathSrc))
        self.context['author'] = author
        self.context['date'] = datetime.date.today().strftime('%d, %b %Y')
        self.context['version'] = version
        self.context['licence'] = licence
        
        env = Environment(loader=FileSystemLoader(template_dir),trim_blocks=True,lstrip_blocks=True)
        template = env.get_template(str(pathSrc))
        
        generated_code = template.render(self.context)
            
        if platform.system() == 'Windows':    

            with open(pathDst, 'w') as f:
                f.write(generated_code)
        
        elif platform.system() == 'Linux':

            with open(pathDst, 'w') as f:
                f.write(generated_code)        
        else:
            # Different OS than Windows or Linux            
            pass
    
    def linkerScript(self,pathSrc, pathDst='',template_dir=TEMPLATE_DIR):
#    def linkerScript(self,pathSrc, pathDst='',template_dir='.../PegasusTemplates'):
                
        if (pathDst == ''):
            pathDst = pathSrc
            
        self.context['file'] = os.path.basename(str(pathSrc))
        self.context['flash'] = '64'
        self.context['ram'] = '8'        
        
        env = Environment(loader=FileSystemLoader(template_dir),trim_blocks=True,lstrip_blocks=True)
        template = env.get_template(str(pathSrc))
        
        generated_code = template.render(self.context)
            
        if platform.system() == 'Windows':    

            with open(pathDst, 'w') as f:
                f.write(generated_code)
        
        elif platform.system() == 'Linux':

            with open(pathDst, 'w') as f:
                f.write(generated_code)        
        else:
            # Different OS than Windows or Linux            
            pass
        
        
