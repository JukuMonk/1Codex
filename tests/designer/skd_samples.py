"""Stable representative SKD inputs for byte-for-byte refactoring parity."""
from types import SimpleNamespace


def outputs(module):
    fields=[('Товар','Товар'),('Количество','Количество')]
    query='ВЫБРАТЬ Товар, Количество ИЗ Данные ГДЕ Количество > &Минимум'
    result={
        'simple':module.dcs_schema('Report','Остатки',fields,query,['Товар','Количество']),
        'groups':module.dcs_schema('Report','Остатки',fields,query,['Товар','Количество'],
            filters=[('Товар','Справочник.Товары.ПустаяСсылка'),('Текст','')],
            total='Количество',groups=['Товар'],parameters=[('Начало','Начало','BeginningOfThisYear')]),
    }
    fs=[SimpleNamespace(path=n,title=t,dim=(n=='Товар'),fmt='ЧДЦ=2' if n=='Количество' else '',width=20) for n,t in fields]
    variants=[dict(name='Основной',title='По товарам',selection=['Товар','Количество'],groups=[['Товар']],
        filters=[('Товар','Справочник.Товары.ПустаяСсылка')],order=[('Количество','Desc')]),
        dict(name='Детальный',title='Детальные записи',selection=['Товар','Количество'],detail=True)]
    for period in (False,True):
        result['extended-period-'+str(period)]=module.dcs_schema_ex(fs,query,variants,period=period,
            params=[('Минимум','Минимум','xs:decimal',module.dcs_param_value('xs:decimal',0))],
            calc=[('Удвоено','Количество * 2','Удвоено')],totals=[('Количество','Сумма(Количество)')])
    return result
