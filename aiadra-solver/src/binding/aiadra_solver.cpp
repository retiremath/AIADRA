// SPDX-License-Identifier: AGPL-3.0-only
// SPDX-FileCopyrightText: 2026 AIADRA
// AIADRA thin pybind11 binding over the extracted PlaneGCS (SK-B Gate 1/2 spike).
//
// Deliberately DUMB: parameter/entity/constraint registration + solve/diagnose.
// All corpus translation, classification, completion policy, and DTO emission
// live in the Python harness where they are testable and candidate-neutral.
// Entities live in std::deque so double*/Point references stay stable.

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include <deque>
#include <stdexcept>
#include <string>
#include <vector>

#ifdef _WIN32
#include <windows.h>
#endif

#include "GCS.h"

namespace py = pybind11;

// ---- DLL-side compatibility handshake (arc 20260717-2 Codex16 B2) ----
// The replacement proof keeps THIS pyd unchanged while planegcs.dll is
// swapped, so contract/ABI identity must be reported by the DLL itself —
// a rebuilt LGPL replacement has different PE bytes while implementing the
// same declared ABI. Resolved by NAME from the already-loaded module (never
// an arbitrary PATH search); every failure is loud and specific so the
// Python loader can refuse with a typed error.
#ifdef _WIN32
static HMODULE loaded_planegcs()
{
    HMODULE mod = GetModuleHandleW(L"planegcs.dll");
    if (mod == nullptr) {
        throw std::runtime_error(
            "aiadra_solver: planegcs.dll is not loaded in this process -- "
            "the binding was imported without its native solver artifact");
    }
    return mod;
}
#endif

static std::string dll_handshake()
{
#ifdef _WIN32
    HMODULE mod = loaded_planegcs();
    using HandshakeFn = const char* (*)(void);
    auto fn = reinterpret_cast<HandshakeFn>(
        reinterpret_cast<void*>(GetProcAddress(mod, "aiadra_planegcs_handshake")));
    if (fn == nullptr) {
        throw std::runtime_error(
            "aiadra_solver: the loaded planegcs.dll exports no "
            "aiadra_planegcs_handshake -- it cannot identify its supported "
            "solver contract; refuse it (a conforming replacement build must "
            "implement the handshake export)");
    }
    const char* declared = fn();
    if (declared == nullptr || declared[0] == '\0') {
        throw std::runtime_error(
            "aiadra_solver: planegcs.dll returned an empty handshake -- "
            "it cannot identify its supported solver contract; refuse it");
    }
    return std::string(declared);
#else
    throw std::runtime_error(
        "aiadra_solver: the DLL handshake is implemented for Windows only "
        "in this build (cp312-win_amd64)");
#endif
}

// ---- DLL origin (arc 20260717-2 Codex17 B1) ----
// The handshake is a semantic declaration; THIS reports which file on disk
// actually made it. GetModuleFileNameW on the SAME HMODULE the handshake
// uses lets the Python loader compare the loaded module's canonical path to
// the explicitly selected dist/planegcs.dll and refuse a conforming but
// wrong-origin/preloaded same-name DLL.
static std::wstring dll_origin_w()
{
#ifdef _WIN32
    HMODULE mod = loaded_planegcs();
    std::wstring path(32768, L'\0');
    DWORD n = GetModuleFileNameW(mod, path.data(),
                                 static_cast<DWORD>(path.size()));
    if (n == 0 || n >= path.size()) {
        throw std::runtime_error(
            "aiadra_solver: GetModuleFileNameW failed for the loaded "
            "planegcs.dll -- its origin cannot be identified; refuse it");
    }
    path.resize(n);
    return path;
#else
    throw std::runtime_error(
        "aiadra_solver: the DLL origin query is implemented for Windows "
        "only in this build (cp312-win_amd64)");
#endif
}

struct PySystem
{
    GCS::System sys;
    std::deque<double> params;
    std::deque<GCS::Point> points;
    std::deque<GCS::Line> lines;
    std::deque<GCS::Circle> circles;
    std::deque<GCS::Arc> arcs;
    std::vector<double*> unknowns;

    double* P(int i) { return &params.at(static_cast<size_t>(i)); }

    int add_param(double v, bool free_param)
    {
        params.push_back(v);
        double* p = &params.back();
        if (free_param) {
            unknowns.push_back(p);
        }
        return static_cast<int>(params.size()) - 1;
    }

    int add_point(int ix, int iy)
    {
        GCS::Point p;
        p.x = P(ix);
        p.y = P(iy);
        points.push_back(p);
        return static_cast<int>(points.size()) - 1;
    }

    int add_line(int ip1, int ip2)
    {
        GCS::Line l;
        l.p1 = points.at(ip1);
        l.p2 = points.at(ip2);
        lines.push_back(l);
        return static_cast<int>(lines.size()) - 1;
    }

    int add_circle(int icenter, int irad)
    {
        GCS::Circle c;
        c.center = points.at(icenter);
        c.rad = P(irad);
        circles.push_back(c);
        return static_cast<int>(circles.size()) - 1;
    }

    // start/end points are REAL planegcs points; arc_rules ties them to
    // center/radius/angles (tag 0 = internal, never reported as a user fact).
    int add_arc(int icenter, int istart, int iend, int istartangle, int iendangle, int irad)
    {
        GCS::Arc a;
        a.center = points.at(icenter);
        a.start = points.at(istart);
        a.end = points.at(iend);
        a.startAngle = P(istartangle);
        a.endAngle = P(iendangle);
        a.rad = P(irad);
        arcs.push_back(a);
        sys.addConstraintArcRules(arcs.back(), 0);
        return static_cast<int>(arcs.size()) - 1;
    }

    // ---- constraints (tag = harness-side fact index, must be > 0) ----
    void horizontal(int il, int tag) { sys.addConstraintHorizontal(lines.at(il), tag); }
    void vertical(int il, int tag) { sys.addConstraintVertical(lines.at(il), tag); }
    void parallel(int il1, int il2, int tag)
    {
        sys.addConstraintParallel(lines.at(il1), lines.at(il2), tag);
    }
    void perpendicular(int il1, int il2, int tag)
    {
        sys.addConstraintPerpendicular(lines.at(il1), lines.at(il2), tag);
    }
    void l2l_angle(int il1, int il2, int iangle, int tag)
    {
        sys.addConstraintL2LAngle(lines.at(il1), lines.at(il2), P(iangle), tag);
    }
    void p2p_coincident(int ip1, int ip2, int tag)
    {
        sys.addConstraintP2PCoincident(points.at(ip1), points.at(ip2), tag);
    }
    void point_on_line(int ip, int il, int tag)
    {
        sys.addConstraintPointOnLine(points.at(ip), lines.at(il), tag);
    }
    void point_on_circle(int ip, int ic, int tag)
    {
        sys.addConstraintPointOnCircle(points.at(ip), circles.at(ic), tag);
    }
    void point_on_arc(int ip, int ia, int tag)
    {
        sys.addConstraintPointOnArc(points.at(ip), arcs.at(ia), tag);
    }
    void p2p_distance(int ip1, int ip2, int idist, int tag)
    {
        sys.addConstraintP2PDistance(points.at(ip1), points.at(ip2), P(idist), tag);
    }
    void p2l_distance(int ip, int il, int idist, int tag)
    {
        sys.addConstraintP2LDistance(points.at(ip), lines.at(il), P(idist), tag);
    }
    void tangent_lc(int il, int ic, bool ccw, int tag)
    {
        sys.addConstraintTangent(lines.at(il), circles.at(ic), ccw, tag);
    }
    void tangent_la(int il, int ia, bool ccw, int tag)
    {
        sys.addConstraintTangent(lines.at(il), arcs.at(ia), ccw, tag);
    }
    void tangent_cc(int ic1, int ic2, int tag)
    {
        sys.addConstraintTangent(circles.at(ic1), circles.at(ic2), tag);
    }
    void tangent_ca(int ic, int ia, int tag)
    {
        sys.addConstraintTangent(circles.at(ic), arcs.at(ia), tag);
    }
    void tangent_aa(int ia1, int ia2, int tag)
    {
        sys.addConstraintTangent(arcs.at(ia1), arcs.at(ia2), tag);
    }
    // endpoint tangency (corpus tangent_at): angle between the two curves at a
    // point; the harness pins the angle param (0 or pi snapshot from the seed).
    void angle_via_point_la(int il, int ia, int ip, int iangle, int tag)
    {
        sys.addConstraintAngleViaPoint(lines.at(il), arcs.at(ia), points.at(ip), P(iangle), tag);
    }
    void equal_params(int i1, int i2, int tag) { sys.addConstraintEqual(P(i1), P(i2), tag); }
    void equal_length(int il1, int il2, int tag)
    {
        sys.addConstraintEqualLength(lines.at(il1), lines.at(il2), tag);
    }
    void equal_radius_cc(int ic1, int ic2, int tag)
    {
        sys.addConstraintEqualRadius(circles.at(ic1), circles.at(ic2), tag);
    }
    void equal_radius_ca(int ic, int ia, int tag)
    {
        sys.addConstraintEqualRadius(circles.at(ic), arcs.at(ia), tag);
    }
    void equal_radius_aa(int ia1, int ia2, int tag)
    {
        sys.addConstraintEqualRadius(arcs.at(ia1), arcs.at(ia2), tag);
    }
    void circle_radius(int ic, int ir, int tag)
    {
        sys.addConstraintCircleRadius(circles.at(ic), P(ir), tag);
    }
    void arc_radius(int ia, int ir, int tag)
    {
        sys.addConstraintArcRadius(arcs.at(ia), P(ir), tag);
    }
    void circle_diameter(int ic, int id, int tag)
    {
        sys.addConstraintCircleDiameter(circles.at(ic), P(id), tag);
    }
    void arc_diameter(int ia, int id, int tag)
    {
        sys.addConstraintArcDiameter(arcs.at(ia), P(id), tag);
    }

    // ---- lifecycle ----
    void declare_unknowns()
    {
        GCS::VEC_pD vec(unknowns.begin(), unknowns.end());
        sys.declareUnknowns(vec);
    }
    void init_solution() { sys.initSolution(); }
    void set_max_iter(int n) { sys.maxIter = n; }
    int get_max_iter() const { return sys.maxIter; }
    double get_convergence() const { return sys.convergence; }
    int solve(int alg, bool is_fine)
    {
        return sys.solve(is_fine, static_cast<GCS::Algorithm>(alg));
    }
    void apply() { sys.applySolution(); }
    double get_param(int i) { return *P(i); }
    void set_param(int i, double v) { *P(i) = v; }
    double constraint_error(int tag) { return sys.calculateConstraintErrorByTag(tag); }
    int diagnose(int alg) { return sys.diagnose(static_cast<GCS::Algorithm>(alg)); }
    int dofs() const { return sys.dofsNumber(); }
    std::vector<int> conflicting() const
    {
        GCS::VEC_I v;
        sys.getConflicting(v);
        return v;
    }
    std::vector<int> redundant() const
    {
        GCS::VEC_I v;
        sys.getRedundant(v);
        return v;
    }
};

PYBIND11_MODULE(aiadra_solver, m)
{
    m.doc() = "AIADRA thin binding over extracted PlaneGCS (SK-B spike)";
    // Codex16 B2: the binding's OWN declared identity (compile-time facts of
    // this pyd) + the runtime query of the DLL's declaration. The Python
    // loader must verify BOTH and fail closed on any mismatch.
    m.attr("BINDING_ABI") = "cp312-win_amd64";
    m.attr("BINDING_SOLVER_CONTRACT") = "skb-c0";
    m.def("dll_handshake", &dll_handshake,
          "Return the loaded planegcs.dll's own ABI/contract declaration "
          "(raises when the DLL cannot identify its supported contract)");
    m.def("dll_origin", &dll_origin_w,
          "Return the absolute filesystem path of the loaded planegcs.dll "
          "(Codex17 B1: the loader must prove the handshaking module IS the "
          "explicitly selected artifact, not a same-named preload)");
    py::class_<PySystem>(m, "System")
        .def(py::init<>())
        .def("add_param", &PySystem::add_param, py::arg("value"), py::arg("free_param") = true)
        .def("add_point", &PySystem::add_point)
        .def("add_line", &PySystem::add_line)
        .def("add_circle", &PySystem::add_circle)
        .def("add_arc", &PySystem::add_arc)
        .def("horizontal", &PySystem::horizontal)
        .def("vertical", &PySystem::vertical)
        .def("parallel", &PySystem::parallel)
        .def("perpendicular", &PySystem::perpendicular)
        .def("l2l_angle", &PySystem::l2l_angle)
        .def("p2p_coincident", &PySystem::p2p_coincident)
        .def("point_on_line", &PySystem::point_on_line)
        .def("point_on_circle", &PySystem::point_on_circle)
        .def("point_on_arc", &PySystem::point_on_arc)
        .def("p2p_distance", &PySystem::p2p_distance)
        .def("p2l_distance", &PySystem::p2l_distance)
        .def("tangent_lc", &PySystem::tangent_lc)
        .def("tangent_la", &PySystem::tangent_la)
        .def("tangent_cc", &PySystem::tangent_cc)
        .def("tangent_ca", &PySystem::tangent_ca)
        .def("tangent_aa", &PySystem::tangent_aa)
        .def("angle_via_point_la", &PySystem::angle_via_point_la)
        .def("equal_params", &PySystem::equal_params)
        .def("equal_length", &PySystem::equal_length)
        .def("equal_radius_cc", &PySystem::equal_radius_cc)
        .def("equal_radius_ca", &PySystem::equal_radius_ca)
        .def("equal_radius_aa", &PySystem::equal_radius_aa)
        .def("circle_radius", &PySystem::circle_radius)
        .def("arc_radius", &PySystem::arc_radius)
        .def("circle_diameter", &PySystem::circle_diameter)
        .def("arc_diameter", &PySystem::arc_diameter)
        .def("declare_unknowns", &PySystem::declare_unknowns)
        .def("init_solution", &PySystem::init_solution)
        .def("set_max_iter", &PySystem::set_max_iter)
        .def("get_max_iter", &PySystem::get_max_iter)
        .def("get_convergence", &PySystem::get_convergence)
        .def("solve", &PySystem::solve, py::arg("alg") = 2, py::arg("is_fine") = true)
        .def("apply", &PySystem::apply)
        .def("get_param", &PySystem::get_param)
        .def("set_param", &PySystem::set_param)
        .def("constraint_error", &PySystem::constraint_error)
        .def("diagnose", &PySystem::diagnose, py::arg("alg") = 2)
        .def("dofs", &PySystem::dofs)
        .def("conflicting", &PySystem::conflicting)
        .def("redundant", &PySystem::redundant);
}
