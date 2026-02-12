# Руководство по использованию Plural Forms

## Быстрый старт

LocalizerX теперь полностью поддерживает перевод plural variations в xcstrings файлах!

### Пример 1: Базовый перевод с plurals

**Файл: Localizable.xcstrings**
```json
{
  "sourceLanguage": "en",
  "strings": {
    "notifications_count": {
      "comment": "Number of unread notifications",
      "localizations": {
        "en": {
          "variations": {
            "plural": {
              "one": {
                "stringUnit": {"value": "%d notification"}
              },
              "other": {
                "stringUnit": {"value": "%d notifications"}
              }
            }
          }
        }
      }
    }
  }
}
```

**Команда:**
```bash
localizerx translate Localizable.xcstrings --to ru --src en
```

**Результат (ru):**
- `one`: "%d уведомление" (1 уведомление)
- `few`: "%d уведомления" (2-4 уведомления)
- `many`: "%d уведомлений" (5+ уведомлений)

### Пример 2: С zero формой

```json
"items_selected": {
  "localizations": {
    "en": {
      "variations": {
        "plural": {
          "zero": {"stringUnit": {"value": "No items"}},
          "one": {"stringUnit": {"value": "%d item"}},
          "other": {"stringUnit": {"value": "%d items"}}
        }
      }
    }
  }
}
```

**Перевод на испанский:**
- `zero`: "Ningún elemento"
- `one`: "%d elemento"
- `other`: "%d elementos"

## Что исправлено

### ❌ Раньше (проблема):
```
Исходный текст:
- one: "%lld week"
- other: "%lld weeks"

Перевод на русский:
- ❌ Только: "%lld недель" (теряется единственное число!)
```

### ✅ Теперь (исправлено):
```
Исходный текст:
- one: "%lld week"
- other: "%lld weeks"

Перевод на русский:
- ✅ one: "%lld неделя"
- ✅ few: "%lld недели"
- ✅ many: "%lld недель"
```

## Поддерживаемые формы

LocalizerX корректно обрабатывает все CLDR plural категории:

| Форма  | Описание                    | Примеры языков       |
|--------|----------------------------|---------------------|
| zero   | Ноль (специальная форма)    | Arabic              |
| one    | Единственное число          | Все языки           |
| two    | Два (специальная форма)     | Arabic, Welsh       |
| few    | Малое количество (2-4)      | Russian, Polish     |
| many   | Большое количество (5+)     | Russian, Polish     |
| other  | Множественное/по умолчанию  | Все языки           |

## Особенности перевода

### 1. Сохранение плейсхолдеров

Все типы плейсхолдеров корректно сохраняются:
- `%lld`, `%d`, `%@` - printf-style
- `{count}`, `{{count}}` - template-style
- `$COUNT$` - uppercase-style

### 2. Кеширование

Каждая plural форма кешируется отдельно в SQLite:
- Повторные переводы используют кеш
- Кеш работает между разными файлами
- Ускоряет повторные запуски

### 3. Контекстные промпты

Gemini получает специализированные промпты для каждой формы:
```
Translate the following "one" form of a plural string...
This is the "one" plural form (e.g., singular)
Translate appropriately for this plural form in Russian
```

Это гарантирует правильный грамматический перевод каждой формы.

## Команды

### Базовый перевод
```bash
localizerx translate MyApp.xcstrings --to ru,es,de
```

### С предпросмотром
```bash
localizerx translate MyApp.xcstrings --to ru --preview
```

### Сухой запуск (посмотреть, что будет переведено)
```bash
localizerx translate MyApp.xcstrings --to ru --dry-run
```

### С бекапом
```bash
localizerx translate MyApp.xcstrings --to ru --backup
```

## Информация о файле

Проверить, какие строки имеют plurals:
```bash
localizerx info MyApp.xcstrings
```

## Тестирование

Запустить тесты plural форм:
```bash
pytest tests/test_xcstrings_plurals.py -v
```

Протестировать на примере:
```bash
localizerx translate examples/Plurals.xcstrings --to ru,es,fr,de,ja
```

## Известные проблемы

### Проблема: "У вас %d товаров в корзине"

Если русский перевод получился без разных форм для разных чисел, проверьте:

1. **Исходный файл имеет plural variations:**
   ```json
   "variations": {
     "plural": {
       "one": {"stringUnit": {"value": "%d item"}},
       "other": {"stringUnit": {"value": "%d items"}}
     }
   }
   ```

2. **Не простой stringUnit:**
   ```json
   // ❌ Неправильно (простая строка):
   "stringUnit": {"value": "You have %d items"}

   // ✅ Правильно (с plurals):
   "variations": {
     "plural": { ... }
   }
   ```

### Решение

Если исходный файл имеет только `stringUnit` без `variations`, Xcode должен автоматически создать plural variations при использовании String Interpolation с числами.

В коде Swift:
```swift
// Xcode автоматически создаст plural variations:
Text("You have \(count) items")
```

## Интеграция с Xcode

После перевода с LocalizerX:

1. Откройте `.xcstrings` файл в Xcode
2. Выберите язык (например, русский)
3. Вы увидите все plural формы: one, few, many
4. Можете вручную скорректировать при необходимости

## Поддержка

Если у вас остались вопросы или проблемы:

1. Проверьте `PLURALS_IMPLEMENTATION.md` для технических деталей
2. Запустите тесты: `pytest tests/test_xcstrings_plurals.py -v`
3. Создайте issue на GitHub с примером файла
