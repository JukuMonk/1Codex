// Внешняя компонента 1С (Native API) «ФРЕГАТ ПУЛЬС: опрос ЧПУ» — объект AddIn.<Имя>.CNC.
// Только связь: подключиться к ЧПУ, прочитать, вернуть JSON. Расписание, хранение, состояния — в BSL
// (общий модуль пульс_ОпросЧПУ). В ЧПУ ничего не пишет: из FOCAS берутся только функции чтения (focas.h).
//
//   ЗагрузитьБиблиотеку(Путь) → Булево   Fwlib64.dll заказчика (или подставная) — динамически, не входит в поставку
//   Очистить()                          список станков пуст
//   ДобавитьСтанок(Ид, Адрес, Порт, ТаймаутМс)
//   ПрочитатьВсе() → Строка (JSON)      все станки ПАРАЛЛЕЛЬНО, у каждого свой таймаут
//   Пауза(Мс)                           в 8.3.21 у встроенного языка нет «спать»
//   Версия, ПоследняяОшибка, БиблиотекаЗагружена — свойства (только чтение)
//
// Дескриптор FOCAS открывается и закрывается внутри одного опроса и одного потока: у ЧПУ мало сетевых сессий,
// утечка дескрипторов при обрывах — известная беда FOCAS; цена — TCP-соединение раз в цикл (единицы мс в ЛВС).
#include "include/ComponentBase.h"
#include "include/AddInDefBase.h"
#include "include/IMemoryManager.h"
#include "focas.h"

#include <string>
#include <vector>
#include <thread>
#include <chrono>
#include <cstring>
#include <cstdio>

#ifdef _WIN32
#include <windows.h>
#define EXPORT __declspec(dllexport)
typedef HMODULE ДескрипторБиблиотеки;
#else
#include <dlfcn.h>
#define EXPORT __attribute__((visibility("default")))
typedef void* ДескрипторБиблиотеки;
#endif

#define ВЕРСИЯ "1.0.0"

typedef std::u16string wstr16;   // WCHAR_T — 2 байта на обеих ОС; basic_string<uint16_t> libc++ не умеет

namespace {

// --- строки: UTF-16 (WCHAR_T — 2 байта и под Windows, и под Linux) ↔ UTF-8
wstr16 в_utf16(const std::string& s) {
    wstr16 r;
    for (size_t i = 0; i < s.size();) {
        unsigned c = (unsigned char)s[i];
        unsigned cp; int n;
        if (c < 0x80) { cp = c; n = 1; }
        else if ((c >> 5) == 6) { cp = c & 0x1F; n = 2; }
        else if ((c >> 4) == 14) { cp = c & 0x0F; n = 3; }
        else { cp = c & 0x07; n = 4; }
        for (int k = 1; k < n && i + k < s.size(); ++k) cp = (cp << 6) | ((unsigned char)s[i + k] & 0x3F);
        i += n;
        if (cp >= 0x10000) { cp -= 0x10000; r += (char16_t)(0xD800 + (cp >> 10)); r += (char16_t)(0xDC00 + (cp & 0x3FF)); }
        else r += (char16_t)cp;
    }
    return r;
}

std::string в_utf8(const WCHAR_T* w, size_t len) {
    std::string r;
    for (size_t i = 0; i < len; ++i) {
        unsigned cp = w[i];
        if (cp >= 0xD800 && cp < 0xDC00 && i + 1 < len) { cp = 0x10000 + ((cp - 0xD800) << 10) + (w[i + 1] - 0xDC00); ++i; }
        if (cp < 0x80) r += (char)cp;
        else if (cp < 0x800) { r += (char)(0xC0 | (cp >> 6)); r += (char)(0x80 | (cp & 0x3F)); }
        else if (cp < 0x10000) { r += (char)(0xE0 | (cp >> 12)); r += (char)(0x80 | ((cp >> 6) & 0x3F)); r += (char)(0x80 | (cp & 0x3F)); }
        else { r += (char)(0xF0 | (cp >> 18)); r += (char)(0x80 | ((cp >> 12) & 0x3F)); r += (char)(0x80 | ((cp >> 6) & 0x3F)); r += (char)(0x80 | (cp & 0x3F)); }
    }
    return r;
}

// имена методов 1С сравнивает без учёта регистра: латиница и кириллица (с Ё)
unsigned нижний(unsigned c) {
    if (c >= 'A' && c <= 'Z') return c + 32;
    if (c >= 0x410 && c <= 0x42F) return c + 32;
    if (c == 0x401) return 0x451;
    return c;
}

bool равны(const WCHAR_T* a, const wstr16& b) {
    size_t i = 0;
    for (; a[i] && i < b.size(); ++i) if (нижний(a[i]) != нижний(b[i])) return false;
    return !a[i] && i == b.size();
}

// строка JSON из UTF-8 (Ид станка, тексты ошибок); управляющие символы — пробел
std::string json_строка(const std::string& s) {
    std::string r = "\"";
    for (unsigned char c : s) {
        if (c == '"' || c == '\\') { r += '\\'; r += (char)c; }
        else if (c < 0x20 || c == 0x7F) r += ' ';
        else r += (char)c;
    }
    return r + "\"";
}

// байты из ЧПУ (char[n] без гарантии нуля в конце; кодировка не гарантирована): печатный ASCII, прочее «?»
std::string строка_фикс(const char* p, size_t n) {
    size_t k = 0;
    while (k < n && p[k]) ++k;
    while (k > 0 && p[k - 1] == ' ') --k;
    std::string r;
    for (size_t i = 0; i < k; ++i) r += ((unsigned char)p[i] >= 0x20 && (unsigned char)p[i] < 0x7F) ? p[i] : '?';
    return r;
}

const char* текст_кода(short код) {
    switch (код) {
        case EW_OK: return "EW_OK";
        case EW_SOCKET: return "EW_SOCKET: нет связи с ЧПУ (таймаут, отказ соединения)";
        case EW_HANDLE: return "EW_HANDLE: неверный дескриптор";
        case EW_FUNC: return "EW_FUNC: функция не поддерживается ЧПУ";
        case EW_NOOPT: return "EW_NOOPT: нет опции на ЧПУ";
        case EW_BUSY: return "EW_BUSY: ЧПУ занято";
        default: return "ошибка FOCAS";
    }
}

struct Функции {
    pcnc_allclibhndl3 allclibhndl3 = nullptr;
    pcnc_freelibhndl freelibhndl = nullptr;
    pcnc_statinfo statinfo = nullptr;
    pcnc_exeprgname exeprgname = nullptr;
    pcnc_acts acts = nullptr;
    pcnc_actf actf = nullptr;
    pcnc_rdspload rdspload = nullptr;
    pcnc_rdparam rdparam = nullptr;
    pcnc_alarm2 alarm2 = nullptr;
    pcnc_sysinfo sysinfo = nullptr;
};

struct Станок {
    std::string ид, адрес;
    unsigned short порт = 8193;
    int таймаут_мс = 2000;
};

// один станок за один опрос: соединение → чтение → закрытие; результат — объект JSON
std::string опросить(const Функции& ф, const Станок& с) {
    auto t0 = std::chrono::steady_clock::now();
    auto мс = [&]() { return (long long)std::chrono::duration_cast<std::chrono::milliseconds>(
                                 std::chrono::steady_clock::now() - t0).count(); };
    std::string r = "{\"id\":" + json_строка(с.ид);
    auto ошибка = [&](short код, const char* где) {
        return r + ",\"ok\":false,\"code\":" + std::to_string(код) + ",\"where\":\"" + где + "\",\"error\":" +
               json_строка(текст_кода(код)) + ",\"ms\":" + std::to_string(мс()) + "}";
    };
    unsigned short h = 0;
    int32_t таймаут_с = (с.таймаут_мс + 999) / 1000;
    if (таймаут_с < 1) таймаут_с = 1;
    short к = ф.allclibhndl3(с.адрес.c_str(), с.порт, таймаут_с, &h);
    if (к != EW_OK) return ошибка(к, "allclibhndl3");

    ODBST st;
    std::memset(&st, 0, sizeof(st));
    к = ф.statinfo(h, &st);
    if (к != EW_OK) { ф.freelibhndl(h); return ошибка(к, "statinfo"); }
    r += ",\"ok\":true,\"aut\":" + std::to_string(st.aut) + ",\"run\":" + std::to_string(st.run) +
         ",\"motion\":" + std::to_string(st.motion) + ",\"emergency\":" + std::to_string(st.emergency) +
         ",\"alarm\":" + std::to_string(st.alarm);

    // остальное — по возможности: функции нет на этом ЧПУ (EW_FUNC, EW_NOOPT) — поля нет; обрыв — весь станок.
    // Срок станка — его таймаут: медленный канал не растягивает цикл опроса (что не успели — без полей, partial)
    bool обрыв = false, срок = false;
    auto учесть = [&](short код) {
        if (код == EW_SOCKET || код == EW_HANDLE) обрыв = true;
        if (мс() > с.таймаут_мс) срок = true;
        return код == EW_OK;
    };
#define МОЖНО (!обрыв && !срок)
    ODBEXEPRG пр; std::memset(&пр, 0, sizeof(пр));
    if (МОЖНО && ф.exeprgname && учесть(ф.exeprgname(h, &пр)))
        r += ",\"prog\":" + json_строка(строка_фикс(пр.name, sizeof(пр.name))) + ",\"onum\":" + std::to_string(пр.o_num);
    ODBACT а; std::memset(&а, 0, sizeof(а));
    if (МОЖНО && ф.acts && учесть(ф.acts(h, &а))) r += ",\"speed\":" + std::to_string(а.data);
    std::memset(&а, 0, sizeof(а));
    if (МОЖНО && ф.actf && учесть(ф.actf(h, &а))) r += ",\"feed\":" + std::to_string(а.data);
    ODBSPN н; std::memset(&н, 0, sizeof(н));
    if (МОЖНО && ф.rdspload && учесть(ф.rdspload(h, 1, &н))) r += ",\"load\":" + std::to_string(н.data[0]);
    IODBPSD_L п; std::memset(&п, 0, sizeof(п));
    if (МОЖНО && ф.rdparam && учесть(ф.rdparam(h, 6711, 0, (short)sizeof(п), &п))) r += ",\"parts\":" + std::to_string(п.ldata);
    std::memset(&п, 0, sizeof(п));
    if (МОЖНО && ф.rdparam && учесть(ф.rdparam(h, 6712, 0, (short)sizeof(п), &п))) r += ",\"total\":" + std::to_string(п.ldata);
    int32_t ав = 0;
    if (МОЖНО && ф.alarm2 && учесть(ф.alarm2(h, &ав))) r += ",\"alarm_bits\":" + std::to_string(ав);
    ODBSYS sy; std::memset(&sy, 0, sizeof(sy));
    if (МОЖНО && ф.sysinfo && учесть(ф.sysinfo(h, &sy)))
        r += ",\"cnc_type\":" + json_строка(строка_фикс(sy.cnc_type, 2)) + ",\"series\":" +
             json_строка(строка_фикс(sy.series, 4)) + ",\"version\":" + json_строка(строка_фикс(sy.version, 4));
#undef МОЖНО
    ф.freelibhndl(h);
    if (обрыв) return ошибка(EW_SOCKET, "read");
    if (срок) r += ",\"partial\":true";
    return r + ",\"ms\":" + std::to_string(мс()) + "}";
}

struct Метод { const char* en; const char* ru; long параметров; bool есть_результат; };
const Метод МЕТОДЫ[] = {
    {"LoadLibrary", "ЗагрузитьБиблиотеку", 1, true},
    {"Clear", "Очистить", 0, false},
    {"AddMachine", "ДобавитьСтанок", 4, false},
    {"ReadAll", "ПрочитатьВсе", 0, true},
    {"Sleep", "Пауза", 1, false},
};
const char* СВОЙСТВА[][2] = {{"Version", "Версия"}, {"LastError", "ПоследняяОшибка"}, {"LibraryLoaded", "БиблиотекаЗагружена"}};
const long N_МЕТОДОВ = sizeof(МЕТОДЫ) / sizeof(МЕТОДЫ[0]);
const long N_СВОЙСТВ = sizeof(СВОЙСТВА) / sizeof(СВОЙСТВА[0]);

class ОпросЧПУ : public IComponentBase {
public:
    ~ОпросЧПУ() { выгрузить(); }

    // IInitDoneBase
    bool ADDIN_API Init(void* disp) override { платформа = (IAddInDefBase*)disp; return true; }
    bool ADDIN_API setMemManager(void* mem) override { память = (IMemoryManager*)mem; return память != nullptr; }
    long ADDIN_API GetInfo() override { return 2000; }
    void ADDIN_API Done() override { выгрузить(); }

    // ILanguageExtenderBase
    bool ADDIN_API RegisterExtensionAs(WCHAR_T** имя) override { return строка_платформе(имя, "CNC"); }
    long ADDIN_API GetNProps() override { return N_СВОЙСТВ; }
    long ADDIN_API FindProp(const WCHAR_T* имя) override {
        for (long i = 0; i < N_СВОЙСТВ; ++i)
            if (равны(имя, в_utf16(СВОЙСТВА[i][0])) || равны(имя, в_utf16(СВОЙСТВА[i][1]))) return i;
        return -1;
    }
    const WCHAR_T* ADDIN_API GetPropName(long i, long алиас) override {
        if (i < 0 || i >= N_СВОЙСТВ) return nullptr;
        WCHAR_T* р = nullptr;
        строка_платформе(&р, СВОЙСТВА[i][алиас ? 1 : 0]);
        return р;
    }
    bool ADDIN_API GetPropVal(const long i, tVariant* v) override {
        switch (i) {
            case 0: return строка_в_вариант(v, ВЕРСИЯ);
            case 1: return строка_в_вариант(v, последняя_ошибка);
            case 2: TV_VT(v) = VTYPE_BOOL; TV_BOOL(v) = библиотека != nullptr; return true;
        }
        return false;
    }
    bool ADDIN_API SetPropVal(const long, tVariant*) override { return false; }
    bool ADDIN_API IsPropReadable(const long i) override { return i >= 0 && i < N_СВОЙСТВ; }
    bool ADDIN_API IsPropWritable(const long) override { return false; }
    long ADDIN_API GetNMethods() override { return N_МЕТОДОВ; }
    long ADDIN_API FindMethod(const WCHAR_T* имя) override {
        for (long i = 0; i < N_МЕТОДОВ; ++i)
            if (равны(имя, в_utf16(МЕТОДЫ[i].en)) || равны(имя, в_utf16(МЕТОДЫ[i].ru))) return i;
        return -1;
    }
    const WCHAR_T* ADDIN_API GetMethodName(const long i, const long алиас) override {
        if (i < 0 || i >= N_МЕТОДОВ) return nullptr;
        WCHAR_T* р = nullptr;
        строка_платформе(&р, алиас ? МЕТОДЫ[i].ru : МЕТОДЫ[i].en);
        return р;
    }
    long ADDIN_API GetNParams(const long i) override { return i >= 0 && i < N_МЕТОДОВ ? МЕТОДЫ[i].параметров : 0; }
    bool ADDIN_API GetParamDefValue(const long, const long, tVariant* v) override { TV_VT(v) = VTYPE_EMPTY; return false; }
    bool ADDIN_API HasRetVal(const long i) override { return i >= 0 && i < N_МЕТОДОВ && МЕТОДЫ[i].есть_результат; }

    bool ADDIN_API CallAsProc(const long i, tVariant* п, const long n) override {
        try {
            switch (i) {
                case 1: станки.clear(); return true;
                case 2: {
                    if (n < 4) return сбой("ДобавитьСтанок: нужно 4 параметра (Ид, Адрес, Порт, ТаймаутМс)");
                    Станок с;
                    с.ид = строка_параметра(&п[0]);
                    с.адрес = строка_параметра(&п[1]);
                    int порт = число_параметра(&п[2]);
                    с.порт = (unsigned short)(порт > 0 && порт < 65536 ? порт : 8193);
                    int т = число_параметра(&п[3]);
                    с.таймаут_мс = т > 0 ? т : 2000;
                    if (с.адрес.empty()) return сбой("ДобавитьСтанок: пустой адрес");
                    станки.push_back(с);
                    return true;
                }
                case 4: {
                    int мс = n > 0 ? число_параметра(&п[0]) : 0;
                    if (мс > 0 && мс <= 600000) std::this_thread::sleep_for(std::chrono::milliseconds(мс));
                    return true;
                }
            }
        } catch (...) { return сбой("исключение в компоненте"); }
        return false;
    }

    bool ADDIN_API CallAsFunc(const long i, tVariant* рез, tVariant* п, const long n) override {
        try {
            switch (i) {
                case 0: {
                    bool ок = n > 0 && загрузить(строка_параметра(&п[0]));
                    TV_VT(рез) = VTYPE_BOOL; TV_BOOL(рез) = ок;
                    return true;
                }
                case 3: {
                    if (!библиотека) return сбой("ПрочитатьВсе: библиотека FOCAS не загружена (ЗагрузитьБиблиотеку)");
                    std::vector<std::string> ответы(станки.size());
                    std::vector<std::thread> потоки;
                    for (size_t k = 0; k < станки.size(); ++k)
                        потоки.emplace_back([this, k, &ответы]() {
                            try { ответы[k] = опросить(ф, станки[k]); }
                            catch (...) { ответы[k] = "{\"id\":" + json_строка(станки[k].ид) + ",\"ok\":false,\"code\":-999,\"error\":\"исключение\"}"; }
                        });
                    for (auto& т : потоки) т.join();
                    std::string j = "[";
                    for (size_t k = 0; k < ответы.size(); ++k) j += (k ? "," : "") + ответы[k];
                    return строка_в_вариант(рез, j + "]");
                }
            }
        } catch (...) { return сбой("исключение в компоненте"); }
        return false;
    }

    // LocaleBase
    void ADDIN_API SetLocale(const WCHAR_T*) override {}

private:
    IAddInDefBase* платформа = nullptr;
    IMemoryManager* память = nullptr;
    ДескрипторБиблиотеки библиотека = nullptr;
    Функции ф;
    std::vector<Станок> станки;
    std::string последняя_ошибка;

    bool сбой(const std::string& текст) {
        последняя_ошибка = текст;
        if (платформа) {
            wstr16 ист = в_utf16("ФРЕГАТ ПУЛЬС: опрос ЧПУ"), опис = в_utf16(текст);
            платформа->AddError(ADDIN_E_FAIL, (const WCHAR_T*)ист.c_str(), (const WCHAR_T*)опис.c_str(), -1);
        }
        return false;
    }

    bool строка_платформе(WCHAR_T** куда, const std::string& s) {
        if (!память) return false;
        wstr16 w = в_utf16(s);
        if (!память->AllocMemory((void**)куда, (unsigned long)((w.size() + 1) * sizeof(WCHAR_T)))) return false;
        std::memcpy(*куда, w.c_str(), (w.size() + 1) * sizeof(WCHAR_T));
        return true;
    }

    bool строка_в_вариант(tVariant* v, const std::string& s) {
        WCHAR_T* р = nullptr;
        if (!строка_платформе(&р, s)) return false;
        TV_VT(v) = VTYPE_PWSTR;
        v->pwstrVal = р;
        v->wstrLen = (uint32_t)в_utf16(s).size();
        return true;
    }

    static std::string строка_параметра(tVariant* v) {
        if (TV_VT(v) == VTYPE_PWSTR && v->pwstrVal) return в_utf8(v->pwstrVal, v->wstrLen);
        if (TV_VT(v) == VTYPE_PSTR && v->pstrVal) return std::string(v->pstrVal, v->strLen);
        return std::string();
    }

    static int число_параметра(tVariant* v) {
        switch (TV_VT(v)) {
            case VTYPE_I2: return TV_I2(v);
            case VTYPE_I4: return TV_I4(v);
            case VTYPE_I8: return (int)TV_I8(v);
            case VTYPE_UI4: return (int)TV_UI4(v);
            case VTYPE_R4: return (int)TV_R4(v);
            case VTYPE_R8: return (int)TV_R8(v);
            case VTYPE_PWSTR: return std::atoi(строка_параметра(v).c_str());
        }
        return 0;
    }

    void* найти(const char* имя) {
#ifdef _WIN32
        return (void*)GetProcAddress(библиотека, имя);
#else
        return dlsym(библиотека, имя);
#endif
    }

    bool загрузить(const std::string& путь) {
        выгрузить();
#ifdef _WIN32
        wstr16 w = в_utf16(путь);
        // каталог библиотеки — в поиск зависимостей (у настоящей Fwlib64.dll рядом fwlibe64.dll и т.п.)
        библиотека = LoadLibraryExW((LPCWSTR)w.c_str(), nullptr, LOAD_WITH_ALTERED_SEARCH_PATH);
#else
        библиотека = dlopen(путь.c_str(), RTLD_NOW | RTLD_LOCAL);
#endif
        if (!библиотека) { последняя_ошибка = "не загружена библиотека FOCAS: " + путь; return false; }
        ф.allclibhndl3 = (pcnc_allclibhndl3)найти("cnc_allclibhndl3");
        ф.freelibhndl = (pcnc_freelibhndl)найти("cnc_freelibhndl");
        ф.statinfo = (pcnc_statinfo)найти("cnc_statinfo");
        ф.exeprgname = (pcnc_exeprgname)найти("cnc_exeprgname");
        ф.acts = (pcnc_acts)найти("cnc_acts");
        ф.actf = (pcnc_actf)найти("cnc_actf");
        ф.rdspload = (pcnc_rdspload)найти("cnc_rdspload");
        ф.rdparam = (pcnc_rdparam)найти("cnc_rdparam");
        ф.alarm2 = (pcnc_alarm2)найти("cnc_alarm2");
        ф.sysinfo = (pcnc_sysinfo)найти("cnc_sysinfo");
        if (!ф.allclibhndl3 || !ф.freelibhndl || !ф.statinfo) {
            выгрузить();
            последняя_ошибка = "в библиотеке нет функций FOCAS (cnc_allclibhndl3, cnc_freelibhndl, cnc_statinfo): " + путь;
            return false;
        }
        последняя_ошибка.clear();
        return true;
    }

    void выгрузить() {
        if (библиотека) {
#ifdef _WIN32
            FreeLibrary(библиотека);
#else
            dlclose(библиотека);
#endif
        }
        библиотека = nullptr;
        ф = Функции();
    }
};

const WCHAR_T* имена_классов() {
    static wstr16 имена = в_utf16("CNC");
    return (const WCHAR_T*)имена.c_str();
}

}  // namespace

extern "C" EXPORT long GetClassObject(const WCHAR_T* /*имя*/, IComponentBase** p) {
    if (!*p) { *p = new ОпросЧПУ(); return 1; }   // не 0 — объект создан (указатель в long на Win64 не влезает)
    return 0;
}

extern "C" EXPORT long DestroyObject(IComponentBase** p) {
    if (!*p) return -1;
    delete static_cast<ОпросЧПУ*>(*p);
    *p = nullptr;
    return 0;
}

extern "C" EXPORT const WCHAR_T* GetClassNames() { return имена_классов(); }

extern "C" EXPORT AppCapabilities SetPlatformCapabilities(const AppCapabilities) { return eAppCapabilitiesLast; }
