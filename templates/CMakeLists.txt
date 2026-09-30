# CMake minimum version
cmake_minimum_required (VERSION {{ cmake.version }})

# Project Infomation
project ({{ cmake.project }})
enable_language(ASM)
enable_language(C)
{% if cmake.cxx == 'true' %}
enable_language(CXX)
{% endif %}

# Reset output path
set (EXECUTABLE_OUTPUT_PATH ${CMAKE_BINARY_DIR}/bin)
set (LIBRARY_OUTPUT_PATH ${CMAKE_BINARY_DIR}/lib)

# STDLIB
set (CMAKE_SHARED_LIBRARY_LINK_C_FLAGS)

# Source files, grouped to mirror the project's own organization
# (headers are listed too, only for IDE/source_group display)
{% for group in cmake.groups %}
set ({{ group.var }}
{% for f in group.files %}
    "{{ f }}"
{% endfor %}
)
{% endfor %}

set (ALL_SOURCES
{% for group in cmake.groups %}
    {{ '${' ~ group.var ~ '}' }}
{% endfor %}
)

{% for as in cmake.ass %}
set_source_files_properties("{{ as.path }}" PROPERTIES COMPILE_FLAGS "-x assembler-with-cpp")
{% endfor %}

set(CROSS_TARGET_TRIPLET "arm-none-eabi-")

# CC AR LD AS
set(CMAKE_C_COMPILER "${CROSS_TARGET_TRIPLET}gcc")
{% if cmake.cxx == 'true' %}
set(CMAKE_CXX_COMPILER "${CROSS_TARGET_TRIPLET}g++")
{% endif %}
set(CMAKE_ASM_COMPILER "${CROSS_TARGET_TRIPLET}gcc")

# CFLAGS
set (CMAKE_C_FLAGS "{{ cmake.c_flags }}" CACHE INTERNAL "c compiler flags")

# CXXFLAGS
set (CMAKE_CXX_FLAGS "{{ cmake.cxx_flags }}" CACHE INTERNAL "cxx compiler flags")

# ASMFLAGS
set (CMAKE_ASM_FLAGS "{{ cmake.asm_flags }}" CACHE INTERNAL "asm compiler flags")

# LDFLAGS
set (CMAKE_EXE_LINKER_FLAGS "{{ cmake.linker_flags }}" CACHE INTERNAL "executable linker flags")
{% if cmake.linker_script %}
set (CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -T ${CMAKE_SOURCE_DIR}/{{ cmake.linker_script }} -L {{ cmake.linker_path }}")
{% else %}
# WARNING: no linker script could be determined for this chip; add one manually, e.g.:
# set (CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} -T ${CMAKE_SOURCE_DIR}/<your_linker_script>.ld -L {{ cmake.linker_path }}")
{% endif %}

{% for lib in cmake.libs %}
# Load the the extern library
set ({{ lib.name }} ${CMAKE_SOURCE_DIR}/{{ lib.path }}/{{ lib.name }}.a)
#add_library ({{ lib.name }} STATIC IMPORTED)
#set_property ({{ lib.name }} PROPERTIES IMPORTED_LOCATION ${CMAKE_SOURCE_DIR}/{{ lib.path }}/{{ lib.name }}.a)
{% endfor %}

# Group files in IDEs (Visual Studio, CLion, Xcode) to match the original project's groups
{% for group in cmake.groups %}
source_group("{{ group.name }}" FILES {{ '${' ~ group.var ~ '}' }})
{% endfor %}

# Generate the target
add_executable (${CMAKE_PROJECT_NAME}.elf ${ALL_SOURCES})

target_include_directories (${CMAKE_PROJECT_NAME}.elf PRIVATE
{% for inc in cmake.incs %}
    "{{ inc }}"
{% endfor %}
)

target_compile_definitions (${CMAKE_PROJECT_NAME}.elf PRIVATE
{% for define in cmake.defines %}
    "{{ define }}"
{% endfor %}
)

# Link the library to the target
target_link_libraries (${CMAKE_PROJECT_NAME}.elf {% for lib in cmake.libs %} {{ lib.name }} {% endfor %})

# Generate the binary file
add_custom_target (${CMAKE_PROJECT_NAME}.bin ALL arm-none-eabi-objcopy -Obinary "${EXECUTABLE_OUTPUT_PATH}/${CMAKE_PROJECT_NAME}.elf" "${EXECUTABLE_OUTPUT_PATH}/${CMAKE_PROJECT_NAME}.bin" DEPENDS ${EXECUTABLE_OUTPUT_PATH}/${CMAKE_PROJECT_NAME}.elf)

# Generate the hex file
add_custom_target (${CMAKE_PROJECT_NAME}.hex ALL arm-none-eabi-objcopy -Oihex "${EXECUTABLE_OUTPUT_PATH}/${CMAKE_PROJECT_NAME}.elf" "${EXECUTABLE_OUTPUT_PATH}/${CMAKE_PROJECT_NAME}.hex" DEPENDS ${EXECUTABLE_OUTPUT_PATH}/${CMAKE_PROJECT_NAME}.elf)

# Echo the size Infomation
add_custom_target (size ALL arm-none-eabi-size "${EXECUTABLE_OUTPUT_PATH}/${CMAKE_PROJECT_NAME}.elf" DEPENDS ${EXECUTABLE_OUTPUT_PATH}/${CMAKE_PROJECT_NAME}.elf)

{% if cmake.oocd_target %}
# Make flash to the board by st-link
add_custom_target (flash COMMAND st-flash write ${EXECUTABLE_OUTPUT_PATH}/${CMAKE_PROJECT_NAME}.bin 0x8000000)
{% else %}
# WARNING: no OpenOCD/flash target could be determined for this chip; add one manually.
{% endif %}

# Make clean-all
add_custom_target (clean-all COMMAND rm -rf ${CMAKE_BINARY_DIR}/*)
