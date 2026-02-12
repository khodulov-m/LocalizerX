# Changelog: Plural Forms Support

## Версия: Не выпущена (разработка)

### ✨ Новые возможности

#### Полная поддержка plural variations в xcstrings

Теперь LocalizerX корректно переводит все plural формы (one, few, many, other, zero, two).

**Пример проблемы (до исправления):**
```
Исходный текст (en):
- one: "%lld week"
- other: "%lld weeks"

Перевод (ru):
- ❌ Только: "%lld недель" (единственное число потеряно!)
```

**После исправления:**
```
Исходный текст (en):
- one: "%lld week"
- other: "%lld weeks"

Перевод (ru):
- ✅ one: "%lld неделя"
- ✅ few: "%lld недели"
- ✅ many: "%lld недель"
```

### 🔧 Изменения в API

#### Модель данных (`parser/model.py`)

- **Новое поле в `Entry`:**
  - `source_variations: dict[str, Any] | None` - хранит plural/gender формы из исходного языка

- **Новое свойство:**
  - `Entry.has_plurals` - проверка наличия plural форм

- **Обновлено свойство:**
  - `Entry.needs_translation` - теперь учитывает entries с plurals

#### Translator API (`translator/base.py`)

- **Новое поле в `TranslationRequest`:**
  - `plural_forms: dict[str, str] | None` - plural формы для перевода

- **Новое поле в `TranslationResult`:**
  - `translated_plurals: dict[str, str] | None` - переведённые plural формы

#### GeminiTranslator (`translator/gemini_adapter.py`)

- **Новый метод:**
  - `_translate_plural_forms()` - переводит каждую plural форму с отдельным контекстом

- **Обновлён метод:**
  - `translate_batch()` - обрабатывает запросы с `plural_forms`

#### CLI (`cli/translate.py`)

- Автоматически извлекает plural формы из source language
- Передаёт их в `TranslationRequest`
- Сохраняет переведённые plurals в правильной структуре `variations`

### 📁 Новые файлы

- `examples/Plurals.xcstrings` - тестовый файл с примерами plural форм
- `tests/test_xcstrings_plurals.py` - комплексные тесты для plurals
- `tests/test_plurals_parsing.py` - дополнительные тесты парсинга
- `PLURALS_IMPLEMENTATION.md` - техническая документация
- `PLURAL_USAGE_GUIDE.md` - руководство пользователя

### 🐛 Исправления

- **Критическое:** Plural формы теперь не теряются при переводе
- **Критическое:** Source language plural variations теперь корректно парсятся
- **Улучшение:** Entries с только plurals (без simple text) теперь распознаются как требующие перевода

### 🧪 Тесты

Добавлено 15+ новых тестов:
- Парсинг plural variations из xcstrings
- Перевод отдельных plural форм
- Batch перевод с plurals
- Смешанные batch (simple + plurals)
- Запись plural переводов в файл
- Round-trip тесты (чтение → запись → чтение)
- Edge cases

### 🚀 Производительность

- Каждая plural форма кешируется отдельно в SQLite
- Cache key: `plural:{form_name}:{text_hash}`
- Повторные переводы используют кеш
- Plural формы переводятся асинхронно

### 📚 Поддерживаемые plural формы

| Форма  | Пример языка      |
|--------|------------------|
| zero   | Arabic           |
| one    | Все языки        |
| two    | Arabic, Welsh    |
| few    | Russian, Polish  |
| many   | Russian, Polish  |
| other  | Все языки        |

### 🔄 Обратная совместимость

✅ Все изменения полностью обратно совместимы:
- Entries без plurals работают как раньше
- Новые поля имеют значение `None` по умолчанию
- Старые xcstrings файлы без plurals обрабатываются корректно

### 📖 Примеры использования

#### Базовый перевод
```bash
localizerx translate MyApp.xcstrings --to ru,es,de
```

#### С предпросмотром
```bash
localizerx translate MyApp.xcstrings --to ru --preview
```

#### Тестовый файл
```bash
localizerx translate examples/Plurals.xcstrings --to ru,es,fr,de,ja
```

### 🔍 Как проверить

```bash
# Запустить все тесты
pytest tests/test_xcstrings_plurals.py -v

# Проверить парсинг
pytest tests/test_plurals_parsing.py -v

# Проверить синтаксис
python3 -m py_compile localizerx/**/*.py
```

### 📝 Примечания

1. **Качество перевода:** Каждая plural форма переводится с отдельным промптом, указывающим Gemini, что это за форма (one/few/many), что улучшает качество перевода.

2. **Кеширование:** Plural формы кешируются независимо, что ускоряет повторные переводы.

3. **Структура данных:** Используется native xcstrings формат для variations, обеспечивая полную совместимость с Xcode.

### 🎯 Что дальше

В будущих версиях можно оптимизировать:
- Группировать plural формы в один API вызов (сейчас каждая форма = отдельный вызов)
- Добавить поддержку gender variations (сейчас только plurals)
- Добавить валидацию plural форм для целевого языка

### 👥 Contributors

- Implementation: Claude Sonnet 4.5
- Reported by: @mdmrk
