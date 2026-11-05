"""Generate an explicit sandbox-only EPF for save/close/posting comparison.

No platform launch and no connection credentials are stored. The caller supplies
an existing catalog/document name and a distinctive non-secret test-IB marker.
"""
from pathlib import Path
import argparse
import re
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'tools'))
import designer_lib as dl

CLOSE = '''&НаКлиенте
Перем РазрешеноЗакрытиеПробы;
&НаКлиенте
Перем ВопросПробыОткрыт;

&НаКлиенте
Процедура ПередЗакрытиемПробы(Отказ, ЗавершениеРаботы, ТекстПредупреждения, СтандартнаяОбработка)
	Если ЗавершениеРаботы Или РазрешеноЗакрытиеПробы = Истина Тогда
		Если РазрешеноЗакрытиеПробы = Истина Тогда
			СтандартнаяОбработка = Ложь;
		КонецЕсли;
		Возврат;
	КонецЕсли;
	Если Не Модифицированность Тогда
		Возврат;
	КонецЕсли;
	Отказ = Истина;
	СтандартнаяОбработка = Ложь;
	Если ВопросПробыОткрыт = Истина Тогда
		Возврат;
	КонецЕсли;
	ВопросПробыОткрыт = Истина;
	ПоказатьВопрос(Новый ОписаниеОповещения("ОтветЗакрытияПробы", ЭтотОбъект),
		"Данные были изменены. Сохранить изменения?", РежимДиалогаВопрос.ДаНетОтмена);
КонецПроцедуры

&НаКлиенте
Процедура ОтветЗакрытияПробы(Ответ, ДополнительныеПараметры) Экспорт
	ВопросПробыОткрыт = Ложь;
	Если Ответ = КодВозвратаДиалога.Да Тогда
		Если Не Записать() Тогда
			Возврат;
		КонецЕсли;
	ИначеЕсли Ответ <> КодВозвратаДиалога.Нет Тогда
		Возврат;
	КонецЕсли;
	РазрешеноЗакрытиеПробы = Истина;
	Закрыть();
	РазрешеноЗакрытиеПробы = Ложь;
КонецПроцедуры

'''


def generate(output, kind, object_name, test_marker, metadata_version='2.21'):
    with dl.generation_context(metadata_version):
        return _generate(output, kind, object_name, test_marker)


def _generate(output, kind, object_name, test_marker):
    if kind not in {'catalog', 'document', 'close'}: raise ValueError('Unsupported probe')
    if not re.fullmatch(r'[^\W\d]\w*', object_name, re.UNICODE): raise ValueError('Metadata identifier required')
    if len(test_marker) < 8 or any(c in test_marker for c in '\r\n\0'):
        raise ValueError('A distinctive non-secret test-database marker of at least 8 characters is required')
    if re.search(r'password|pwd\s*=|пароль|authorization|token\s*=',test_marker,re.I):
        raise ValueError('Credentials are not a test-database marker')
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()): raise ValueError('Probe output must be empty')
    name = 'ПробаМетодаЗаписи'
    doc = kind == 'document'
    form = dl.Form('Проба метода записи')
    form.attr('Объект', ('cfg:DocumentObject.' if doc else 'cfg:CatalogObject.')+object_name, main=True)
    form.attr('Результат', 'string:200')
    form.command('СтандартнаяЗапись', 'Стандартная команда', action='ЗаглушкаКоманды')
    form.command('ЗаписьМетодом', 'Метод формы')
    form.items = [form.group('КомандыПробы', [form.button('СтандартнаяЗапись',name='СтандартнаяЗапись'),
                    form.button('ЗаписьМетодом',name='ЗаписьМетодом')], kind='horizontal'),
                  form.input('Объект.Дата' if doc else 'Объект.Наименование', name='ЗначениеПробы'),
                  form.input('Результат', name='Результат',read_only=True)]
    form.autofill_cmdbar = False
    events = {'OnCreateAtServer':'ПриСозданииНаСервере'}
    if kind == 'close': events['BeforeClose']='ПередЗакрытиемПробы'
    xml=form.xml(events=events)
    xml=xml.replace('Form.Command.СтандартнаяЗапись','Form.StandardCommand.'+('Post' if doc else 'Write'))
    if doc: xml=xml.replace('<AutoCommandBar','<UsePostingMode>Auto</UsePostingMode>\n\t<AutoCommandBar',1)
    marker=test_marker.replace('"','""')
    create=('Документы.'+object_name+'.СоздатьДокумент()') if doc else ('Справочники.'+object_name+'.СоздатьЭлемент()')
    initial='ОбъектПробы.Дата = ТекущаяДата();' if doc else 'ОбъектПробы.Наименование = "ТЕСТ проба " + Строка(Новый УникальныйИдентификатор);'
    save='Записать(Новый Структура("РежимЗаписи", РежимЗаписиДокумента.Проведение))' if doc else 'Записать()'
    module = CLOSE if kind == 'close' else ''
    template = '''&НаСервере
Процедура ПриСозданииНаСервере(Отказ, СтандартнаяОбработка)
	Если СтрНайти(НРег(СтрокаСоединенияИнформационнойБазы()), НРег("MARKER")) = 0 Тогда
		ВызватьИсключение "Проба разрешена только в заранее проверенной тестовой базе.";
	КонецЕсли;
	ОбъектПробы = CREATE;
	INITIAL
	ЗначениеВРеквизитФормы(ОбъектПробы, "Объект");
КонецПроцедуры

&НаКлиенте
Процедура ЗаписьМетодом(Команда)
	Если SAVE Тогда
		Результат = "Успешно";
	Иначе
		Результат = "Отказ записи";
	КонецЕсли;
КонецПроцедуры

&НаКлиенте
Процедура ЗаглушкаКоманды(Команда)
	ВызватьИсключение "Неверная привязка стандартной команды пробника.";
КонецПроцедуры
'''
    values={'MARKER':marker,'CREATE':create,'INITIAL':initial,'SAVE':save}
    module += re.sub(r'\b(MARKER|CREATE|INITIAL|SAVE)\b',lambda match: values[match.group(1)],template)
    dl.write_new(output/(name+'.xml'),dl.external_data_processor_xml(name,'Проба метода записи',forms=['Форма']))
    dl.write_new(output/name/'Forms/Форма.xml',dl.form_meta_xml('ExternalDataProcessor.'+name,'Форма'))
    dl.write_new(output/name/'Forms/Форма/Ext/Form.xml',xml)
    dl.write_new(output/name/'Forms/Форма/Ext/Form/Module.bsl',module)
    return output/(name+'.xml')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kind',choices=('catalog','document','close'))
    parser.add_argument('output',type=Path)
    parser.add_argument('--object',required=True)
    parser.add_argument('--test-marker',required=True)
    parser.add_argument('--metadata-version',choices=('2.20','2.21'),default='2.21')
    args=parser.parse_args()
    print(generate(args.output,args.kind,args.object,args.test_marker,args.metadata_version))
