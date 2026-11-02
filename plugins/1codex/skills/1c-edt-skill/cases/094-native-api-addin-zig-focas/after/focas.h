// Подмножество FANUC FOCAS2, которым пользуется ФРЕГАТ ПУЛЬС: только ЧТЕНИЕ состояния (в ЧПУ не пишем ничего).
// Сигнатуры и раскладка структур — по открытому описанию FOCAS2 (fwlib32.h, справка FANUC; inventcom.net) для
// Windows x64 (long = 4 байта). Сверить с fwlib32.h поставки заказчика при первом подключении к реальному ЧПУ:
// подставная библиотека (fwlib_подставная.cpp) собрана по ЭТОМУ же заголовку и расхождение с реальной не покажет.
// Под Linux x64 long = 8 байт: реальная libfwlib32 ждёт 4-байтовые поля — там вместо long нужен int32 (известная
// проблема 64-битного Linux), поэтому поля ниже — int32_t, а не long.
#ifndef FREGAT_FOCAS_H
#define FREGAT_FOCAS_H
#include <stdint.h>

#ifdef _WIN32
#define FOCAS_API __stdcall
#else
#define FOCAS_API
#endif

// коды возврата (FOCAS2)
#define EW_OK 0
#define EW_FUNC 1        // функция не поддерживается этим ЧПУ
#define EW_LENGTH 2
#define EW_NUMBER 3
#define EW_ATTRIB 4
#define EW_DATA 5
#define EW_NOOPT 6       // нет опции
#define EW_HANDLE -8     // неверный дескриптор
#define EW_SOCKET -16    // нет связи / таймаут
#define EW_BUSY -1

#pragma pack(push, 4)
// cnc_statinfo: Series 0i/16i/18i/21i/30i — 9 short (у 30i первые два — hdck/tmmode, у 16i — резерв)
typedef struct {
    short hdck;      // 30i: ручная рукоятка; 16i: резерв
    short tmmode;    // 30i: T/M режим
    short aut;       // режим: 0 MDI, 1 MEM(AUTO), 2 нет, 3 EDIT, 4 HND, 5 JOG, 6 TJOG, 7 THND, 8 INC, 9 REF, 10 RMT
    short run;       // выполнение: 0 RESET (STOP), 1 STOP, 2 HOLD, 3 STaRT (идёт программа), 4 MSTR
    short motion;    // 0 нет, 1 движение, 2 выдержка (dwell)
    short mstb;      // 0 нет, 1 выполняется M/S/T/B
    short emergency; // 0 нет, 1 аварийный стоп, 2 сброс
    short alarm;     // 0 нет, 1 есть авария, 2 предупреждение батареи
    short edit;      // 0 нет редактирования
} ODBST;

typedef struct {     // cnc_exeprgname: имя выполняемой основной программы
    char name[36];
    int32_t o_num;
} ODBEXEPRG;

typedef struct {     // cnc_acts / cnc_actf: фактические обороты шпинделя / подача
    short dummy[2];
    int32_t data;
} ODBACT;

typedef struct {     // cnc_rdspload: нагрузка шпинделей, %
    short datano;
    short type;
    short data[4];
} ODBSPN;

typedef struct {     // cnc_rdparam: один параметр типа «двойное слово» (6711 — детали, 6712 — всего деталей)
    short datano;
    short type;
    int32_t ldata;
} IODBPSD_L;

typedef struct {     // cnc_sysinfo: тип и серия ЧПУ
    short addinfo;
    short max_axis;
    char cnc_type[2];
    char mt_type[2];
    char series[4];
    char version[4];
    char axes[2];
} ODBSYS;
#pragma pack(pop)

extern "C" {
typedef short (FOCAS_API *pcnc_allclibhndl3)(const char* ip, unsigned short port, int32_t timeout, unsigned short* h);
typedef short (FOCAS_API *pcnc_freelibhndl)(unsigned short h);
typedef short (FOCAS_API *pcnc_statinfo)(unsigned short h, ODBST* st);
typedef short (FOCAS_API *pcnc_exeprgname)(unsigned short h, ODBEXEPRG* p);
typedef short (FOCAS_API *pcnc_acts)(unsigned short h, ODBACT* a);
typedef short (FOCAS_API *pcnc_actf)(unsigned short h, ODBACT* a);
typedef short (FOCAS_API *pcnc_rdspload)(unsigned short h, short sp_no, ODBSPN* s);
typedef short (FOCAS_API *pcnc_rdparam)(unsigned short h, short number, short axis, short length, IODBPSD_L* p);
typedef short (FOCAS_API *pcnc_alarm2)(unsigned short h, int32_t* alarm);
typedef short (FOCAS_API *pcnc_sysinfo)(unsigned short h, ODBSYS* s);
}
#endif
