# Скрипт для создания Pull Request master -> main
# Использование: .\create_pr.ps1

$repo = "ferixdi-png/5656"
$baseBranch = "main"
$headBranch = "master"
$title = "Merge: Kie.ai API Scraper improvements and Render deployment fixes"
$body = @"
## 🚀 Изменения

- ✅ Улучшенный парсинг API endpoints и параметров
- ✅ Валидация всех моделей с автоматическим исправлением
- ✅ Исправлены все ошибки для деплоя на Render
- ✅ Добавлена обработка исключений и кодировка UTF-8
- ✅ Созданы файлы для деплоя: runtime.txt, .renderignore, RENDER_DEPLOY.md

## 📁 Файлы

- `kie_api_scraper.py` - улучшенный скрипт парсинга
- `requirements.txt` - зависимости
- `runtime.txt` - версия Python
- `.renderignore` - игнорируемые файлы
- `RENDER_DEPLOY.md` - инструкция по деплою

## ✅ Проверки

- Все исключения обработаны
- Кодировка UTF-8 настроена
- Пути относительные
- Готово к деплою на Render.com
"@

Write-Host "🔗 Создание Pull Request..." -ForegroundColor Green
Write-Host ""

# Прямая ссылка для создания PR
$titleEncoded = [System.Web.HttpUtility]::UrlEncode($title)
$bodyEncoded = [System.Web.HttpUtility]::UrlEncode($body)
$prUrl = "https://github.com/$repo/compare/$baseBranch...$headBranch?expand=1&title=$titleEncoded&body=$bodyEncoded"

Write-Host "📋 Информация о PR:" -ForegroundColor Yellow
Write-Host "  Репозиторий: $repo" -ForegroundColor Cyan
Write-Host "  Из ветки: $headBranch" -ForegroundColor Cyan
Write-Host "  В ветку: $baseBranch" -ForegroundColor Cyan
Write-Host "  Заголовок: $title" -ForegroundColor Cyan
Write-Host ""

Write-Host "🌐 Откройте эту ссылку в браузере для создания PR:" -ForegroundColor Green
Write-Host $prUrl -ForegroundColor Cyan
Write-Host ""

# Попытка открыть в браузере
try {
    Start-Process $prUrl
    Write-Host "✅ Браузер открыт!" -ForegroundColor Green
} catch {
    Write-Host "⚠️ Не удалось открыть браузер автоматически" -ForegroundColor Yellow
    Write-Host "   Скопируйте ссылку выше и откройте вручную" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "📝 Или создайте PR вручную:" -ForegroundColor Yellow
Write-Host "   1. Перейдите: https://github.com/$repo" -ForegroundColor White
Write-Host "   2. Нажмите 'Compare and pull request'" -ForegroundColor White
Write-Host "   3. Заполните заголовок и описание" -ForegroundColor White
Write-Host "   4. Нажмите 'Create pull request'" -ForegroundColor White

