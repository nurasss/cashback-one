> **СТОП — куратором не принято 2026-11-09. Не запускать приведённый скрипт на рабочем компьютере. Обнаружены неограниченные запросы, раскрытие четырёхзначных карт и небезопасный вывод ошибок. Исправления: `docs/PROMPT_WINDOWS_KEREMET_TURNOVER_REWORK_2026-11-09.md`.**

# Задание: Инспекция источника оборота за 6 месяцев в боевой 1С Keremet (Windows) — 2026-11-09

**Где выполнять:** на Windows-компьютере с **боевой базой 1С POSCENTER ONE магазина Keremet** (НЕ KONS2 / int).
**Исполнитель:** специалист с доступом к серверу Keremet.
**Окружение:** PowerShell / Python 32-bit (`C:\cashback-venv\Scripts\python.exe` или штатный Python агента).
**Консоль:** стандартная консоль пользователя (без отключения безопасности).

---

## Важнейшие правила безопасности

1. **Строго READ ONLY.**
   Запрещено создавать документы, проводить документы, помечать на удаление, регистрировать COM (`regsvr32`), модифицировать конфигурацию или данные 1С.
2. **Службу и состояние агента не трогать.**
   НЕ останавливать и НЕ перезапускать службу `POSCENTERLoyaltyAgent`.
   НЕ изменять и НЕ открывать на запись файлы в `C:\ProgramData\POSCENTER\LoyaltyAgent\state\` (`agent_state.db`, `agent_state.key`, `agent.lock`).
3. **Безопасная папка вывода.**
   Все результаты, скрипты и логи сохранять строго в изолированную папку:
   `C:\cashback-inspection\keremet-turnover\` (создать перед запуском).
4. **Секреты и персональные данные скрыть.**
   НЕ выводить в консоль и НЕ сохранять в отчёт: пароль 1С, строку подключения, DPAPI-ключи, API-ключи, номера телефонов, полные имена покупателей, штрихкоды карт.
5. **Обязательное правило:**
   **«Упало или неожиданно — СТОП и сырой вывод; без самостоятельных исправлений и повторных мутаций; секреты и персональные данные скрыть»**.

---

## Цель исследования

Ответить на ключевой вопрос владельца: **есть ли в настоящей базе 1С POSCENTER ONE магазина Keremet достоверный источник оборота покупок за последние 6 календарных месяцев от текущей даты?**

Необходимо выяснить:
1. Есть ли в метаданных ONE штатный реквизит/регистр накопительного оборота или категории по карте?
2. В регистре `ОстаткиБонусныхКарт`:
   - Насколько полон реквизит `СуммаЧека`?
   - Заполняется ли он при всех покупках с картой (в том числе когда начислено 0 бонусов)?
   - Как отражаются возвраты (уменьшают ли они оборот)?
3. Сколько времени занимает расчёт агрегированного 6-месячного оборота по картам на боевом объёме данных (безопасный хронометраж без зависания касс).

---

## Порядок выполнения

### Шаг 1. Подготовка изолированного каталога (PowerShell)

```powershell
New-Item -ItemType Directory -Path "C:\cashback-inspection\keremet-turnover" -Force | Out-Null
Set-Location "C:\cashback-inspection\keremet-turnover"
```

### Шаг 2. Создание изолированного скрипта инспекции

Создайте файл `C:\cashback-inspection\keremet-turnover\inspect_keremet_turnover.py` со следующим содержимым:

```python
"""
Инспекция метаданных и оборота бонусных карт в 1C POSCENTER ONE (Keremet).
СТРОГО READ ONLY. Никаких записей, проводок и изменений.
Все секреты (пароли, строки подключения) маскируются.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path

# Выводной каталог
OUTPUT_DIR = Path(r"C:\cashback-inspection\keremet-turnover")
REPORT_JSON = OUTPUT_DIR / "inspection_report.json"
REPORT_MD = OUTPUT_DIR / "inspection_report.md"

def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def run_inspection():
    log("=== Старт инспекции источника оборота Keremet (READ ONLY) ===")

    # 1. Загрузка конфигурации агента без раскрытия секретов
    agent_code_path = Path(r"C:\Program Files (x86)\POSCENTER\LoyaltyAgent")
    if agent_code_path.exists():
        sys.path.insert(0, str(agent_code_path))

    # Пытаемся безопасно получить параметры подключения через библиотеку агента
    try:
        from poscenter_loyalty_agent.config import AgentSettings
        from poscenter_loyalty_agent.one_com import OneComConnector
        settings = AgentSettings()
        log("Конфигурация AgentSettings успешно загружена через DPAPI (пароли скрыты)")
        connector = OneComConnector(settings.one_connection_string)
        conn = connector.connect()
        log("Успешное COM-подключение к 1С:Предприятие!")
    except Exception as exc:
        err_msg = str(exc)
        # Маскируем возможные секреты
        log(f"ОШИБКА подключения к 1С: {type(exc).__name__}: {err_msg[:200]}")
        log("СТОП: проверьте права доступа или сообщите об ошибке без расшифровки секретов.")
        sys.exit(1)

    report_data = {
        "timestamp": datetime.now().isoformat(),
        "one_version": getattr(conn, "Метаданные", {}).Версия if hasattr(conn, "Метаданные") else "unknown",
        "catalogs": {},
        "accumulation_registers": {},
        "documents": {},
        "bonus_register_stats": {},
        "rolling_sample": {},
    }

    try:
        md = conn.Метаданные

        # ------------------------------------------------------------------
        # 2. Инвентаризация метаданных (справочники, регистры)
        # ------------------------------------------------------------------
        log("1. Проверка метаданных справочников карт...")
        card_catalogs = ["БонусныеКарты", "ИнформационныеКарты", "КартыЛояльности"]
        for cat_name in card_catalogs:
            try:
                cat_md = md.Справочники[cat_name]
                attrs = [cat_md.Реквизиты[i].Имя for i in range(cat_md.Реквизиты.Количество())]
                report_data["catalogs"][cat_name] = {
                    "exists": True,
                    "attributes": attrs,
                }
                log(f"  Справочник '{cat_name}': найден. Реквизиты: {attrs}")
            except Exception:
                report_data["catalogs"][cat_name] = {"exists": False}

        log("2. Проверка метаданных регистров накопления...")
        reg_names = ["ОстаткиБонусныхКарт", "Продажи", "Бонусы"]
        for r_name in reg_names:
            try:
                r_md = md.РегистрыНакопления[r_name]
                dimensions = [r_md.Измерения[i].Имя for i in range(r_md.Измерения.Количество())]
                resources = [r_md.Ресурсы[i].Имя for i in range(r_md.Ресурсы.Количество())]
                attributes = [r_md.Реквизиты[i].Имя for i in range(r_md.Реквизиты.Количество())]
                report_data["accumulation_registers"][r_name] = {
                    "exists": True,
                    "dimensions": dimensions,
                    "resources": resources,
                    "attributes": attributes,
                }
                log(f"  Регистр '{r_name}': найден. Измерения: {dimensions}, Ресурсы: {resources}, Реквизиты: {attributes}")
            except Exception:
                report_data["accumulation_registers"][r_name] = {"exists": False}

        log("3. Проверка метаданных документов розницы...")
        doc_names = ["ОтчетКассовойСмены", "ОтчетОРозничныхПродажах", "ЧекККМ"]
        for d_name in doc_names:
            try:
                d_md = md.Документы[d_name]
                attrs = [d_md.Реквизиты[i].Имя for i in range(d_md.Реквизиты.Количество())]
                report_data["documents"][d_name] = {
                    "exists": True,
                    "attributes": attrs[:15], # первые 15
                }
                log(f"  Документ '{d_name}': найден.")
            except Exception:
                report_data["documents"][d_name] = {"exists": False}

        # ------------------------------------------------------------------
        # 3. Семантика ОстаткиБонусныхКарт (СуммаЧека, возвраты, виды движений)
        # ------------------------------------------------------------------
        log("4. Анализ регистра 'ОстаткиБонусныхКарт' (READ ONLY)...")
        q = conn.NewObject("Запрос")
        q.Текст = """
        ВЫБРАТЬ
            КОЛИЧЕСТВО(*) КАК ВсегоСтрок,
            МИНИМУМ(Т.Период) КАК МинДата,
            МАКСИМУМ(Т.Период) КАК МаксДата
        ИЗ
            РегистрНакопления.ОстаткиБонусныхКарт КАК Т
        """
        sel = q.Выполнить().Выбрать()
        if sel.Следующий():
            report_data["bonus_register_stats"]["total_rows"] = int(sel.ВсегоСтрок or 0)
            report_data["bonus_register_stats"]["min_period"] = str(sel.МинДата)
            report_data["bonus_register_stats"]["max_period"] = str(sel.МаксДата)
            log(f"  Всего строк: {sel.ВсегоСтрок}, Период от {sel.МинДата} до {sel.МаксДата}")

        # Распределение СуммаЧека и ВидДвижения
        log("5. Анализ распределения СуммаЧека и видов движений...")
        q2 = conn.NewObject("Запрос")
        q2.Текст = """
        ВЫБРАТЬ
            Т.ВидДвижения КАК ВидДвижения,
            ВЫБОР
                КОГДА Т.СуммаЧека > 0 ТОГДА "gt_0"
                КОГДА Т.СуммаЧека = 0 ТОГДА "eq_0"
                ИНАЧЕ "null_or_neg"
            КОНЕЦ КАК ЧекКатегория,
            КОЛИЧЕСТВО(*) КАК КолВоСтрок,
            СУММА(Т.Сумма) КАК СуммаБонусов,
            СУММА(Т.СуммаЧека) КАК СуммаЧеков
        ИЗ
            РегистрНакопления.ОстаткиБонусныхКарт КАК Т
        СГРУППИРОВАТЬ ПО
            Т.ВидДвижения,
            ВЫБОР
                КОГДА Т.СуммаЧека > 0 ТОГДА "gt_0"
                КОГДА Т.СуммаЧека = 0 ТОГДА "eq_0"
                ИНАЧЕ "null_or_neg"
            КОНЕЦ
        """
        sel2 = q2.Выполнить().Выбрать()
        breakdown = []
        while sel2.Следующий():
            v_dv = str(sel2.ВидДвижения)
            cat = str(sel2.ЧекКатегория)
            cnt = int(sel2.КолВоСтрок or 0)
            bonus_sum = float(sel2.СуммаБонусов or 0)
            check_sum = float(sel2.СуммаЧеков or 0)
            breakdown.append({
                "kind": v_dv,
                "check_category": cat,
                "count": cnt,
                "bonus_sum": bonus_sum,
                "check_sum": check_sum,
            })
            log(f"  Вид: {v_dv}, Категория: {cat}, Строк: {cnt}, Сумма чеков: {check_sum:.2f}")
        report_data["bonus_register_stats"]["breakdown"] = breakdown

        # Анализ регистраторов (какие документы формируют движения)
        log("6. Анализ документов-регистраторов...")
        q3 = conn.NewObject("Запрос")
        q3.Текст = """
        ВЫБРАТЬ ПЕРВЫЕ 10
            ТИПЗНАЧЕНИЯ(Т.Регистратор) КАК ТипРегистратора,
            КОЛИЧЕСТВО(*) КАК КолВоСтрок
        ИЗ
            РегистрНакопления.ОстаткиБонусныхКарт КАК Т
        СГРУППИРОВАТЬ ПО
            ТИПЗНАЧЕНИЯ(Т.Регистратор)
        """
        sel3 = q3.Выполнить().Выбрать()
        registrars = []
        while sel3.Следующий():
            registrars.append({
                "registrar_type": str(sel3.ТипРегистратора),
                "count": int(sel3.КолВоСтрок or 0)
            })
        report_data["bonus_register_stats"]["registrars"] = registrars

        # ------------------------------------------------------------------
        # 4. Тестовый замер расчета оборота за 6 месяцев (хронометраж)
        # ------------------------------------------------------------------
        log("7. Замер скорости агрегации оборота за 6 месяцев (Timebox)...")
        t_start = time.perf_counter()

        q_roll = conn.NewObject("Запрос")
        # 6 календарных месяцев назад
        from datetime import date
        today = date.today()
        # Вычисляем 6 месяцев назад
        m = today.month - 6
        y = today.year
        if m <= 0:
            m += 12
            y -= 1
        d = min(today.day, 28)
        start_date = datetime(y, m, d, 0, 0, 0)

        q_roll.Текст = """
        ВЫБРАТЬ ПЕРВЫЕ 20
            Т.БонуснаяКарта.Код КАК КартаКод,
            СУММА(Т.СуммаЧека) КАК Оборот,
            КОЛИЧЕСТВО(РАЗЛИЧНЫЕ Т.Регистратор) КАК Чеков
        ИЗ
            РегистрНакопления.ОстаткиБонусныхКарт КАК Т
        ГДЕ
            Т.Период >= &WindowStart
            И Т.ВидДвижения = ЗНАЧЕНИЕ(ВидДвиженияНакопления.Приход)
        СГРУППИРОВАТЬ ПО
            Т.БонуснаяКарта.Код
        """
        q_roll.УстановитьПараметр("WindowStart", start_date)

        t_query_0 = time.perf_counter()
        sel_roll = q_roll.Выполнить().Выбрать()
        t_query_1 = time.perf_counter()
        duration_ms = (t_query_1 - t_query_0) * 1000

        sample_cards = []
        while sel_roll.Следующий():
            # Маскируем код карты: оставляем только последние 4 цифры
            raw_code = str(sel_roll.КартаКод or "")
            masked_code = ("*" * (len(raw_code) - 4)) + raw_code[-4:] if len(raw_code) >= 4 else "****"
            sample_cards.append({
                "masked_code": masked_code,
                "spend": float(sel_roll.Оборот or 0),
                "receipts_count": int(sel_roll.Чеков or 0),
            })

        log(f"  Выборка 20 карт выполнена за {duration_ms:.2f} мс. Найдено записей: {len(sample_cards)}")
        report_data["rolling_sample"] = {
            "window_start": start_date.isoformat(),
            "query_duration_ms": duration_ms,
            "sample_count": len(sample_cards),
            "sample": sample_cards[:5], # только 5 примеров с маскированными кодами
        }

    except Exception as exc:
        log(f"ОШИБКА во время инспекции 1С: {type(exc).__name__}: {exc}")
        report_data["error"] = str(exc)
    finally:
        try:
            connector.disconnect()
        except Exception:
            pass

    # Сохраняем отчеты
    with open(REPORT_JSON, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write("# Результаты инспекции 1C Keremet (READ ONLY)\n\n")
        f.write(f"- Дата: {report_data['timestamp']}\n")
        f.write(f"- Версия ONE: {report_data.get('one_version')}\n\n")
        f.write("## 1. Справочники\n```json\n" + json.dumps(report_data.get("catalogs"), ensure_ascii=False, indent=2) + "\n```\n\n")
        f.write("## 2. Регистры накопления\n```json\n" + json.dumps(report_data.get("accumulation_registers"), ensure_ascii=False, indent=2) + "\n```\n\n")
        f.write("## 3. Статистика ОстаткиБонусныхКарт\n```json\n" + json.dumps(report_data.get("bonus_register_stats"), ensure_ascii=False, indent=2) + "\n```\n\n")
        f.write("## 4. Замер расчета 6 месяцев\n```json\n" + json.dumps(report_data.get("rolling_sample"), ensure_ascii=False, indent=2) + "\n```\n")

    log(f"Отчёты сохранены:\n  JSON: {REPORT_JSON}\n  MD:   {REPORT_MD}")
    log("=== Инспекция завершена ===")

if __name__ == "__main__":
    run_inspection()
```

### Шаг 3. Запуск инспекции (PowerShell)

Запустите скрипт через виртуальное окружение агента (32-битный Python с COM):

```powershell
& "C:\cashback-venv\Scripts\python.exe" C:\cashback-inspection\keremet-turnover\inspect_keremet_turnover.py
```

*Если виртуальное окружение расположено по другому пути, используйте путь к `python.exe` установленного агента или проверьте `where.exe python`.*
*Если возникает ошибка DPAPI или импорта — **СТОП**, скопируйте текст ошибки без паролей.*

### Шаг 4. Сбор результатов

После завершения работы скрипта убедитесь, что файлы созданы:
```powershell
Get-Item C:\cashback-inspection\keremet-turnover\*
```

Передайте куратору содержимое `C:\cashback-inspection\keremet-turnover\inspection_report.md` (или JSON). Секретные строки и персональные данные скриптом автоматически исключены.

---

## Что делать при ошибках
- При ошибке COM-подключения (`auth_failed`, `com_not_registered`, `db_not_found`) — **СТОП**, не меняйте пароли и реестр вручную.
- Не запускайте повторные мутирующие команды.
- Не удаляйте файлы конфигурации или службы.
