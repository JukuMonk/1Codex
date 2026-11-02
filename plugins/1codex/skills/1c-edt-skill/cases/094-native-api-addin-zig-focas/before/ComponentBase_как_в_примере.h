// WRONG при сборке clang/MinGW (zig -target x86_64-windows-gnu): заголовок Native API как в примере 1С.
// В Itanium C++ ABI виртуальный деструктор — ДВЕ ячейки vtable, в MSVC (платформа 1С) — одна:
// 1С вызывает слот 1 «Init», а там у нас deleting destructor; все методы ниже сдвинуты.
class IInitDoneBase
{
public:
    virtual ~IInitDoneBase() {}                          // MSVC: [0]=dtor; Itanium: [0]=complete, [1]=deleting
    virtual bool ADDIN_API Init(void* disp) = 0;         // MSVC: [1];      Itanium: [2]  ← разъехались
    virtual bool ADDIN_API setMemManager(void* mem) = 0;
    virtual long ADDIN_API GetInfo() = 0;
    virtual void ADDIN_API Done() = 0;
};
// То же у ILanguageExtenderBase, LocaleBase и у интерфейсов ПЛАТФОРМЫ, которые вызывает компонента:
// IMemoryManager (AllocMemory) и IAddInDefBase (AddError) — вызов уйдёт не в ту функцию 1С.
