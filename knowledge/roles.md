# Роли и права

Пример — `examples/metadata/role/`, эталон — `reference/Roles/мвмВодитель/`
(роль водителя мобильного АРМ; проверена входом с телефона и с компьютера).

## 1. Файлы

```text
Roles/Имя/Имя.mdo          — <mdclass:Role uuid><name><synonym>
Roles/Имя/Rights.rights    — сами права, отступы ТАБАМИ, без BOM, CRLF
Configuration.mdo          — <roles>Role.Имя</roles>
```

```xml
<Rights xmlns:xsi… xmlns="http://v8.1c.ru/8.2/roles" xsi:type="Rights">
	<setForNewObjects>false</setForNewObjects>
	<setForAttributesByDefault>true</setForAttributesByDefault>
	<independentRightsOfChildObjects>false</independentRightsOfChildObjects>
	<object><name>Configuration.ИмяКонфигурации</name>
		<right><name>ThinClient</name><value>true</value></right> …
	</object>
	<object><name>Catalog.X</name><right><name>Read</name>…</object>
</Rights>
```

## 2. Какие права за что (HIGH, из работающей роли)

| Объект | Права | Зачем |
|---|---|---|
| Configuration.Имя | ThinClient, MobileClient, OutputToPrinter, SaveUserData | запуск клиентов (по образцу типовой «Запуск тонкого клиента»); без MobileClient с телефона не войти |
| DataProcessor.АРМ | Use, View | Use — открыть, View — увидеть команду; без обоих обработка недоступна |
| Subsystem.Раздел | View | без права на подсистему команда АРМ в панель не попадёт |
| Catalog.X | Read, View | справочники, которые читает АРМ и его запросы (ВСЕ, включая типовые: ФизическиеЛица, Пользователи, Организации…) |
| Document.X | Read, View, Edit, Update | документ, в котором пользователь отмечает факты; проведение (Posting) не даём — движения делает не он |
| InformationRegister.X | Read, Update | регистр, который АРМ пишет (кэш, статусы) |
| Report.X | Use, View | отчёт |

`setForAttributesByDefault=true` — права на реквизиты наследуются от объекта.
Право на несуществующий объект 1С не примет — генератор сверяет FQN с
папками проекта перед записью.

## 3. Чего роль НЕ даёт

Отбор «только свои записи» — это RLS (ограничения доступа на уровне записей),
их в проекте не делали (LOW). В АРМ водителя чужие рейсы отсекает запрос
формы по физлицу пользователя, а не права. Если пользователь получит доступ
к спискам документов помимо АРМ — RLS понадобится.

## 4. Порядок работы

1. Собрать список объектов, которые трогает функционал: сам АРМ, подсистема,
   все справочники из запросов (включая через точку), документы на запись,
   регистры на запись.
2. Права — минимальные: чтение по умолчанию, запись только там, где пишем.
3. Прописать роль в Configuration.mdo; новая роль — новый объект → полное
   обновление базы (case 020).
4. Проверить входом под пользователем с ЭТОЙ ролью (плюс базовые права
   библиотеки — `БазовыеПраваБСП`, `уатБазовыеПрава`, `ЗапускМобильногоКлиента`
   в проекте-источнике). Ошибка прав видна только в бою.
