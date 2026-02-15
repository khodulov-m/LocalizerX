# Кастомные инструкции для перевода

## Описание

Начиная с текущей версии, LocalizerX поддерживает кастомные инструкции для перевода. Это позволяет вам задавать специфические правила, которых должен придерживаться переводчик.

## Использование

### Через CLI опцию

```bash
localizerx translate <path> --to fr,es,de \
  --custom-prompt "Do not translate proper names. Do not translate the word 'Water'"
```

Или с использованием короткого алиаса `--instructions`:

```bash
localizerx translate <path> --to fr,es,de \
  --instructions "Не переводи имена собственные. Не переводи слово Water"
```

### Через конфигурационный файл

Добавьте в `~/.config/localizerx/config.toml`:

```toml
[translator]
custom_instructions = "Do not translate proper names. Do not translate the word 'Water'"
```

Теперь эти инструкции будут применяться ко всем переводам по умолчанию.

## Примеры использования

### Сохранение брендовых названий

```bash
localizerx translate Localizable.xcstrings --to ru,ja \
  --custom-prompt "Do not translate brand names: iPhone, MacBook, AirPods"
```

### Сохранение технических терминов

```bash
localizerx translate Localizable.xcstrings --to de,fr \
  --custom-prompt "Keep technical terms in English: API, SDK, OAuth, webhook"
```

### Специфические правила для языка

```bash
localizerx translate Localizable.xcstrings --to ru \
  --custom-prompt "Use formal 'Вы' instead of informal 'ты'"
```

### Комплексные инструкции

```bash
localizerx translate Localizable.xcstrings --to es,pt-BR \
  --custom-prompt "1. Do not translate 'Water' - keep it in English
2. Use Latin American Spanish, not European Spanish
3. Keep all brand names in original form
4. Use informal tone (tú instead of usted)"
```

## Как это работает

Кастомные инструкции добавляются в промпт для Gemini API как дополнительное правило. Они применяются к:

- Обычным строкам перевода
- Пакетному переводу нескольких строк
- Множественным формам (plurals)

## Приоритет настроек

Если вы указываете и CLI опцию, и конфигурационный файл:

```bash
# config.toml содержит: custom_instructions = "Rule from config"
localizerx translate --custom-prompt "Rule from CLI"
```

CLI опция имеет приоритет над конфигурационным файлом.

## Рекомендации

1. **Будьте конкретны**: Четко формулируйте свои инструкции
2. **Короткие инструкции лучше**: Слишком длинные промпты могут снизить качество перевода
3. **Тестируйте с `--preview`**: Используйте опцию `--preview` для проверки результатов перед применением
4. **Используйте `--dry-run`**: Проверьте, какие строки будут переведены

## Пример workflow

```bash
# 1. Сначала посмотрим, что будет переведено
localizerx translate Localizable.xcstrings --to ru \
  --custom-prompt "Не переводи слово 'Water'" \
  --dry-run

# 2. Проверим предложенные переводы
localizerx translate Localizable.xcstrings --to ru \
  --custom-prompt "Не переводи слово 'Water'" \
  --preview

# 3. Применим перевод
localizerx translate Localizable.xcstrings --to ru \
  --custom-prompt "Не переводи слово 'Water'" \
  --backup
```

## Ограничения

- Кастомные инструкции работают только с командой `translate` (для `.xcstrings` файлов)
- Для других команд (`chrome`, `metadata`, `screenshots`) эта функциональность будет добавлена в будущих версиях
- Модель Gemini интерпретирует инструкции, но не гарантирует 100% соблюдение в сложных случаях

## Устранение проблем

Если кастомные инструкции не применяются:

1. Проверьте синтаксис в `config.toml` (должна быть строка в кавычках)
2. Убедитесь, что используете последнюю версию LocalizerX
3. Попробуйте более простые и прямые формулировки
4. Используйте `--preview` для проверки результатов
