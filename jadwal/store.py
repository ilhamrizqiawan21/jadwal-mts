"""Penyimpan status aplikasi: proyek aktif, undo/redo, simpan otomatis."""
from __future__ import annotations

import copy
import os
from contextlib import contextmanager
from typing import Callable, List, Optional

from . import checks, model as M


class Store:
    def __init__(self, proyek: M.Proyek, path: Optional[str] = None):
        self.p = proyek
        self.path = path
        self.dirty = False
        self.undo_stack: List[dict] = []
        self.redo_stack: List[dict] = []
        self.listeners: List[Callable[[], None]] = []
        self.hasil = checks.periksa(self.p)

    # ------------------------------------------------------------- perubahan
    def _snap(self) -> dict:
        return self.p.to_dict()

    def _notify(self):
        self.hasil = checks.periksa(self.p)
        for f in list(self.listeners):
            f()

    @contextmanager
    def edit(self):
        """Bungkus perubahan agar bisa di-undo: `with store.edit() as p: ...`"""
        before = self._snap()
        try:
            yield self.p
        except BaseException:
            # perubahan setengah jadi dibatalkan agar data dan tampilan tetap konsisten
            self.p = M.Proyek.from_dict(copy.deepcopy(before))
            self._notify()
            raise
        self.undo_stack.append(before)
        del self.undo_stack[:-100]
        self.redo_stack.clear()
        self.dirty = True
        self._notify()

    def undo(self) -> bool:
        if not self.undo_stack:
            return False
        self.redo_stack.append(self._snap())
        self.p = M.Proyek.from_dict(copy.deepcopy(self.undo_stack.pop()))
        self.dirty = True
        self._notify()
        return True

    def redo(self) -> bool:
        if not self.redo_stack:
            return False
        self.undo_stack.append(self._snap())
        self.p = M.Proyek.from_dict(copy.deepcopy(self.redo_stack.pop()))
        self.dirty = True
        self._notify()
        return True

    def replace(self, proyek: M.Proyek, path: Optional[str]):
        self.p, self.path = proyek, path
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.dirty = False
        self._notify()

    # ----------------------------------------------------------------- simpan
    def save(self, path: Optional[str] = None):
        path = path or self.path
        if not path:
            raise ValueError("path belum ditentukan")
        M.save(self.p, path)
        self.path = path
        self.dirty = False
        for f in list(self.listeners):
            f()

    @property
    def nama_berkas(self) -> str:
        return os.path.basename(self.path) if self.path else "(belum disimpan)"
