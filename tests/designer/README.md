# Проверки без EDT

fixtures/configuration — минимальная принятая XML-выгрузка; источник и версия
платформы записаны в provenance.json. Здесь нет информационной базы и данных.

Автономная проверка: `python tools/selftest.py`. Реальный прогон требует Windows
с установленной платформой, COM и доступным рабочим столом:

```
python tests/designer/create_fixture.py --v8 <1cv8.exe> --output <new-empty-directory>
python tools/project_cli.py check --config <new-empty-directory/platform.json>
python tools/project_cli.py release --config <new-empty-directory/platform.json>
```

Создаётся новая отдельная база без пользователей. check сверяет обратную выгрузку;
release дополнительно проверяет COM и UI, затем сохраняет локальный CF. При
отличии канонического формата просмотреть comparison.json и выгрузку; автоматического
перезаписывания исходников нет. Историческая EDT-песочница остаётся в tests/sandbox.
Задания для оценки решений агента — tasks.json. Проверка инструментов не доказывает,
что произвольная модель безошибочно решит все эти задания.
