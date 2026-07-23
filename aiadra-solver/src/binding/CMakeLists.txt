# SPDX-License-Identifier: AGPL-3.0-only
# SPDX-FileCopyrightText: 2026 AIADRA
# AIADRA SK-B spike: planegcs.dll (separate, replaceable — the Gate 2 artifact
# form) + aiadra_solver.pyd (thin AIADRA-owned pybind11 binding linking it).
cmake_minimum_required(VERSION 3.20)
project(aiadra_planegcs_spike CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_WINDOWS_EXPORT_ALL_SYMBOLS ON)

get_filename_component(SPIKE_ROOT ${CMAKE_CURRENT_SOURCE_DIR} DIRECTORY)

file(GLOB PLANEGCS_SRC ${SPIKE_ROOT}/extraction/src/App/planegcs/*.cpp)
# The DLL-side compatibility handshake (Codex16 B2): the replaceable artifact
# itself declares its ABI + solver contract; the binding fails closed on a DLL
# that cannot identify what it executes. LGPL-2.1-or-later like the DLL.
list(APPEND PLANEGCS_SRC ${SPIKE_ROOT}/handshake/aiadra_handshake.cpp)
add_library(planegcs SHARED ${PLANEGCS_SRC})
target_include_directories(planegcs PUBLIC
    ${SPIKE_ROOT}/extraction/src/App/planegcs
    ${SPIKE_ROOT}/shims
    ${SPIKE_ROOT}/eigen
    ${SPIKE_ROOT})            # boost/ lives at the spike root
target_compile_options(planegcs PRIVATE /bigobj /EHsc /permissive-)
# Sketcher_EXPORTS makes SketcherExport = dllexport inside the DLL build; the
# binding (without it) sees dllimport -- the standard pairing.
target_compile_definitions(planegcs PRIVATE _USE_MATH_DEFINES NOMINMAX Sketcher_EXPORTS)

find_package(pybind11 REQUIRED CONFIG)
pybind11_add_module(aiadra_solver ${CMAKE_CURRENT_SOURCE_DIR}/aiadra_solver.cpp)
target_link_libraries(aiadra_solver PRIVATE planegcs)
target_compile_options(aiadra_solver PRIVATE /bigobj /EHsc /permissive-)
target_compile_definitions(aiadra_solver PRIVATE _USE_MATH_DEFINES NOMINMAX)
