// SPDX-License-Identifier: LGPL-2.1-or-later
// SPDX-FileCopyrightText: 2026 AIADRA (extraction completion shim for PlaneGCS)
// AIADRA extraction shim: export/import macros normally supplied by FreeCAD.
#pragma once
#ifndef FREECAD_DECL_EXPORT
#define FREECAD_DECL_EXPORT __declspec(dllexport)
#define FREECAD_DECL_IMPORT __declspec(dllimport)
#endif
