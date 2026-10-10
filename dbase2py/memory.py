"""Variáveis com escopo dinâmico e referências para DO ... WITH."""
from collections.abc import MutableMapping
from dataclasses import dataclass
from fnmatch import fnmatchcase
from .syntax import XBaseError

UNSET=object()


class XArray(list):
    """Array do dBASE IV/Clipper/FoxPro: listas aninhadas com índices a partir de 1."""
    @classmethod
    def build(cls,dims,fill=False):
        if not dims: return fill
        return cls(cls.build(dims[1:],fill) if len(dims)>1 else fill for _ in range(int(dims[0])))


@dataclass
class Cell:
    value: object = UNSET


class Memory(MutableMapping):
    def __init__(self):
        self.public={}
        self.frames=[{}]

    def cell(self,name,create=False):
        name=name.upper()
        for frame in reversed(self.frames):
            if name in frame: return frame[name]
        if name in self.public: return self.public[name]
        if create:
            self.frames[-1][name]=Cell(); return self.frames[-1][name]
        raise KeyError(name)

    def __getitem__(self,name):
        cell=self.cell(name)
        if cell.value is UNSET: raise KeyError(name)
        return cell.value

    def __setitem__(self,name,value): self.cell(name,True).value=value

    def __delitem__(self,name):
        name=name.upper()
        for frame in reversed(self.frames):
            if name in frame: del frame[name]; return
        del self.public[name]

    def __iter__(self):
        values={**self.public}
        for frame in self.frames: values.update(frame)
        return iter(k for k,v in values.items() if v.value is not UNSET)

    def __len__(self): return len(list(iter(self)))

    def push(self): self.frames.append({})
    def pop(self): self.frames.pop()

    def private(self,names):
        for name in names: self.frames[-1][name.upper()]=Cell()

    def declare_public(self,names):
        for name in names:
            name=name.upper()
            if name not in self.public: self.public[name]=Cell(False)

    def bind(self,name,cell): self.frames[-1][name.upper()]=cell

    def names(self,tail):
        import re
        m=re.fullmatch(r'ALL(?:\s+(LIKE|EXCEPT)\s+(.+))?',tail,re.I)
        if m:
            values=list(self)
            if m[1]: values=[n for n in values if fnmatchcase(n,m[2].upper()) == (m[1].upper()=='LIKE')]
            return values
        from .syntax import split
        names=split(tail)
        if not all(re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*',n) for n in names): raise XBaseError('Lista de variáveis inválida.')
        return names
