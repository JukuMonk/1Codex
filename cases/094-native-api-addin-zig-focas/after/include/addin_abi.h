// ФРЕГАТ ПУЛЬС: единственная правка заголовков Native API 1С (остальное — как в примере 1С).
//
// Платформа 1С под Windows собрана MSVC: виртуальный деструктор занимает в vtable ОДНУ ячейку.
// clang/MinGW (Itanium C++ ABI, сборка zig -target x86_64-windows-gnu) ставит ДВЕ (complete + deleting) —
// все методы интерфейса после деструктора сдвинулись бы на ячейку, и 1С вызывала бы не те функции.
// Поэтому под Windows не-MSVC вместо деструктора базового интерфейса — заглушка в одну ячейку
// (платформа деструктор интерфейса не вызывает: объект удаляет наш DestroyObject), у производного
// интерфейса — ничего (в MSVC его деструктор занимает ячейку базового, новой не добавляет).
// Под Linux платформа собрана gcc (тот же Itanium ABI) — деструкторы как в оригинале.
#ifndef FREGAT_ADDIN_ABI_H
#define FREGAT_ADDIN_ABI_H

#if defined(_WIN32) && !defined(_MSC_VER)
#define ADDIN_VDTOR(C) virtual void __stdcall msvc_dtor_slot_##C(unsigned int) {}
#define ADDIN_VDTOR_DERIVED(C)
#else
#define ADDIN_VDTOR(C) virtual ~C() {}
#define ADDIN_VDTOR_DERIVED(C) virtual ~C() {}
#endif

#endif
