# streamstats

Потоковый анализатор файлов с событиями. Читает CSV и JSONL построчно, считает
статистику по уровням и источникам, находит источники с наибольшим числом
ошибок и строит отчёт в JSON или CSV. Файлы любого размера обрабатываются с
почти постоянной памятью: события не накапливаются, после подсчёта каждое
выбрасывается.

Лабораторная работа 2 по Python.

## Установка

Нужен Python 3.12 или новее. Проект собирается через [uv](https://docs.astral.sh/uv/):

```bash
uv sync
```

Это создаёт `.venv`, ставит пакет в режиме разработки и dev-зависимости
(pytest, pytest-cov, ruff). Все команды ниже запускаются из корня репозитория
через `uv run`. Без uv то же самое делается так:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e . pytest pytest-cov ruff
```

## Быстрый старт

```bash
bash scripts/prepare_demo.sh
uv run python -m streamstats analyze demo/app.jsonl --format jsonl
```

Первая команда создаёт каталог `demo/` с тестовыми файлами. Отчёт печатается
в stdout. Чтобы записать его в файл, добавьте `--output`, а чтобы объединить
несколько файлов, перечислите их:

```bash
uv run python -m streamstats analyze demo/app.csv demo/app.csv --format csv --output demo/report.json
```

## Использование

```
python -m streamstats analyze INPUT [INPUT ...] --format {csv,jsonl}
                              [--output REPORT] [--report-format {json,csv}]
                              [--skip-invalid]
                              [--level LEVEL] [--source SOURCE]
                              [--since TIME] [--until TIME]
                              [--plugin MODULE]
```

### Формат входных данных

Событие состоит из четырёх обязательных полей:

| Поле | Требование |
|---|---|
| `timestamp` | дата и время в ISO 8601 |
| `level` | `DEBUG`, `INFO`, `WARNING`, `ERROR` или `CRITICAL` |
| `source` | непустая строка |
| `message` | строка (может быть пустой) |

JSONL: один JSON-объект на строку. CSV: первая строка это заголовок, колонки
могут идти в любом порядке, лишние колонки допускаются. Файлы читаются в
UTF-8 (BOM в начале файла допускается), кириллица сохраняется как есть.

Время без часового пояса считается UTC. Время с поясом пересчитывается в UTC,
поэтому метки из разных поясов сравнимы между собой.

### Параметры

| Параметр | Что делает |
|---|---|
| `INPUT ...` | один или несколько файлов, статистика объединяется |
| `--format` | формат всех входных файлов: `csv` или `jsonl` |
| `--output` | файл для отчёта, по умолчанию отчёт идёт в stdout; не может совпадать с входным файлом |
| `--report-format` | формат отчёта: `json` (по умолчанию) или `csv` |
| `--skip-invalid` | пропускать некорректные строки, а не останавливаться |
| `--level` | оставить только эти уровни (регистр не важен), флаг можно повторять |
| `--source` | оставить только эти источники, флаг можно повторять |
| `--since` | не раньше этого времени (включительно) |
| `--until` | раньше этого времени (не включительно) |
| `--plugin` | модуль, который регистрирует свои парсеры, можно повторять |

### Обработка некорректных строк

По умолчанию первая же некорректная строка останавливает работу. Программа
печатает файл и номер строки и завершается с кодом 2:

```
error: demo/broken.jsonl:7: invalid JSON
```

Отчёт при этом не создаётся. С `--skip-invalid` строка пропускается, в stderr
пишется предупреждение с тем же адресом, остальные строки учитываются, а число
пропущенных попадает в поле `skipped` отчёта:

```
WARNING: skipped invalid line: demo/broken.jsonl:7: invalid JSON
```

Строка считается некорректной, если: JSON не разбирается или это не объект;
нет обязательного поля или колонки; в CSV строка короче или длиннее заголовка;
уровень не из списка; пустой `source`; дата не в ISO 8601; строка пустая.
Исключение: если в заголовке CSV не хватает колонки, это ошибка всего файла, и
`--skip-invalid` её не обходит, потому что разобрать нельзя ни одну строку.

### Фильтры

Фильтры лениво применяются к потоку событий уже после разбора строки, поэтому
память не растёт. Условия соединяются через И.

```bash
uv run python -m streamstats analyze demo/app.jsonl --format jsonl \
    --level ERROR --level CRITICAL --source payments \
    --since 2024-03-01T09:00:00 --until 2024-03-01T10:00:00
```

- интервал времени полуоткрытый: `since <= время < until`;
- `--since` и `--until` принимают ISO 8601, пояс учитывается; если
  `since >= until`, программа завершается с кодом 2;
- итоги, первая и последняя метка в отчёте относятся только к событиям,
  прошедшим фильтр;
- фильтр применяется после проверки строки: некорректная строка всё равно
  остановит работу (или будет посчитана в `skipped`), даже если событие всё
  равно было бы отброшено.

### Отчёт

JSON (`--report-format json`):

```json
{
  "total": 8,
  "skipped": 0,
  "by_level": {"DEBUG": 1, "INFO": 2, "WARNING": 1, "ERROR": 3, "CRITICAL": 1},
  "by_source": {"auth": 3, "payments": 2, "web": 2, "база": 1},
  "top_error_sources": [
    {"source": "payments", "count": 2},
    {"source": "auth", "count": 1},
    {"source": "база", "count": 1}
  ],
  "first_timestamp": "2024-03-01T09:00:00+00:00",
  "last_timestamp": "2024-03-01T09:30:00+00:00"
}
```

(в реальном выводе поля разложены с отступами, здесь для краткости в строку).

- `by_level` содержит все уровни, в том числе с нулём, поэтому у пустого файла
  отчёт той же формы: `total: 0` и метки `null`;
- `top_error_sources`: источники событий `ERROR` и `CRITICAL`, не больше пяти.
  Сортировка по числу ошибок по убыванию, при равенстве по имени источника по
  алфавиту, поэтому порядок не зависит от порядка файлов;
- `by_source` отсортирован по имени.

CSV (`--report-format csv`) это та же информация в плоской таблице
`section,key,value`:

```
section,key,value
total,,8
skipped,,0
level,ERROR,3
source,auth,3
top_error_source,payments,2
first_timestamp,,2024-03-01T09:00:00+00:00
```

CSV строится из того же словаря, что и JSON (`Report.to_dict`), поэтому
расчёты не дублируются.

### Коды выхода

| Код | Когда |
|---|---|
| 0 | всё прошло успешно |
| 2 | некорректная строка в строгом режиме, нечитаемый файл, неверные аргументы (в том числе от argparse), `--output` совпадает с входным файлом, ошибка записи отчёта |

Исходные файлы открываются только на чтение и никогда не меняются.

## Устройство проекта

```
pyproject.toml
README.md
scripts/
    measure_memory.py      замер пиковой памяти на больших файлах
    prepare_demo.sh        тестовые файлы для команд из раздела «Для защиты»
src/streamstats/
    __main__.py            CLI: аргументы, плагины, код выхода
    analysis.py            AnalysisResult (счётчики) и Analyzer (чтение файлов)
    parsers.py             BaseParser, JsonlParser, CSVParser, реестр парсеров
    filters.py             EventsFilters: ленивые фильтры по уровню, источнику, времени
    report.py              Report: словарь, JSON и CSV, топ источников ошибок
    models.py              Event: проверка полей события
    errors.py              исключения и error_position
    core.py                EventsLevels, to_utc
    constants.py           TOP_N, коды выхода, обязательные поля
tests/                     116 тестов
```

### Как идут данные

```
файл ──► строки ──► парсер ──► Event ──► фильтр ──► AnalysisResult.add ──► Report
        (итератор)  (генератор)          (генератор)  (счётчики)
```

`Analyzer` открывает файл и передаёт парсеру сам файловый объект. Парсер
берёт из него строки по одной и через `yield` отдаёт события. Фильтр тоже
генератор. Каждое событие проходит всю цепочку и забывается, как только
`AnalysisResult.add` обновил счётчики. Список событий нигде не строится.

Место, гарантирующее построчную обработку, это связка двух мест:
`for event in ...` в `Analyzer.analyze` ([analysis.py](src/streamstats/analysis.py))
и циклы по `lines` в парсерах ([parsers.py](src/streamstats/parsers.py)).
`read()`, `readlines()` и `list(file)` в коде не используются.

### Память

В памяти постоянно лежат только счётчики: по уровням (их пять), по источникам
и по источникам ошибок. Поэтому дополнительная память не зависит от размера
файла, а зависит от числа **различных источников** (по записи на каждый).
Замеры в разделе «Замер памяти» показывают обе стороны этого утверждения.

### Исключения

Базовый класс `StreamStatsError` и четыре потомка:

| Класс | Когда |
|---|---|
| `InvalidEventError` | неверное событие: поле, уровень, источник, JSON |
| `InvalidTimestampError` | дата не в ISO 8601 |
| `UnsupportedFormatError` | неизвестный формат |
| `CLIConfigurationError` | нечитаемый файл, неверный диапазон времени, неудачный плагин |

Исключения стандартных библиотек превращаются в свои через
`raise ... from e`, `except Exception` в проекте нет. Адрес ошибки
(`файл:строка`) добавляет контекстный менеджер `error_position`: внутри
парсера никто не знает номер строки, а менеджер дописывает его к любой
`StreamStatsError`, которая вылетела из блока.

### Принятые решения

- Время без пояса считается UTC.
- Пустая строка во входном файле это ошибка и для JSONL, и для CSV.
- Лишние колонки в CSV допускаются, недостающие нет.
- Уровни определены один раз, в `EventsLevels`. Отчёт, проверка события и
  допустимые значения `--level` берутся оттуда.
- Топ ошибок считается только по `ERROR` и `CRITICAL`.

## Свой формат (плагин)

Парсеры хранятся в реестре `PARSERS`, встроенные `csv` и `jsonl` регистрируются
так же. Новый формат это наследник `BaseParser` с методом `parse`, который
регистрируется декоратором `register_parser`. Пример для строк вида
`LEVEL источник сообщение`:

```python
# plain_plugin.py
from streamstats.errors import InvalidEventError, StreamStatsError, error_position
from streamstats.parsers import BaseParser, register_parser


@register_parser(name="plain")
class PlainParser(BaseParser):
    def parse(self, lines, source_name):
        for line_no, raw in enumerate(lines, start=1):
            try:
                with error_position(path=source_name, line=line_no):
                    parts = raw.split(maxsplit=2)
                    if len(parts) != 3:
                        raise InvalidEventError(
                            message="expected: LEVEL source message"
                        )
                    level, source, message = parts
                    event = self._build_event(
                        record={
                            "timestamp": "2024-03-01T09:00:00",
                            "level": level,
                            "source": source,
                            "message": message,
                        }
                    )
            except StreamStatsError as e:
                self._handle_error(source_name=source_name, line=line_no, error=e)
                continue
            yield event
```

`_build_event` проверяет поля события и переводит время в UTC,
`_handle_error` отвечает за строгий режим и `--skip-invalid`, поэтому
новый формат получает оба режима без дополнительного кода.

Модуль подключается флагом `--plugin`, после этого его формат можно указать
в `--format`. `PYTHONPATH` говорит Python, где искать файл плагина:

```bash
PYTHONPATH=. uv run python -m streamstats analyze events.log --format plain --plugin plain_plugin
```

## Тесты и качество кода

```bash
uv run pytest                    # 116 тестов
uv run python -m pytest          # то же, как в задании
uv run ruff check .
uv run ruff format --check .
uv run python -m streamstats --help
```

| Файл | Что проверяет |
|---|---|
| `test_parsers.py` | оба парсера, UTC, Unicode, пустой ввод, ленивость, номера строк, оба режима |
| `test_analysis.py` | статистика, CSV и JSONL дают одно и то же, несколько файлов, пустой файл, режимы, файл не в UTF-8, исходники не меняются |
| `test_filters.py` | фильтры, границы времени, ленивость, `to_utc` |
| `test_report.py` | топ и равные значения, `top_n`, пустой отчёт, кириллица, CSV |
| `test_registry.py` | регистрация своего формата |
| `test_cli.py` | запуск CLI в временном каталоге: коды выхода, режимы, фильтры, плагин |

Тесты не зависят друг от друга: все файлы создаются в `tmp_path`, реестр
парсеров после каждого теста возвращается к исходному состоянию.

## Замер памяти

Скрипт генерирует файл нужного размера, запускает настоящий CLI дочерним
процессом и снимает пик памяти именно этого процесса:

```bash
uv run python scripts/measure_memory.py --sizes 10 100 600
uv run python scripts/measure_memory.py --sizes 100 --sources 1000000
```

Параметры скрипта: `--sizes` размеры генерируемых файлов в МБ (для каждого
отдельный замер), `--sources` число различных источников в файле, `--seed`
для воспроизводимости.

Результат на macOS (arm64), Python 3.13.7. Числа зависят от системы, важна
форма зависимости.

100 различных источников:

| Файл, МБ | Строк | Время, с | Пик памяти, МБ |
|---|---|---|---|
| 12 | 100 000 | 0,3 | 19,5 |
| 101 | 840 000 | 2,6 | 19,5 |
| 601 | 4 980 000 | 15,5 | 19,5 |

Пик не меняется при росте файла в 50 раз: около 19,5 МБ это сам интерпретатор.

Около 820 тысяч различных источников:

| Файл, МБ | Строк | Время, с | Пик памяти, МБ |
|---|---|---|---|
| 101 | 820 000 | 3,4 | 161,2 |

Здесь память выросла, потому что счётчикам нужна запись на каждый источник.
Это и есть оценка дополнительной памяти: O(число различных источников), и не
O(размер файла).

## Дополнительные задания

| Задание | Баллы | Как использовать |
|---|---|---|
| Ленивые фильтры по времени, уровню и источнику | +3 | `--level`, `--source`, `--since`, `--until` |
| Пользовательский формат через реестр парсеров | +3 | `--plugin МОДУЛЬ` и `--format ИМЯ` |
| Отчёт CSV без дублирования расчётов | +2 | `--report-format csv` |
| Измерение памяти на файле от 500 МБ | +2 | `scripts/measure_memory.py --sizes 600` |

## Для защиты

Все команды запускаются из корня репозитория. Тестовые файлы создаются в
каталоге `demo/` один раз:

```bash
bash scripts/prepare_demo.sh
```

Основной сценарий:

```bash
uv run python -m streamstats analyze demo/app.jsonl --format jsonl
uv run python -m streamstats analyze demo/app.csv --format csv --report-format csv
uv run python -m streamstats analyze demo/app.jsonl --format jsonl --output demo/report.json
```

CSV и JSONL дают одинаковую статистику:

```bash
diff <(uv run python -m streamstats analyze demo/app.jsonl --format jsonl) <(uv run python -m streamstats analyze demo/app.csv --format csv) && echo "идентичны"
```

Пустой файл:

```bash
uv run python -m streamstats analyze demo/empty.jsonl --format jsonl
```

Режимы обработки ошибок:

```bash
uv run python -m streamstats analyze demo/broken.jsonl --format jsonl; echo "код выхода: $?"
uv run python -m streamstats analyze demo/bad_date.csv --format csv; echo "код выхода: $?"
uv run python -m streamstats analyze demo/broken.jsonl --format jsonl --skip-invalid
```

Несколько файлов и порядок топа при равных значениях:

```bash
uv run python -m streamstats analyze demo/app.jsonl demo/broken.jsonl --format jsonl --skip-invalid
uv run python -m streamstats analyze demo/ties_a.jsonl demo/ties_b.jsonl --format jsonl --report-format csv
diff <(uv run python -m streamstats analyze demo/ties_a.jsonl demo/ties_b.jsonl --format jsonl) <(uv run python -m streamstats analyze demo/ties_b.jsonl demo/ties_a.jsonl --format jsonl) && echo "идентичны"
```

Исходные файлы не меняются:

```bash
shasum -a 256 demo/*.jsonl demo/*.csv > demo/before.txt
uv run python -m streamstats analyze demo/app.jsonl demo/broken.jsonl --format jsonl --skip-invalid > /dev/null
shasum -a 256 -c demo/before.txt
```

Фильтры:

```bash
uv run python -m streamstats analyze demo/app.jsonl --format jsonl --level ERROR --level CRITICAL --report-format csv
uv run python -m streamstats analyze demo/app.jsonl --format jsonl --source auth --report-format csv
uv run python -m streamstats analyze demo/app.jsonl --format jsonl --since 2024-03-01T09:10:00 --until 2024-03-01T09:25:00 --report-format csv
uv run python -m streamstats analyze demo/app.jsonl --format jsonl --since 2024-03-01T12:20:00+03:00 --until 2024-03-01T12:26:00+03:00 --report-format csv
uv run python -m streamstats analyze demo/app.jsonl --format jsonl --since 2024-03-01T10:00:00 --until 2024-03-01T10:00:00; echo "код выхода: $?"
```

Свой формат через плагин:

```bash
cat > demo/plain_plugin.py <<'EOF'
from streamstats.errors import InvalidEventError, StreamStatsError, error_position
from streamstats.parsers import BaseParser, register_parser


@register_parser(name="plain")
class PlainParser(BaseParser):
    def parse(self, lines, source_name):
        for line_no, raw in enumerate(lines, start=1):
            try:
                with error_position(path=source_name, line=line_no):
                    parts = raw.split(maxsplit=2)
                    if len(parts) != 3:
                        raise InvalidEventError(
                            message="expected: LEVEL source message"
                        )
                    level, source, message = parts
                    event = self._build_event(
                        record={
                            "timestamp": "2024-03-01T09:00:00",
                            "level": level,
                            "source": source,
                            "message": message,
                        }
                    )
            except StreamStatsError as e:
                self._handle_error(source_name=source_name, line=line_no, error=e)
                continue
            yield event
EOF
uv run python -m streamstats analyze demo/events.log --format plain
PYTHONPATH=demo uv run python -m streamstats analyze demo/events.log --format plain --plugin plain_plugin --report-format csv
```

Память:

```bash
uv run python scripts/measure_memory.py --sizes 100 600
uv run python scripts/measure_memory.py --sizes 100 --sources 1000000
```

Построчное чтение, полного чтения файла в коде нет:

```bash
grep -rnE "readlines|\.read\(\)|list\(f\)|list\(file\)" src || echo "не найдено"
```

Проверки качества:

```bash
uv run python -m pytest
uv run ruff check .
uv run ruff format --check .
uv run python -m streamstats --help
```
