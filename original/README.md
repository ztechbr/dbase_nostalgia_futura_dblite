# dBASE II 2.4 - Python rewrite from the MSX-DOS disk image

This project is a native Python rewrite of the dBASE II environment found on the supplied `dBASE II.dsk` image.

It does not emulate the Z80 CPU, CP/M, MSX BIOS, MSX-DOS, `DBASE.COM`, or `DBASEOVR.COM`. The Python code itself implements the database engine and command processor.

## Source image inventory

The 720 KiB FAT12 disk contained:

- DBASE.COM - 2,048 bytes
- DBASEOVR.COM - 40,192 bytes
- DBASEMSG.TXT - 52,736 bytes
- D40.OVL - 19,456 bytes
- D80.OVL - 19,456 bytes
- DBKRST.OVL - 512 bytes
- S80.OVL - 28,672 bytes
- DATETEST.HEX - 640 bytes
- AUTOEXEC.BAT
- COMMAND.COM
- MSXDOS.SYS

The executable identifies itself as dBASE II adapted for MSX-DOS by Piet Habich, July 1985. `DBASEOVR.COM` identifies the core as dBASE II version 2.x and carries the original command/error strings.

## What is implemented as real functionality

- Native dBASE II `.DBF` read and write
- dBASE II version byte `0x02`
- Fixed 521-byte dBASE II header
- Up to 32 fields
- Character, Numeric and Logical fields
- Physical record persistence
- Logical deletion flag and `PACK`
- PRIMARY and SECONDARY work areas
- Current record pointer, EOF behavior, GO/GOTO and SKIP
- Memory variables
- `.MEM` persistence
- Expression parser
- `.AND.`, `.OR.`, `.NOT.`
- comparison operators
- arithmetic and string concatenation
- dBASE II functions including `CHR`, `DATE`, `INT`, `LEN`, `RANK`, `STR`, `VAL`, `TRIM`, `TYPE`, `FILE`, `AT`
- `USE`
- `CREATE`
- `APPEND`, `APPEND BLANK`, `APPEND FROM`
- `LIST`, `DISPLAY`, structure, memory, status and files
- `REPLACE`
- `DELETE`, `RECALL`, `PACK`
- `EDIT`, `CHANGE`, `INSERT`, `BROWSE`
- `COUNT`, `SUM`
- `LOCATE`, `CONTINUE`
- `INDEX`, `REINDEX`, `FIND`
- `SORT`
- `COPY`
- `TOTAL`
- `JOIN`
- `UPDATE`
- `STORE`, `RELEASE`, `SAVE`, `RESTORE`
- `SELECT PRIMARY`, `SELECT SECONDARY`
- `SET` state including DELETED, EXACT, FILTER and console settings
- `.CMD` execution
- `IF / ELSE / ENDIF`
- `DO WHILE / ENDDO`
- `DO CASE / CASE / OTHERWISE / ENDCASE`
- `TEXT / ENDTEXT`
- `DO <file>`
- `ACCEPT`, `INPUT`, `WAIT`
- `@ row,col SAY ... GET ...` plus `READ` using ANSI terminal positioning
- `RENAME`, file deletion and `QUIT`

## Deliberate portability changes

The DBF format is native dBASE II and byte-level compatible with the documented dBASE II table structure.

The Python runtime does not execute the original machine-code overlays. Screen behavior is implemented through a modern terminal. Full-screen MSX-specific cursor and printer driver code has no meaning outside MSX-DOS and was replaced by equivalent terminal I/O.

Indexes are real and persistent, but the Python port currently stores its index structure in the requested `.NDX` file as deterministic JSON rather than recreating the original dBASE II B+tree byte layout. `INDEX`, `REINDEX`, and `FIND` are functional inside this Python implementation, but an index generated here is not intended to be opened by the 1985 executable.

`REPORT FORM` output is executed against real records, but binary `.FRM` form compatibility is not reconstructed because no `.FRM` sample is present on the supplied disk image.

These are compatibility boundaries, not simulated database behavior.

## Run

```bash
python main.py --cwd ./data
```

Or:

```bash
python main.py --cwd ./data -c "USE CUSTOMERS" -c "LIST ALL"
```

Execute a command file:

```bash
python main.py --cwd ./data --cmd STARTUP.CMD
```

## Example

```text
. USE PEOPLE
. APPEND BLANK
. REPLACE NAME WITH 'RODRIGO', AGE WITH 52
. LIST ALL
. INDEX ON NAME TO PEOPLE
. FIND RODRIGO
. DISPLAY
. DELETE
. PACK
```

## Python API

```python
from dbase2py import DBase2Table, Field, DBaseEngine

t = DBase2Table.create(
    "PEOPLE.DBF",
    [Field("NAME", "C", 30), Field("AGE", "N", 3)]
)
t.append({"NAME": "RODRIGO", "AGE": 52})
t.save()

engine = DBaseEngine(".")
engine.execute("USE PEOPLE")
engine.execute("LIST ALL")
```

## Tests

```bash
PYTHONPATH=. pytest -q
```

The included automated tests cover native DBF round-trip, persistent update/delete/pack/index/memory behavior and `.CMD` control flow.
