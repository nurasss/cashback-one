# APP Stage 0 — инструмент на Mac, 2026-10-27

## Итог и граница проверки

Часть А реализована в локальном рабочем дереве, проверена на синтетическом COM и
ожидает независимой приёмки куратором. Тесты инструмента: **20 passed**; регрессия
агента: **241 passed, 23 skipped**; Ruff с конфигом агента: чисто. Это не проверка
настоящего COM, синтаксиса запросов в 1С или конфигурации ONE.

Часть Б не начиналась: к ONE и Windows-службе не обращались, сборок, установки,
деплоя, commit и push не было. Изменения в `agent/`, `backend/`, `admin/` и
`mobile/` отсутствовали по показанным ниже проверкам до создания отчёта.
Существовавшие до задачи неотслеживаемые `C:/`, `video/` и файл промпта не
изменялись. `git diff --stat` не показывает новые неотслеживаемые файлы.

## Файлы

- `tools/app_stage0/app_stage0.py` — CLI `metadata`, `profile`, `crosscheck`.
- `tools/app_stage0/common.py` — проверка запросов, путь результатов, проверка
  вывода, тайминг и обработка ошибок.
- `tools/app_stage0/metadata.py` — инвентаризация метаданных и эвристические кандидаты.
- `tools/app_stage0/app_profile.py` — агрегирующие запросы, эталонные выборки и сверка.
- `tools/app_stage0/tests/test_app_stage0.py` — 20 тестов с синтетическим COM.
- `tools/app_stage0/README.md` — формат выбора и инструкция владельцу для Windows.
- `reports/APP_STAGE0_TOOL_2026-10-27.md` — этот отчёт.

Проверка текста запроса выполняется перед созданием COM-запроса. Строка
подключения берётся только из окружения; содержимое всех формируемых файлов и
консольных сообщений проверяется `validate_safe_output`. `crosscheck` пишет
сумму и количество только в отдельный локальный файл вне репозитория; в консоль
числа не выводятся.

## Известные ограничения

1. Настоящая ONE и Windows COM не проверены. Имена COM-свойств метаданных,
   полнота инвентаризации и работоспособность всех шаблонов запросов на платформе
   1С не подтверждены. Для недоступных категорий и большинства недоступных свойств
   записываются ошибки. **Недоступный синоним при этом заменяется пустой строкой
   без отдельной отметки**; пустой синоним не следует считать доказанным фактом.
2. Ввод задним числом среди последних 100 документов не вычисляется: ссылка и
   номер не доказаны как порядок создания. Профиль явно указывает «не проверено».
3. Выбор `register_kind` делается оператором по метаданным; код проверяет его
   допустимое значение, но не сравнивает автоматически с реальным видом регистра.
   Виртуальная таблица остатков может не содержать нулевых комбинаций. Поддержка
   функций длины и шаблонов поиска для штрихкода на данной версии 1С не проверена.
4. Виды оплаты выводятся только из явно заданного владельцем списка
   `allowed_values`; другие объединяются в число без значений. Сам список должен
   содержать исключительно проверенные неперсональные виды оплаты: автоматическое
   распознавание ФИО существующим sanitizer не обеспечивается.
5. Для безопасности исходный текст ошибок не сохраняется полностью: после
   `sanitize_text` дополнительно остаются только разрешённые общие слова и тип
   исключения. Это ограничивает диагностику, но исключает вывод произвольных
   фрагментов ошибки, которые могут содержать ФИО или секреты.
6. Порог медленного запроса не прерывает выполняющийся COM-запрос. После его
   завершения пропускаются последующие тяжёлые запросы того же объекта. Статистика
   строк получает одно агрегированное число на документ и на больших объёмах может
   требовать существенных времени и памяти. Эталонные чтения запускаются последними.
7. Сверка считает все документы выбранного типа за дату без фильтров проведения,
   отмены и возвратов. Условия требуется сопоставить с отчётом ONE. Числа сверки
   преобразуются в Python `float`, поэтому десятичные суммы могут округляться;
   точность такой сверки требует отдельной оценки до использования как доказательства.
8. Периоды в 24 и 3 месяца включают текущий календарный месяц до его конца;
   эталонная неделя — последняя полная неделя с понедельника по воскресенье.
   Тесты используют только синтетические данные и не доказывают безопасность
   произвольных пользовательских списков или поведение реальной базы.

## Проверки — команды, коды и сырой вывод

Первоначальный baseline, до правок, код выхода **0**:

```text
$ PYTHONPATH=agent/src backend/.venv/bin/python -m pytest agent/tests -q
.......................................ssssssssssssss................... [ 27%]
..........................................ssss..s....................... [ 54%]
........................................................................ [ 81%]
.........................................ssss...                         [100%]
241 passed, 23 skipped in 17.68s
```

При первоначальной проверке Ruff без конфига вернул код **1** и 31 замечание;
работа была остановлена. Полный сырой вывод приведён в приложении ниже. После
уточнения владельца разрешены только I001, UP035, B033 и два B023; `allowed` и
`visible` привязаны в параметрах `consume`, подсчёт `hidden` не менялся.
Авторизованная автофиксация, код выхода **0**:

```text
$ backend/.venv/bin/python -m ruff check --config agent/pyproject.toml --select I001,UP035,B033 --fix tools/app_stage0
Found 8 errors (8 fixed, 0 remaining).
```

Итоговые проверки после исправлений, код выхода каждой команды **0**:

```text
$ PYTHONPATH=agent/src backend/.venv/bin/python -m pytest tools/app_stage0/tests -q
....................                                                     [100%]
20 passed in 0.75s

$ PYTHONPATH=agent/src backend/.venv/bin/python -m pytest agent/tests -q
.......................................ssssssssssssss................... [ 27%]
..........................................ssss..s....................... [ 54%]
........................................................................ [ 81%]
.........................................ssss...                         [100%]
241 passed, 23 skipped in 20.17s

$ backend/.venv/bin/python -m ruff check --config agent/pyproject.toml tools/app_stage0
All checks passed!

$ git diff --stat agent/ backend/ admin/ mobile/
(нет вывода)

$ git status --short --untracked-files=all -- agent/ backend/ admin/ mobile/
(нет вывода)
```

Состояние непосредственно перед созданием отчёта, код выхода каждой команды **0**:

```text
$ git status --short
?? C:/
?? docs/PROMPT_APP_STAGE0_ONE_PROFILE_2026-10-27.md
?? tools/
?? video/

$ git diff --stat
(нет вывода)

$ git status --short --untracked-files=all -- tools/app_stage0/
?? tools/app_stage0/README.md
?? tools/app_stage0/app_profile.py
?? tools/app_stage0/app_stage0.py
?? tools/app_stage0/common.py
?? tools/app_stage0/metadata.py
?? tools/app_stage0/tests/test_app_stage0.py
```

## Шаблоны запросов без данных

Подстановки в фигурных скобках — служебные обозначения проверенных имён
метаданных или формируемых выражений. Параметры `&Начало`, `&Конец` и `&Момент`
передаются через `УстановитьПараметр`. Ниже — тексты из `app_profile.py`, а не
утверждение об их исполнении на реальной ONE.

Документы: общее число, статусы и крайние даты:

```sql
ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК Всего,
СУММА(ВЫБОР КОГДА Т.Проведен ТОГДА 1 ИНАЧЕ 0 КОНЕЦ) КАК Проведено,
СУММА(ВЫБОР КОГДА Т.ПометкаУдаления ТОГДА 1 ИНАЧЕ 0 КОНЕЦ) КАК Удалено,
МИНИМУМ(Т.Дата) КАК Первая, МАКСИМУМ(Т.Дата) КАК Последняя ИЗ {key} КАК Т
```

Документы и регистры по месяцам:

```sql
ВЫБРАТЬ НАЧАЛОПЕРИОДА(Т.{date_field}, МЕСЯЦ) КАК Месяц,
КОЛИЧЕСТВО(*) КАК Количество ИЗ {table} КАК Т
ГДЕ Т.{date_field} >= &Начало И Т.{date_field} < &Конец
СГРУППИРОВАТЬ ПО НАЧАЛОПЕРИОДА(Т.{date_field}, МЕСЯЦ)
```

Доступность версии данных документа или справочника:

```sql
ВЫБРАТЬ КОЛИЧЕСТВО(Т.ВерсияДанных) КАК Количество ИЗ {table} КАК Т
```

Число строк табличной части на документ:

```sql
ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК Строк
ИЗ {key}.{section} КАК Т СГРУППИРОВАТЬ ПО Т.Ссылка
```

Виды оплаты и количество; значения, не разрешённые оператором, не сохраняются:

```sql
ВЫБРАТЬ Т.{field} КАК Вид, КОЛИЧЕСТВО(*) КАК Количество
ИЗ {key}.{section} КАК Т ГДЕ Т.Ссылка.Дата >= &Начало И Т.Ссылка.Дата < &Конец
СГРУППИРОВАТЬ ПО Т.{field}
```

Справочник:

```sql
ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК Всего,
СУММА(ВЫБОР КОГДА Т.ЭтоГруппа ТОГДА 1 ИНАЧЕ 0 КОНЕЦ) КАК Группы,
СУММА(ВЫБОР КОГДА Т.ПометкаУдаления ТОГДА 1 ИНАЧЕ 0 КОНЕЦ) КАК Удалено
ИЗ {key} КАК Т
```

Длины и доля цифровых штрихкодов:

```sql
ВЫБРАТЬ ДЛИНАСТРОКИ(СОКРЛП(Т.{field})) КАК Длина,
КОЛИЧЕСТВО(*) КАК Всего,
СУММА(ВЫБОР КОГДА СОКРЛП(Т.{field}) <> "" И НЕ СОКРЛП(Т.{field}) ПОДОБНО "%[^0-9]%"
ТОГДА 1 ИНАЧЕ 0 КОНЕЦ) КАК Цифровых ИЗ {key} КАК Т
СГРУППИРОВАТЬ ПО ДЛИНАСТРОКИ(СОКРЛП(Т.{field}))
```

Регистр остатков: `{zero}` — соединённые через `И` сравнения каждого ресурса
с нулём; `{negative}` — соединённые через `ИЛИ` сравнения ресурсов с нулём:

```sql
ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК Всего,
СУММА(ВЫБОР КОГДА {zero} ТОГДА 1 ИНАЧЕ 0 КОНЕЦ) КАК Нулевых,
СУММА(ВЫБОР КОГДА {negative} ТОГДА 1 ИНАЧЕ 0 КОНЕЦ) КАК Отрицательных
ИЗ {key}.Остатки(&Момент, ) КАК Т
```

Различные значения измерения в виртуальной таблице остатков:

```sql
ВЫБРАТЬ КОЛИЧЕСТВО(РАЗЛИЧНЫЕ Т.{dimension}) КАК Количество
ИЗ {key}.Остатки(&Момент, ) КАК Т
```

Строки виртуальной таблицы оборотов за последний полный месяц:

```sql
ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК Количество
ИЗ {key}.Обороты(&Начало, &Конец, , ) КАК Т
```

Эталонное чтение; `{columns}` содержит реквизиты выбранной табличной части,
значения читаются и отбрасываются:

```sql
ВЫБРАТЬ {columns} ИЗ {key}.{section} КАК Т
ГДЕ Т.Ссылка.Дата >= &Начало И Т.Ссылка.Дата < &Конец
```

Сверка владельца, только в отдельный локальный файл:

```sql
ВЫБРАТЬ КОЛИЧЕСТВО(*) КАК Количество, СУММА(Т.{field}) КАК Сумма
ИЗ {key} КАК Т ГДЕ Т.Дата >= &Начало И Т.Дата < &Конец
```

## Приложение: первоначальный Ruff без конфига

Команда `backend/.venv/bin/python -m ruff check tools/app_stage0`, код выхода **1**.
После этого сбоя без разрешения владельца исправлений не выполнялось.

```text
I001 [*] Import block is un-sorted or un-formatted
  --> tools/app_stage0/app_profile.py:3:1
   |
 1 |   """Только агрегаты и отдельные эталонные выборки по выбранным метаданным."""
 2 |
 3 | / from __future__ import annotations
 4 | |
 5 | | import math
 6 | | from datetime import datetime, time, timedelta
 7 | | from typing import Any
 8 | |
 9 | | from common import InputError, QueryRunner, as_count, as_date, as_number, check_output, identifier
10 | | from metadata import describe
   | |_____________________________^
help: Organize imports
   |
8  |
   - from common import InputError, QueryRunner, as_count, as_date, as_number, check_output, identifier
9  + from common import (
10 +     InputError,
11 +     QueryRunner,
12 +     as_count,
13 +     as_date,
14 +     as_number,
15 +     check_output,
16 +     identifier,
17 + )
18 | from metadata import describe
   -
19 |
   |

B023 Function definition does not bind loop variable `allowed`
   --> tools/app_stage0/app_profile.py:213:25
    |
211 |             count = as_count(sel.Количество)
212 |             value = str(runner.conn.String(sel.Вид))
213 |             if value in allowed:
    |                         ^^^^^^^
214 |                 visible.append({"type": value, "count": count})
215 |             else:
    |

B023 Function definition does not bind loop variable `visible`
   --> tools/app_stage0/app_profile.py:214:17
    |
212 |             value = str(runner.conn.String(sel.Вид))
213 |             if value in allowed:
214 |                 visible.append({"type": value, "count": count})
    |                 ^^^^^^^
215 |             else:
216 |                 hidden += count
    |

I001 [*] Import block is un-sorted or un-formatted
  --> tools/app_stage0/app_stage0.py:3:1
   |
 1 |   """Локальный read-only CLI для первоначального исследования POSCENTER APP."""
 2 |
 3 | / from __future__ import annotations
 4 | |
 5 | | import argparse
 6 | | import json
 7 | | import logging
 8 | | import math
 9 | | import os
10 | | import sys
11 | | from datetime import datetime
12 | | from pathlib import Path
13 | | from typing import Any
14 | |
15 | | from poscenter_loyalty_agent.one_com import OneComConnector
16 | |
17 | | from common import InputError, check_output, json_text, output_dir, safe_print, write_files
18 | | from metadata import inventory
19 | | from app_profile import collect_profile, crosscheck, select_targets
   | |___________________________________________________________________^
help: Organize imports
   |
14 |
   - from poscenter_loyalty_agent.one_com import OneComConnector
   -
   - from common import InputError, check_output, json_text, output_dir, safe_print, write_files
15 + from app_profile import collect_profile, crosscheck, select_targets
16 + from common import (
17 +     InputError,
18 +     check_output,
19 +     json_text,
20 +     output_dir,
21 +     safe_print,
22 +     write_files,
23 + )
24 | from metadata import inventory
   - from app_profile import collect_profile, crosscheck, select_targets
25 + from poscenter_loyalty_agent.one_com import OneComConnector
26 |
   |

BLE001 Do not catch blind exception: `Exception`
  --> tools/app_stage0/app_stage0.py:50:12
   |
48 |         with Path(path).open("r", encoding="utf-8") as handle:
49 |             return json.load(handle)
50 |     except Exception:
   |            ^^^^^^^^^
51 |         raise InputError("Не удалось прочитать JSON выбора объектов.") from None
   |

BLE001 Do not catch blind exception: `Exception`
   --> tools/app_stage0/app_stage0.py:131:12
    |
129 |         safe_print(str(exc), secret, file=sys.stderr)
130 |         return 1
131 |     except Exception:
    |            ^^^^^^^^^
132 |         # Ни строки COM-ошибки, ни traceback не попадают в консоль.
133 |         safe_print("Операция не выполнена; подробности скрыты во избежание утечки данных.",
    |

I001 [*] Import block is un-sorted or un-formatted
  --> tools/app_stage0/common.py:3:1
   |
 1 |   """Общие безопасные границы для локального инструмента APP Stage 0."""
 2 |
 3 | / from __future__ import annotations
 4 | |
 5 | | import json
 6 | | import math
 7 | | import os
 8 | | import re
 9 | | import time
10 | | from datetime import date, datetime
11 | | from pathlib import Path
12 | | from typing import Any, Callable
13 | |
14 | | from poscenter_loyalty_agent.stage0.sanitizer import sanitize_text, validate_safe_output
   | |________________________________________________________________________________________^
help: Organize imports
   |
15 |
   -
16 | REPO_ROOT = Path(__file__).resolve().parents[2]
   |

UP035 [*] Import from `collections.abc` instead: `Callable`
  --> tools/app_stage0/common.py:12:1
   |
10 | from datetime import date, datetime
11 | from pathlib import Path
12 | from typing import Any, Callable
   | ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
13 |
14 | from poscenter_loyalty_agent.stage0.sanitizer import sanitize_text, validate_safe_output
   |
help: Import from `collections.abc`
   |
11 | from pathlib import Path
   - from typing import Any, Callable
12 + from typing import Any
13 + from collections.abc import Callable
14 |
   |

B033 [*] Sets should not contain duplicate item `"ошибка"`
  --> tools/app_stage0/common.py:25:17
   |
19 | FORBIDDEN = re.compile(r"\b(?:ПОМЕСТИТЬ|УНИЧТОЖИТЬ|ДЛЯ\s+ИЗМЕНЕНИЯ)\b", re.IGNORECASE)
20 | SAFE_ERROR_WORDS = {
21 |     "ошибка", "ошибке", "запроса", "запрос", "поле", "поля", "полей", "таблица",
   |     -------- Previous occurrence here
22 |     "таблицы", "не", "найдено", "найден", "обнаружено", "ожидается", "неверный",
23 |     "неверное", "недопустимое", "имя", "тип", "значение", "параметр", "параметра",
24 |     "синтаксическая", "синтаксический", "символ", "операция", "невозможно", "доступ",
25 |     "отказано", "ошибка", "выражение", "метод", "ком", "com", "error", "query",
   |                 ^^^^^^^^
26 |     "field", "not", "found", "syntax", "invalid", "type", "parameter", "failed",
27 | }
   |
help: Remove duplicate item
   |
24 |     "синтаксическая", "синтаксический", "символ", "операция", "невозможно", "доступ",
   -     "отказано", "ошибка", "выражение", "метод", "ком", "com", "error", "query",
25 +     "отказано", "выражение", "метод", "ком", "com", "error", "query",
26 |     "field", "not", "found", "syntax", "invalid", "type", "parameter", "failed",
   |

TRY004 Prefer `TypeError` exception for invalid type
   --> tools/app_stage0/common.py:171:9
    |
169 | def as_number(value: Any) -> int | float:
170 |     if isinstance(value, bool):
171 |         raise ValueError("Ожидалось число.")
    |         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
172 |     number = float(value or 0)
173 |     if not math.isfinite(number):
    |

BLE001 Do not catch blind exception: `Exception`
   --> tools/app_stage0/common.py:228:16
    |
226 |                 rows += 1
227 |                 consume(selection)
228 |         except Exception as exc:
    |                ^^^^^^^^^
229 |             error = safe_error(exc, self.secret)
230 |         elapsed = max(0.0, self.clock() - start)
    |

I001 [*] Import block is un-sorted or un-formatted
 --> tools/app_stage0/metadata.py:3:1
  |
1 |   """Инвентаризация только объекта Метаданные; кандидаты не являются маппингом."""
2 |
3 | / from __future__ import annotations
4 | |
5 | | from typing import Any
6 | |
7 | | from common import identifier, safe_error
  | |_________________________________________^
help: Organize imports
  |
8 |
  -
9 | CATEGORIES = {
  |

S112 `try`-`except`-`continue` detected, consider logging the exception
  --> tools/app_stage0/metadata.py:38:9
   |
36 |               if value is not None:
37 |                   return value
38 | /         except Exception:
39 | |             continue
   | |____________________^
40 |       raise AttributeError("Свойство метаданных недоступно")
   |

BLE001 Do not catch blind exception: `Exception`
  --> tools/app_stage0/metadata.py:38:16
   |
36 |             if value is not None:
37 |                 return value
38 |         except Exception:
   |                ^^^^^^^^^
39 |             continue
40 |     raise AttributeError("Свойство метаданных недоступно")
   |

BLE001 Do not catch blind exception: `Exception`
  --> tools/app_stage0/metadata.py:58:12
   |
56 |     try:
57 |         return str(prop(obj, "Synonym", "Синоним"))
58 |     except Exception:
   |            ^^^^^^^^^
59 |         return ""
   |

BLE001 Do not catch blind exception: `Exception`
  --> tools/app_stage0/metadata.py:70:12
   |
68 |     try:
69 |         return str(conn.String(value))
70 |     except Exception:
   |            ^^^^^^^^^
71 |         return "недоступно"
   |

BLE001 Do not catch blind exception: `Exception`
  --> tools/app_stage0/metadata.py:78:12
   |
76 |     try:
77 |         type_name = representation(conn, prop(field, "Type", "Тип"))
78 |     except Exception:
   |            ^^^^^^^^^
79 |         type_name = "недоступно"
80 |     return {"name": name, "synonym": synonym(field), "type": type_name}
   |

BLE001 Do not catch blind exception: `Exception`
  --> tools/app_stage0/metadata.py:86:12
   |
84 |     try:
85 |         return items(prop(obj, *names)), None
86 |     except Exception as exc:
   |            ^^^^^^^^^
87 |         return [], safe_error(exc, secret)
   |

BLE001 Do not catch blind exception: `Exception`
  --> tools/app_stage0/metadata.py:96:12
   |
94 |         parts = str(value).split(".")
95 |         return ".".join(identifier(part) for part in parts)
96 |     except Exception:
   |            ^^^^^^^^^
97 |         return object_name(obj)
   |

BLE001 Do not catch blind exception: `Exception`
   --> tools/app_stage0/metadata.py:123:20
    |
121 |             try:
122 |                 result[key].append(field_info(conn, value))
123 |             except Exception as exc:
    |                    ^^^^^^^^^
124 |                 errors[key] = safe_error(exc, secret)
    |

BLE001 Do not catch blind exception: `Exception`
   --> tools/app_stage0/metadata.py:142:20
    |
140 |                     section["error"] = field_error
141 |                 result["tabular_sections"].append(section)
142 |             except Exception as exc:
    |                    ^^^^^^^^^
143 |                 errors["tabular_sections"] = safe_error(exc, secret)
    |

BLE001 Do not catch blind exception: `Exception`
   --> tools/app_stage0/metadata.py:154:16
    |
152 |         try:
153 |             result["posting"] = representation(conn, prop(obj, "Posting", "Проведение"))
154 |         except Exception as exc:
    |                ^^^^^^^^^
155 |             errors["posting"] = safe_error(exc, secret)
156 |         movements, error = read_list(obj, ("RegisterRecords", "Registers", "Движения"), secret)
    |

BLE001 Do not catch blind exception: `Exception`
   --> tools/app_stage0/metadata.py:163:20
    |
161 |             try:
162 |                 result["register_movements"] = [full_name(m) for m in movements]
163 |             except Exception as exc:
    |                    ^^^^^^^^^
164 |                 errors["register_movements"] = safe_error(exc, secret)
165 |     if kind == "register":
    |

BLE001 Do not catch blind exception: `Exception`
   --> tools/app_stage0/metadata.py:168:16
    |
166 |         try:
167 |             result["register_kind"] = representation(conn, prop(obj, "RegisterType", "ВидРегистра"))
168 |         except Exception as exc:
    |                ^^^^^^^^^
169 |         errors["register_kind"] = safe_error(exc, secret)
170 |         registrars, error = read_list(obj, ("Recorders", "Registrars", "Регистраторы"), secret)
    |

BLE001 Do not catch blind exception: `Exception`
   --> tools/app_stage0/metadata.py:177:20
    |
175 |             try:
176 |                 result["recorders"] = [full_name(r) for r in registrars]
177 |             except Exception as exc:
    |                    ^^^^^^^^^
178 |                 errors["recorders"] = safe_error(exc, secret)
179 |     return result
    |

BLE001 Do not catch blind exception: `Exception`
   --> tools/app_stage0/metadata.py:188:12
    |
186 |     try:
187 |         return {"available": True, "members": [full_name(value) for value in values]}
188 |     except Exception as exc:
    |            ^^^^^^^^^
189 |         return {"available": False, "error": safe_error(exc, secret)}
    |

BLE001 Do not catch blind exception: `Exception`
   --> tools/app_stage0/metadata.py:218:16
    |
216 |                 if kind == "exchange_plan":
217 |                     result["exchange_plans"].append({"name": name, **exchange_contents(obj, secret)})
218 |         except Exception as exc:
    |                ^^^^^^^^^
219 |             section["error"] = safe_error(exc, secret)
220 |     return result, lookup
    |

I001 [*] Import block is un-sorted or un-formatted
  --> tools/app_stage0/tests/test_app_stage0.py:16:1
   |
14 |   sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
15 |
16 | / import app_stage0  # noqa: E402
17 | | from common import InputError, QueryRunner, REPO_ROOT, output_dir, write_files  # noqa: E402
18 | | from poscenter_loyalty_agent.stage0.sanitizer import SecuritySanitizerError  # noqa: E402
   | |___________________________________________________________________________^
help: Organize imports
   |
16 | import app_stage0  # noqa: E402
   - from common import InputError, QueryRunner, REPO_ROOT, output_dir, write_files  # noqa: E402
17 + from common import REPO_ROOT, InputError, QueryRunner, output_dir, write_files  # noqa: E402
18 | from poscenter_loyalty_agent.stage0.sanitizer import SecuritySanitizerError  # noqa: E402
   -
19 |
   |

RUF100 [*] Unused `noqa` directive (non-enabled: `E402`)
  --> tools/app_stage0/tests/test_app_stage0.py:16:20
   |
14 | sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
15 |
16 | import app_stage0  # noqa: E402
   |                    ^^^^^^^^^^^^
17 | from common import InputError, QueryRunner, REPO_ROOT, output_dir, write_files  # noqa: E402
18 | from poscenter_loyalty_agent.stage0.sanitizer import SecuritySanitizerError  # noqa: E402
   |
help: Remove unused `noqa` directive
   |
15 |
   - import app_stage0  # noqa: E402
16 + import app_stage0
17 | from common import InputError, QueryRunner, REPO_ROOT, output_dir, write_files  # noqa: E402
   |

RUF100 [*] Unused `noqa` directive (non-enabled: `E402`)
  --> tools/app_stage0/tests/test_app_stage0.py:17:81
   |
16 | import app_stage0  # noqa: E402
17 | from common import InputError, QueryRunner, REPO_ROOT, output_dir, write_files  # noqa: E402
   |                                                                                 ^^^^^^^^^^^^
18 | from poscenter_loyalty_agent.stage0.sanitizer import SecuritySanitizerError  # noqa: E402
   |
help: Remove unused `noqa` directive
   |
16 | import app_stage0  # noqa: E402
   - from common import InputError, QueryRunner, REPO_ROOT, output_dir, write_files  # noqa: E402
17 + from common import InputError, QueryRunner, REPO_ROOT, output_dir, write_files
18 | from poscenter_loyalty_agent.stage0.sanitizer import SecuritySanitizerError  # noqa: E402
   |

RUF100 [*] Unused `noqa` directive (non-enabled: `E402`)
  --> tools/app_stage0/tests/test_app_stage0.py:18:78
   |
16 | import app_stage0  # noqa: E402
17 | from common import InputError, QueryRunner, REPO_ROOT, output_dir, write_files  # noqa: E402
18 | from poscenter_loyalty_agent.stage0.sanitizer import SecuritySanitizerError  # noqa: E402
   |                                                                              ^^^^^^^^^^^^
help: Remove unused `noqa` directive
   |
17 | from common import InputError, QueryRunner, REPO_ROOT, output_dir, write_files  # noqa: E402
   - from poscenter_loyalty_agent.stage0.sanitizer import SecuritySanitizerError  # noqa: E402
18 + from poscenter_loyalty_agent.stage0.sanitizer import SecuritySanitizerError
19 |
   |

Found 31 errors.
[*] 10 fixable with `--fix`.
```

## Приёмка и доработки куратора — 2026-10-27

Независимая проверка подтвердила цифры исполнителя: 20 passed, агент 241 passed / 23 skipped, ruff с `--config agent/pyproject.toml` чистый, `agent/`, `backend/`, `admin/`, `mobile/` без изменений. Защита «только `ВЫБРАТЬ`», источник строки подключения и проверка вывода соответствуют промпту.

По поручению владельца куратор сам внёс две доработки перед частью Б:

1. **Эталонное чтение от последней даты с данными** (`app_profile.py`, `collect_profile`, `last_data_day`). Раньше брались вчерашний день и прошлая календарная неделя; в тестовой базе без свежих чеков замер прочитал бы 0 строк. Теперь периоды — «последний день с документами» и «7 дней по последний день с документами» от `last_date` запроса «документы всего». Если дата неизвестна (запрос не выполнен), эталон не запускается и помечается «не проверено: неизвестна дата последнего документа». Пункт 8 «Известных ограничений» про календарную неделю этим отменён.
2. **Тип ошибки при полном сбое** (`app_stage0.py`, `main`). Вместо одной общей фразы выводится имя класса исключения, например `Операция не выполнена (COMConnectionError)`; текст ошибки по-прежнему скрыт.

Новые тесты: `test_connection_error_type_is_shown_without_details`, `test_benchmark_uses_last_document_day`, `test_benchmark_is_skipped_without_last_document_date`; в `test_connection_failure_never_prints_or_writes_secret` добавлена проверка `(RuntimeError)`. README обновлён.

Проверки после доработок (код выхода 0):

```text
$ PYTHONPATH=agent/src backend/.venv/bin/python -m pytest tools/app_stage0/tests -q
23 passed
$ PYTHONPATH=agent/src backend/.venv/bin/python -m pytest agent/tests -q
241 passed, 23 skipped
$ backend/.venv/bin/python -m ruff check --config agent/pyproject.toml tools/app_stage0
All checks passed!
$ git diff --stat agent backend admin mobile
(нет вывода)
```

Не сделано: подсчёт строк на документ по-прежнему передаёт через COM по строке на документ (защищён порогом медленного запроса). Настоящая ONE не проверялась. Commit/push не выполнялись.
