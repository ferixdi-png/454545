# Автоматический push на GitHub
# Использование: .\auto_push.ps1 [сообщение коммита]

param(
    [string]$CommitMessage = "Auto commit: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
)

Write-Host "🚀 АВТОМАТИЧЕСКИЙ PUSH НА GITHUB" -ForegroundColor Green
Write-Host "============================================================"

# Проверка что мы в git репозитории
if (-not (Test-Path .git)) {
    Write-Host "❌ Ошибка: Это не git репозиторий!" -ForegroundColor Red
    exit 1
}

# Проверка remote
$remote = git remote get-url origin 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Ошибка: Remote 'origin' не настроен!" -ForegroundColor Red
    exit 1
}

Write-Host "📡 Remote: $remote" -ForegroundColor Cyan

# Проверка изменений
Write-Host ""
Write-Host "📋 Проверка изменений..." -ForegroundColor Yellow
$status = git status --porcelain
if ([string]::IsNullOrWhiteSpace($status)) {
    Write-Host "✅ Нет изменений для коммита" -ForegroundColor Green
    exit 0
}

Write-Host "📝 Найдены изменения:" -ForegroundColor Yellow
git status --short

# Добавление всех изменений
Write-Host ""
Write-Host "📦 Добавление файлов..." -ForegroundColor Yellow
git add -A
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Ошибка при добавлении файлов" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Файлы добавлены" -ForegroundColor Green

# Создание коммита
Write-Host ""
Write-Host "💾 Создание коммита..." -ForegroundColor Yellow
Write-Host "   Сообщение: $CommitMessage" -ForegroundColor Cyan
git commit -m $CommitMessage
if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️ Не удалось создать коммит (возможно нет изменений)" -ForegroundColor Yellow
    exit 0
}
Write-Host "✅ Коммит создан" -ForegroundColor Green

# Определение текущей ветки
$branch = git branch --show-current
Write-Host ""
Write-Host "🌿 Текущая ветка: $branch" -ForegroundColor Cyan

# Push на GitHub
Write-Host ""
Write-Host "🚀 Push на GitHub..." -ForegroundColor Yellow
git push origin $branch
if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✅ УСПЕШНО! Изменения отправлены на GitHub" -ForegroundColor Green
    Write-Host "   🔗 Репозиторий: $remote" -ForegroundColor Cyan
    Write-Host "   🌿 Ветка: $branch" -ForegroundColor Cyan
} else {
    Write-Host ""
    Write-Host "❌ Ошибка при push" -ForegroundColor Red
    Write-Host "   Попробуйте: git push origin $branch --force-with-lease" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "============================================================"
