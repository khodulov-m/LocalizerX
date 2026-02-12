# Дизайн: Команда удаления языков из xcstrings

**Дата:** 2026-02-12
**Статус:** Утверждено

## Общий обзор

Новая команда `delete` для удаления языков из `.xcstrings` файлов с тремя режимами работы:
- **Удалить все** языки кроме source (`--all`)
- **Удалить указанные** языки (позиционный аргумент)
- **Удалить все кроме указанных** и source (`--keep` флаг)

## Интерфейс командной строки

```bash
# Удалить все языки кроме source
localizerx delete --all [path]

# Удалить указанные языки
localizerx delete ro,uk,nl [path]

# Удалить все кроме source и указанных
localizerx delete ru,fr --keep [path]

# Опции
--yes, -y          # Удалить без подтверждения
--backup, -b       # Создать backup перед удалением
--config, -c PATH  # Путь к конфигурационному файлу
```

**Логика аргументов:**
- `path` — опциональный путь к `.xcstrings` файлу или директории
- Если `path` не указан, автопоиск в текущей директории
- `languages` — позиционный аргумент со списком языков через запятую

## Ключевые решения

1. **Подтверждение**: По умолчанию спрашивать подтверждение, с флагом `--yes` удалять без вопросов
2. **Backup**: Создавать backup только с флагом `--backup` (аналогично команде translate)
3. **Несколько файлов**: Поддерживать автопоиск, как в translate (показывать список для выбора если несколько файлов)
4. **Защита source language**: Молча игнорировать с предупреждением
5. **Формат вывода**: Детальный вывод с таблицей, показывающей языки и количество строк

## Архитектура и компоненты

### Файловая структура

- `localizerx/cli/delete.py` — новый модуль с командой `delete()`
- Использует существующие модули:
  - `io/xcstrings.py` — для чтения/записи файлов
  - `parser/model.py` — для работы со структурой `StringCatalog`
  - `cli/utils.py` — для консольного вывода
  - `utils/locale.py` — для валидации языковых кодов

### Основные функции

1. **`delete()`** — точка входа Typer команды
   - Парсинг аргументов и опций
   - Валидация взаимоисключающих флагов
   - Вызов `_run_delete()`

2. **`_run_delete()`** — основная логика
   - Поиск `.xcstrings` файлов
   - Обработка каждого файла через `_process_file()`

3. **`_process_file()`** — обработка одного файла
   - Чтение каталога
   - Определение языков для удаления
   - Отображение таблицы
   - Запрос подтверждения
   - Удаление языков и сохранение

4. **`_show_deletion_table()`** — форматирование таблицы
   - Rich table с информацией о языках

5. **`_determine_languages_to_delete()`** — логика выбора языков
   - Обработка трех режимов
   - Защита source language

6. **`_delete_languages_from_catalog()`** — удаление из структуры
   - Удаление из `catalog.strings`
   - Обновление `_raw_data`

## Логика удаления языков

### Режим 1: Удалить все (`--all`)

```python
# Получить все существующие языки из каталога
existing_langs = set()
for entry in catalog.strings.values():
    existing_langs.update(entry.translations.keys())

# Удалить все кроме source
langs_to_delete = existing_langs - {catalog.source_language}
```

### Режим 2: Удалить указанные

```python
# Парсинг списка: "ro,uk,nl" -> ["ro", "uk", "nl"]
langs_to_delete = set(parse_language_list(languages))

# Защита source language
if catalog.source_language in langs_to_delete:
    console.print(f"[yellow]Warning:[/yellow] Source language '{catalog.source_language}' cannot be deleted (skipped)")
    langs_to_delete.remove(catalog.source_language)
```

### Режим 3: Удалить все кроме указанных (`--keep`)

```python
# Получить все существующие языки
existing_langs = set()
for entry in catalog.strings.values():
    existing_langs.update(entry.translations.keys())

# Языки для сохранения
keep_langs = set(parse_language_list(languages))
keep_langs.add(catalog.source_language)  # Всегда сохранять source

# Удалить все остальные
langs_to_delete = existing_langs - keep_langs
```

## Процесс удаления и сохранения

### Удаление переводов

```python
def _delete_languages_from_catalog(catalog: StringCatalog, languages: set[str]) -> dict[str, int]:
    """Удалить языки из каталога. Возвращает {lang: count}."""
    deleted_counts = {lang: 0 for lang in languages}

    # Удалить из entries
    for entry in catalog.strings.values():
        for lang in languages:
            if lang in entry.translations:
                del entry.translations[lang]
                deleted_counts[lang] += 1

    # Удалить из raw_data для lossless записи
    raw_data = catalog.get_raw_data()
    if raw_data and "strings" in raw_data:
        for key, entry_data in raw_data["strings"].items():
            if "localizations" in entry_data:
                locs = entry_data["localizations"]
                for lang in languages:
                    locs.pop(lang, None)

    return deleted_counts
```

### Сохранение файла

```python
write_xcstrings(catalog, file_path, backup=backup)
```

## Обработка ошибок и граничных случаев

### Валидация аргументов

- Взаимоисключающие опции `--all` и позиционный аргумент (без `--keep`)
- Требуется хотя бы один режим
- `--keep` требует список языков

### Граничные случаи

1. **Файл без переводов** — показать "No languages to delete"
2. **Указанные языки не существуют** — показать warning
3. **Попытка удалить source language** — показать warning и пропустить
4. **Пользователь отменил операцию** — завершить с кодом 0
5. **Ошибка записи файла** — показать ошибку и завершить с кодом 1

## Формат вывода

### До удаления (таблица)

```
File: Localizable.xcstrings
Languages to delete:
┌──────────────┬──────┬─────────┐
│ Language     │ Code │ Strings │
├──────────────┼──────┼─────────┤
│ Romanian     │ ro   │ 125     │
│ Ukrainian    │ uk   │ 118     │
│ Dutch        │ nl   │ 120     │
└──────────────┴──────┴─────────┘
Delete 3 languages? [y/N]:
```

### После удаления

```
✓ Deleted 3 languages from Localizable.xcstrings
  - Romanian (ro): 125 strings
  - Ukrainian (uk): 118 strings
  - Dutch (nl): 120 strings

Backup saved: Localizable.xcstrings.backup
```

## Тестирование

### Unit тесты (`tests/test_delete.py`)

1. `test_delete_all_languages` — режим `--all`
2. `test_delete_specific_languages` — удаление указанных
3. `test_delete_with_keep` — режим `--keep`
4. `test_cannot_delete_source_language` — защита source
5. `test_delete_non_existent_languages` — несуществующие языки
6. `test_lossless_deletion` — сохранение структуры JSON

### Интеграционные тесты

- Тест с реальными `.xcstrings` файлами
- Тест backup функциональности
- Тест множественных файлов
