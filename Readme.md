# Project converter for Embedded Projects

A lot of Embedded Projects use proprietary IDEs and build processes. This make any CI/CD painful. Therefore these simple python scripts allow conversion of existing projects into CMake and corresponding linker file for GCC toolchain. Currently supported are *IAR's ewp* and *ARM's KEIL uvprojx* project formats.

## Module description

- [cmake.py](cmake.py) - Cmake and linker file generation
- [converter.py](converter.py) - Argument parsing
- [ewpproject.py](ewpproject) - Parser for IAR's ewp file format
- [uvprojx.py](uvprojx.py) - Parser for ARM's KEIL uvprojx file format

## Prerequisites

This project is setup to run using [uv](https://docs.astral.sh/uv/) or you can pip install needed dependencies:

Install `python3` on your system run:
```shell
pip install Jinja2 lxml
```

## Usage

Convert project from IAR:
```
    uv run converter.py ewp <path to project root>
```
Convert project from ARM's KEIL:
```
    uv run converter.py uvprojx <path to project root>
```	

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct, and the process for submitting pull requests to us.

## Versioning

We use [SemVer](semver.org) for versioning.

## Authors

- Petr Hodina - *Initial work*
- David Gannerud

## License

The project is licensed under the [Apache License v2.0](https://www.apache.org/licenses/LICENSE-2.0) - see the [LICENSE.md](LICENSE.md) file for details.
