// Подставная библиотека FANUC FOCAS (Fwlib64.dll / libfwlib32.so) для разработки и тестов без станка.
// Те же имена и сигнатуры функций, что у настоящей (focas.h); вместо станка — СЦЕНАРИЙ, текстовый файл:
//   путь — переменная окружения FREGAT_FOCAS_STUB, иначе focas_stub.txt рядом с библиотекой;
//   строка на станок:  <ip> ключ=значение ...   (# — комментарий; перечитывается при каждом вызове — тест
//   меняет сценарий на ходу), ключи:
//     run aut motion emergency alarm   — как в ODBST (run 3 = идёт программа, 1 = стоп, 0 = сброс)
//     prog onum speed feed load parts total  — программа, O-номер, обороты, подача, нагрузка %, детали
//     delay=мс   — задержка ответа на каждый вызов (сеть); offline=1 — нет связи: allclibhndl3 ждёт таймаут
//                  и отдаёт EW_SOCKET, открытый дескриптор тоже начинает отдавать EW_SOCKET (обрыв)
//     nofunc=1   — cnc_rdspload и cnc_exeprgname отвечают EW_FUNC (функции нет на этом ЧПУ)
//     series=0i-F
//   станка нет в сценарии — «авто»: цикл 240 с от времени и адреса (180 с программа, 40 с стоп, 20 с авария),
//   деталь — каждый цикл. Ничего не пишет в «ЧПУ»: функций записи нет, как и в компоненте.
#include "focas.h"
#include <string>
#include <map>
#include <mutex>
#include <fstream>
#include <sstream>
#include <thread>
#include <chrono>
#include <cstring>
#include <cstdlib>
#include <ctime>

#ifdef _WIN32
#include <windows.h>
#define EXPORT extern "C" __declspec(dllexport)
#else
#include <dlfcn.h>
#define EXPORT extern "C" __attribute__((visibility("default")))
#endif

namespace {

struct Профиль {
    bool найден = false;
    int run = 0, aut = 1, motion = 0, emergency = 0, alarm = 0;
    std::string prog = "O0001";
    int onum = 1, speed = 0, feed = 0, load = 0, parts = 0, total = 0;
    int delay = 0;
    bool offline = false, nofunc = false;
    std::string series = "0i-F";
};

std::mutex м;
std::map<unsigned short, std::string> дескрипторы;   // дескриптор → ip
unsigned short следующий = 1;

std::string путь_сценария() {
    if (const char* e = std::getenv("FREGAT_FOCAS_STUB")) return e;
#ifdef _WIN32
    char p[MAX_PATH] = {0};
    HMODULE h = nullptr;
    GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                       (LPCSTR)&путь_сценария, &h);
    GetModuleFileNameA(h, p, MAX_PATH);
    std::string s(p);
#else
    Dl_info di;
    dladdr((void*)&путь_сценария, &di);
    std::string s(di.dli_fname ? di.dli_fname : "");
#endif
    size_t к = s.find_last_of("/\\");
    return (к == std::string::npos ? std::string() : s.substr(0, к + 1)) + "focas_stub.txt";
}

unsigned хеш(const std::string& s) { unsigned h = 2166136261u; for (char c : s) h = (h ^ (unsigned char)c) * 16777619u; return h; }

Профиль авто(const std::string& ip) {
    Профиль п;
    long long t = (long long)std::time(nullptr) + хеш(ip) % 240;
    int фаза = (int)(t % 240);
    п.найден = true;
    п.parts = (int)(t / 240 % 1000);
    п.total = 10000 + п.parts;
    п.onum = 1000 + (int)(хеш(ip) % 9000);
    п.prog = "O" + std::to_string(п.onum);
    if (фаза < 180) { п.run = 3; п.motion = 1; п.speed = 1200 + фаза * 5; п.feed = 300; п.load = 35 + фаза % 30; }
    else if (фаза < 220) { п.run = 1; }
    else { п.run = 0; п.alarm = 1; }
    return п;
}

Профиль профиль(const std::string& ip) {
    std::ifstream f(путь_сценария());
    std::string строка;
    while (std::getline(f, строка)) {
        if (строка.empty() || строка[0] == '#') continue;
        std::istringstream in(строка);
        std::string адрес;
        in >> адрес;
        if (адрес != ip) continue;
        Профиль п;
        п.найден = true;
        std::string кв;
        while (in >> кв) {
            size_t р = кв.find('=');
            if (р == std::string::npos) continue;
            std::string к = кв.substr(0, р), з = кв.substr(р + 1);
            int ч = std::atoi(з.c_str());
            if (к == "run") п.run = ч; else if (к == "aut") п.aut = ч; else if (к == "motion") п.motion = ч;
            else if (к == "emergency") п.emergency = ч; else if (к == "alarm") п.alarm = ч;
            else if (к == "prog") п.prog = з; else if (к == "onum") п.onum = ч; else if (к == "speed") п.speed = ч;
            else if (к == "feed") п.feed = ч; else if (к == "load") п.load = ч; else if (к == "parts") п.parts = ч;
            else if (к == "total") п.total = ч; else if (к == "delay") п.delay = ч; else if (к == "offline") п.offline = ч != 0;
            else if (к == "nofunc") п.nofunc = ч != 0; else if (к == "series") п.series = з;
        }
        return п;
    }
    return авто(ip);
}

void пауза(int мс) { if (мс > 0) std::this_thread::sleep_for(std::chrono::milliseconds(мс)); }

// дескриптор → профиль станка; ошибка связи — EW_SOCKET (после задержки), неизвестный дескриптор — EW_HANDLE
short начать(unsigned short h, Профиль& п) {
    std::string ip;
    {
        std::lock_guard<std::mutex> l(м);
        auto it = дескрипторы.find(h);
        if (it == дескрипторы.end()) return EW_HANDLE;
        ip = it->second;
    }
    п = профиль(ip);
    пауза(п.delay);
    return п.offline ? EW_SOCKET : EW_OK;
}

}  // namespace

EXPORT short FOCAS_API cnc_allclibhndl3(const char* ip, unsigned short port, int32_t timeout, unsigned short* h) {
    (void)port;
    if (!ip || !h) return EW_DATA;
    Профиль п = профиль(ip);
    if (п.offline) {                     // нет связи: ждём задержку, но не дольше таймаута — как сокет
        int ждать = п.delay > 0 ? п.delay : (int)timeout * 1000;
        if (timeout > 0 && ждать > (int)timeout * 1000) ждать = (int)timeout * 1000;
        пауза(ждать);
        return EW_SOCKET;
    }
    пауза(п.delay);
    std::lock_guard<std::mutex> l(м);
    *h = следующий++;
    if (следующий == 0) следующий = 1;
    дескрипторы[*h] = ip;
    return EW_OK;
}

EXPORT short FOCAS_API cnc_freelibhndl(unsigned short h) {
    std::lock_guard<std::mutex> l(м);
    return дескрипторы.erase(h) ? EW_OK : EW_HANDLE;
}

EXPORT short FOCAS_API cnc_statinfo(unsigned short h, ODBST* st) {
    Профиль п; short r = начать(h, п); if (r) return r;
    std::memset(st, 0, sizeof(*st));
    st->aut = (short)п.aut; st->run = (short)п.run; st->motion = (short)п.motion;
    st->emergency = (short)п.emergency; st->alarm = (short)п.alarm;
    return EW_OK;
}

EXPORT short FOCAS_API cnc_exeprgname(unsigned short h, ODBEXEPRG* p) {
    Профиль п; short r = начать(h, п); if (r) return r;
    if (п.nofunc) return EW_FUNC;
    std::memset(p, 0, sizeof(*p));
    std::strncpy(p->name, п.prog.c_str(), sizeof(p->name) - 1);
    p->o_num = п.onum;
    return EW_OK;
}

EXPORT short FOCAS_API cnc_acts(unsigned short h, ODBACT* a) {
    Профиль п; short r = начать(h, п); if (r) return r;
    std::memset(a, 0, sizeof(*a)); a->data = п.speed; return EW_OK;
}

EXPORT short FOCAS_API cnc_actf(unsigned short h, ODBACT* a) {
    Профиль п; short r = начать(h, п); if (r) return r;
    std::memset(a, 0, sizeof(*a)); a->data = п.feed; return EW_OK;
}

EXPORT short FOCAS_API cnc_rdspload(unsigned short h, short sp_no, ODBSPN* s) {
    Профиль п; short r = начать(h, п); if (r) return r;
    if (п.nofunc) return EW_FUNC;
    std::memset(s, 0, sizeof(*s)); s->datano = sp_no; s->data[0] = (short)п.load; return EW_OK;
}

EXPORT short FOCAS_API cnc_rdparam(unsigned short h, short number, short axis, short length, IODBPSD_L* p) {
    Профиль п; short r = начать(h, п); if (r) return r;
    (void)axis;
    if (length < 8) return EW_LENGTH;
    std::memset(p, 0, sizeof(*p));
    p->datano = number;
    if (number == 6711) p->ldata = п.parts;
    else if (number == 6712) p->ldata = п.total;
    else return EW_NUMBER;
    return EW_OK;
}

EXPORT short FOCAS_API cnc_alarm2(unsigned short h, int32_t* alarm) {
    Профиль п; short r = начать(h, п); if (r) return r;
    *alarm = п.alarm ? 1 : 0; return EW_OK;
}

EXPORT short FOCAS_API cnc_sysinfo(unsigned short h, ODBSYS* s) {
    Профиль п; short r = начать(h, п); if (r) return r;
    std::memset(s, 0, sizeof(*s));
    s->max_axis = 3; s->cnc_type[0] = '0'; s->cnc_type[1] = 'i'; s->mt_type[0] = ' '; s->mt_type[1] = 'M';
    std::memcpy(s->series, "D4F1", 4); std::memcpy(s->version, "30.0", 4); s->axes[0] = '0'; s->axes[1] = '3';
    return EW_OK;
}
