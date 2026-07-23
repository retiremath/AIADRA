// SPDX-License-Identifier: LGPL-2.1-or-later
// SPDX-FileCopyrightText: 2026 AIADRA (extraction completion shim for PlaneGCS)
// AIADRA extraction shim: no-op console satisfying planegcs' Base::Console()
// logging calls. Deliberately silent (deterministic gate output).
#pragma once
namespace Base
{
class ConsoleSingleton
{
public:
    template<typename... Args> void log(const char*, Args&&...) {}
    template<typename... Args> void warning(const char*, Args&&...) {}
    template<typename... Args> void message(const char*, Args&&...) {}
    template<typename... Args> void error(const char*, Args&&...) {}
    template<typename... Args> void developerWarning(const char*, Args&&...) {}
    template<typename... Args> void developerError(const char*, Args&&...) {}
};
inline ConsoleSingleton& Console()
{
    static ConsoleSingleton c;
    return c;
}
class TimeElapsed
{
public:
    static double diffTimeF(const TimeElapsed&, const TimeElapsed&) { return 0.0; }
};
}  // namespace Base
