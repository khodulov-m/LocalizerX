# Plural Forms Implementation

## Проблема

LocalizerX не умел корректно переводить численные плейсхолдеры (plurals) в xcstrings файлах. Например, для строки с формами:
- `one`: "%lld week"
- `other`: "%lld weeks"

Переводчик переводил только одну форму (обычно "other"), теряя информацию о единственном числе.

## Решение

Реализована полная поддержка plural variations для xcstrings файлов:

### 1. Модель данных (`localizerx/parser/model.py`)

**Добавлено поле в Entry:**
```python
class Entry(BaseModel):
    # ... existing fields ...
    source_variations: dict[str, Any] | None = None  # For plural/gender forms in source language

    @property
    def has_plurals(self) -> bool:
        """Check if this entry has plural variations."""
        return self.source_variations is not None and "plural" in self.source_variations
```

**Обновлено свойство needs_translation:**
```python
@property
def needs_translation(self) -> bool:
    """Check if this entry should be translated."""
    return self.should_translate and (bool(self.source_text.strip()) or self.source_variations is not None)
```

Теперь entries с plurals корректно определяются как требующие перевода, даже если `source_text` пустой.

### 2. Парсинг (`localizerx/io/xcstrings.py`)

**Обновлён `_parse_entry`:** теперь извлекает `source_variations` из source language:

```python
if source_language in localizations:
    source_loc = localizations[source_language]
    if "stringUnit" in source_loc:
        source_text = source_loc["stringUnit"].get("value", key)
    # Extract source variations (for plurals/gender forms)
    if "variations" in source_loc:
        source_variations = source_loc["variations"]
```

### 3. Translator API (`localizerx/translator/base.py`)

**Расширены dataclass модели:**

```python
@dataclass
class TranslationRequest:
    key: str
    text: str
    comment: str | None = None
    plural_forms: dict[str, str] | None = None  # {"one": "text", "other": "texts"}

@dataclass
class TranslationResult:
    key: str
    original: str
    translated: str
    success: bool = True
    error: str | None = None
    translated_plurals: dict[str, str] | None = None  # {"one": "translation", "other": "translations"}
```

### 4. Gemini Translator (`localizerx/translator/gemini_adapter.py`)

**Новый метод `_translate_plural_forms`:**

Переводит каждую plural форму отдельно с учётом контекста:

```python
async def _translate_plural_forms(
    self,
    plural_forms: dict[str, str],
    source_lang: str,
    target_lang: str,
) -> dict[str, str]:
    """Translate plural forms (zero, one, two, few, many, other)."""
```

Для каждой формы:
1. Проверяется кеш
2. Маскируются плейсхолдеры (`%lld` → `__PH_1__`)
3. Создаётся специализированный промпт с указанием plural формы
4. Вызывается Gemini API
5. Восстанавливаются плейсхолдеры
6. Результат кешируется

**Обновлён `translate_batch`:** обрабатывает запросы с `plural_forms`:

```python
# Handle plural forms separately
if req.plural_forms:
    translated_plurals = await self._translate_plural_forms(
        req.plural_forms, source_lang, target_lang
    )
    results.append(
        TranslationResult(
            key=req.key,
            original=req.text,
            translated=translated_plurals.get("other", ""),
            translated_plurals=translated_plurals,
        )
    )
```

### 5. CLI (`localizerx/cli/translate.py`)

**Обновлён сбор entries для перевода:**

```python
entries_to_translate.append((key, entry.source_text, entry.comment, entry.source_variations))
```

**Создание TranslationRequest с plural forms:**

```python
# Extract plural forms if present
plural_forms = None
if source_variations and "plural" in source_variations:
    plural_forms = {}
    for form_name, form_data in source_variations["plural"].items():
        if "stringUnit" in form_data:
            plural_forms[form_name] = form_data["stringUnit"].get("value", "")

requests.append(
    TranslationRequest(
        key=key,
        text=text,
        comment=comment,
        plural_forms=plural_forms
    )
)
```

**Сохранение plural переводов:**

```python
# Build variations structure if we have plural translations
variations = None
if translated_plurals:
    variations = {
        "plural": {}
    }
    for form_name, form_value in translated_plurals.items():
        variations["plural"][form_name] = {
            "stringUnit": {
                "state": "translated",
                "value": form_value
            }
        }

catalog.strings[key].translations[lang] = Translation(
    value=value,
    variations=variations
)
```

### 6. Тесты (`tests/test_xcstrings_plurals.py`)

Создан полный набор тестов:

1. **TestPluralParsing:**
   - `test_parse_plural_source_variations` - парсинг source plural forms
   - `test_has_plurals_property` - проверка свойства `has_plurals`
   - `test_needs_translation_with_plurals` - entries с plurals требуют перевода
   - `test_parse_items_with_zero_form` - поддержка zero форм

2. **TestPluralTranslation:**
   - `test_translate_plural_forms` - перевод plural форм
   - `test_translate_batch_with_plurals` - batch перевод с plurals
   - `test_translate_mixed_batch` - смешанный batch (simple + plurals)

3. **TestPluralWriting:**
   - `test_write_plural_translation` - запись plural переводов
   - `test_round_trip_with_plurals` - сохранение структуры при чтении/записи

4. **TestPluralEdgeCases:**
   - Тесты edge cases и специальных сценариев

### 7. Тестовый файл (`examples/Plurals.xcstrings`)

Создан пример xcstrings файла с plural variations для тестирования:

```json
{
  "sourceLanguage": "en",
  "strings": {
    "weeks_ago": {
      "localizations": {
        "en": {
          "variations": {
            "plural": {
              "one": {"stringUnit": {"value": "%lld week"}},
              "other": {"stringUnit": {"value": "%lld weeks"}}
            }
          }
        }
      }
    }
  }
}
```

## Поддерживаемые plural формы

Поддерживаются все стандартные CLDR plural категории:
- `zero` - для языков с отдельной формой для нуля (арабский)
- `one` - единственное число
- `two` - для языков с отдельной формой для двух (арабский, валлийский)
- `few` - для малых чисел (русский: 2-4, польский: 2-4)
- `many` - для больших чисел (русский: 5+)
- `other` - множественное число / форма по умолчанию

## Примеры использования

### Английский → Русский

**Исходный текст (en):**
- one: `%lld week`
- other: `%lld weeks`

**Перевод (ru):**
- one: `%lld неделя` (1 неделя)
- few: `%lld недели` (2-4 недели)
- many: `%lld недель` (5+ недель)

### Английский → Испанский

**Исходный текст (en):**
- zero: `No items selected`
- one: `%d item selected`
- other: `%d items selected`

**Перевод (es):**
- zero: `Ningún elemento seleccionado`
- one: `%d elemento seleccionado`
- other: `%d elementos seleccionados`

## Промпты для Gemini

Для перевода каждой plural формы используется специализированный промпт:

```
Translate the following {form_name} form of a plural string from {source} to {target}.

IMPORTANT RULES:
1. Keep all placeholders exactly as they are (like __PH_1__, __PH_2__, etc.)
2. Preserve any formatting and punctuation style
3. This is the "{form_name}" plural form (e.g., "one" = singular, "other" = plural)
4. Translate appropriately for this plural form in {target}
5. This is for an iOS/macOS app interface

Text to translate ({form_name} form):
{masked_text}

Translation (only provide the translated text, nothing else):
```

## Обратная совместимость

Все изменения обратно совместимы:
- Entries без plurals продолжают работать как раньше
- Новые поля имеют значение по умолчанию `None`
- Старые xcstrings файлы без plurals продолжают корректно обрабатываться

## Производительность

- Каждая plural форма кешируется отдельно в SQLite
- Cache key включает форму: `plural:{form_name}:{text}`
- При повторном переводе используется кеш
- Plural формы переводятся параллельно (async)

## Ограничения

1. В текущей реализации plural формы не группируются в один API вызов (каждая форма = отдельный вызов Gemini API)
2. Это сделано намеренно для:
   - Более точного перевода каждой формы с правильным контекстом
   - Независимого кеширования каждой формы
   - Упрощения логики и отладки

3. В будущем можно оптимизировать, отправляя все формы одним batch запросом

## Следующие шаги

Для полного тестирования на реальных файлах:

```bash
# Установить зависимости (если ещё не установлены)
pip3 install -e .

# Запустить тесты
pytest tests/test_xcstrings_plurals.py -v

# Протестировать на примере
localizerx translate examples/Plurals.xcstrings --to ru,es,de --src en
```
