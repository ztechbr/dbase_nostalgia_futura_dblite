# Original MSX dBASE II disk analysis

Image type: FAT12, 720 KiB, 1440 sectors, 512 bytes per sector, 2 sectors per cluster.

The disk contains the dBASE II runtime for MSX-DOS. Important internal strings recovered from the executable/overlay identify:

- `dBASE II`
- `adapted for MSXDOS`
- `by Piet Habich`
- `july 1985`
- `dBASE II COPYRIGHT (C) 1982 BY RATLIFF SOFTWARE PRODUCTION, INCORPORATED`

The supplied help file identifies itself as help text version 1.12 for dBASE II v2.4 and enumerates the language commands used as the behavioral reference for the Python command processor.

The Python rewrite was built from the observable file formats, command language and behavior. It does not contain or execute the supplied copyrighted COM/OVL binaries.
