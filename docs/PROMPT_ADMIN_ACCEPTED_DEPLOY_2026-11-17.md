# Разрешённое продолжение после Phase 1 STOP — 17.11

Владелец уже разрешил сборку и выкладку. Куратор разрешает продолжить только
Phase 2 frontend и Phase 3 live проверки. Backend уже опубликован и healthy;
ошибка собственного probe с неверным именем функции не повод повторять мутации.
Не запускать backend deploy/build/recreate/rollback повторно. Старый STOP и логи
сохранить. Можно новый read-only probe с фактической _app_texts_audit_pair;
имена заранее сверить по принятому candidate-files.

Публиковать уже собранный reports/admin-accepted-deploy-2026-11-17/dist/,
manifest SHA-256 52dd3e16ec812e5aef5b2daa78b8da6bd434f81580a03f1c4f560cb99f242151,
index a6a624b648a59a2fe94875c5b69e0f2e31cd42ad4f1bcc48be35b2c26bbf7ad4.
Без пересборки и правок продукта. Проверь manifest и локальные файлы сначала.
FTPS используй проверенные TLS1.2 и CA /etc/ssl/cert.pem, сертификат не отключать.
Protected backup/rollback сайта, assets first/index last, invariants app/demo/
.htaccess и старые assets сохранить. Обратный HTTPS verify всех файлов/MIME/cache,
RU/KK desktop/mobile live browser. Авторизованные сценарии только штатной сессией,
без мутаций реальных данных/создания пользователей/подделки сессии.
Новые артефакты phase2/, итог отдельный ADMIN_ACCEPTED_DEPLOY_PHASE2_2026-11-17.md.
Новый сбой STOP безопасный сырой вывод без самовольной доправки/повтора/отката.
Остальные условия исходного задания ниже действуют.

---

# Сборка и публикация принятого кабинета/backend — 17.11.2026

## Разрешение и цель

Владелец ответил «Да» на прямой вопрос куратора о сборке и выкладке кабинета
и backend. Выполни публикацию уже принятого результата и проверку рабочего сайта.
Исполнитель Gemini Hydrogen 4 Medium, без подагентов. Куратор код продукта не меняет.
Это отдельное актуальное разрешение, отменяет прежний запрет сборки/deploy только
для указанного кабинета и backend. Commit/push, APK/mobile, ONE и миграции запрещены.

## Прочитать

- AGENTS.md, CLAUDE.md (новое прямое разрешение выше приоритетнее старых запретов).
- reports/ADMIN_FIVE_UI_FIXES_CURATOR_REVIEW_2026-11-17.md (верхняя итоговая приёмка).
- reports/ADMIN_AUDIT_TEXT_VALUES_BACKEND_CURATOR_REVIEW_2026-11-17.md.
- reports/ADMIN_FIVE_UI_FIXES_2026-11-17.md.
- reports/admin-five-ui-fixes-2026-11-17/curator/final-recheck3-hashes.json.
- reports/admin-audit-text-values-2026-11-17/backend/CONTRACT_FOR_GEMINI.md.
- reports/ADMIN_ELEVEN_ITEMS_DEPLOY_2026-11-16.md и его CURATOR_REVIEW.
- scripts/deploy_eleven_items_backend_20261116.py,
  scripts/publish_admin_eleven_items_20261116.py и связанные manifests/verifiers:
  изучи актуальный безопасный способ, старые скрипты не запускай без адаптации путей.
- docs/DEPLOY_VPS.md — историческая схема, не выполнять старую migration-команду.

## Артефакты и проверки до мутаций

Backend брать ТОЛЬКО из:
reports/admin-audit-text-values-2026-11-17/backend/backend-audit-text-values-candidate.tgz
SHA-256 6949f3624508b687b79b78f7648bb5e1f3e333cd7d0f29062119397313333539,
161236 байт, 102 файла. Dirty backend/ не публиковать. Сверь архив и manifests,
проверь отсутствие миграционных изменений против опубликованного backend.

Frontend — текущий принятый admin/, все 18 записей final-recheck3-hashes.json
должны совпасть перед сборкой. Сохрани dirty workspace. Сборка npm --prefix admin
run build с production API https://api.cashback-qr.poscenter.kz по принятой схеме.
Не менять package-lock/зависимости/продукт/тесты. Старый admin/dist сохранить,
новый артефакт скопировать в отдельный каталог сдачи и составить полный manifest
SHA-256/размеров. 355 Vitest/typecheck/lint уже пройдены до CSS-only изменения;
не гонять их заново без причины (build включает tsc).

Предварительно чтением проверь доступ, состояние production и доступность отката.
Используй существующие защищённые подключения SSH/FTPS и механизмы авторизации;
секреты не печатать, не переносить в отчёты/аргументы команд/Git. Если нужен
новый ввод владельца, запроси его через request_secret и останови зависимую часть.

## Публикация

1. Сделай защищённые резервные копии прежних backend source, Docker образа,
   сайта (index и нужные файлы), read-only pg_dump и существующих конфигов
   по прежней безопасной процедуре, без вывода секретов. Проверь целостность
   и запиши точные пути/команды отката. Не выполнять восстановление БД.
2. Backend собрать из чистого staging принятого архива, сверить host/container
   hashes с candidate manifest. Менять только backend контейнер --no-deps,
   без migration, без перезапуска Postgres/Redis/Caddy и изменения env/compose.
   Firebase JSON не читать/не копировать/не хешировать, mounts сохранить.
3. Убедись health/live и health/ready 200, alembic current 0019 без upgrade,
   конфиги неизменны, инфраструктура не пересоздана, новый лог без ошибок.
4. Публикуй frontend безопасно: новые assets первыми, index последним,
   с бэкапом, без удаления старых assets. Сохрани .htaccess, app/*, APK,
   version manifests, demo/* и посторонние файлы. Никакого общего rsync --delete.
5. Обратным HTTPS скачиванием проверь все файлы нового dist по manifest,
   MIME/HTTP/cache, /admin/login и /; сохрани инварианты app/version.json,
   app/keremet-version.json, demo/index.html и .htaccess.
6. Проверь рабочие сценарии RU/KK desktop/mobile в чистом браузере. Если доступна
   штатная авторизованная сессия/учётная запись — read-only dashboard period,
   AuditPage тексты, карточка без трёх строк, редакторы/ошибка без сохранения
   данных production. Не подделывать сессии, не создавать админов/фикстуры,
   не менять реальные бизнесы/контент ради проверки. Если штатной авторизации
   нет — чётко назови предел; публичный refresh 401 не функциональная приёмка.

## STOP и отчёт

При падении/неожиданности СТОП, сохрани безопасный сырой вывод, без самовольных
доправок/повторов/отката. Если часть опубликована — точно зафиксируй что работает,
где остановился, состояние и подготовленный откат. До каждого действия проверь
актуальные пути/локаторы/программы; используй проверенную локаль en_US.UTF-8
только своего процесса, не наследуй пустой LANG. Старые логи не перезаписывать.

Итог reports/ADMIN_ACCEPTED_DEPLOY_2026-11-17.md, артефакты
reports/admin-accepted-deploy-2026-11-17/. Укажи hashes source/dist/archive/image,
backup/rollback, результат HTTPS/health/runtime проверки и screenshots,
предел авторизованной production проверки. Не объявляй full backend suite зелёным:
там известные baseline-падения. Работа до отчёта о публикации, затем куратор
независимо проверяет опубликованный результат.
