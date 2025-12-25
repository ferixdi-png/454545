# Скрипт для push на GitHub
# Использование: .\git_push.ps1 -RepoUrl "https://github.com/username/repo.git"

param(
    [Parameter(Mandatory=$true)]
    [string]$RepoUrl
)

Write-Host "🚀 ПОДГОТОВКА К PUSH НА GITHUB" -ForegroundColor Green
Write-Host "=" * 60

# Проверка наличия файлов
Write-Host "`n📋 Проверка файлов..." -ForegroundColor Yellow
$files = @("kie_api_scraper.py", "requirements.txt", "README.md", ".gitignore")
foreach ($file in $files) {
    if (Test-Path $file) {
        Write-Host "  ✅ $file" -ForegroundColor Green
    } else {
        Write-Host "  ❌ $file не найден!" -ForegroundColor Red
        exit 1
    }
}

# Добавление файлов
Write-Host "`n📦 Добавление файлов в git..." -ForegroundColor Yellow
git add kie_api_scraper.py requirements.txt README.md .gitignore
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✅ Файлы добавлены" -ForegroundColor Green
} else {
    Write-Host "  ❌ Ошибка при добавлении файлов" -ForegroundColor Red
    exit 1
}

# Коммит
Write-Host "`n💾 Создание коммита..." -ForegroundColor Yellow
$commitMessage = "Initial commit: Kie.ai API Scraper with full validation and responses"
git commit -m $commitMessage
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✅ Коммит создан" -ForegroundColor Green
} else {
    Write-Host "  ⚠️ Возможно, нет изменений для коммита" -ForegroundColor Yellow
}

# Проверка remote
Write-Host "`n🔗 Настройка remote репозитория..." -ForegroundColor Yellow
$remoteExists = git remote get-url origin 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ℹ️ Remote 'origin' уже настроен: $remoteExists" -ForegroundColor Cyan
    $update = Read-Host "  Обновить URL? (y/n)"
    if ($update -eq "y") {
        git remote set-url origin $RepoUrl
        Write-Host "  ✅ Remote обновлен" -ForegroundColor Green
    }
} else {
    git remote add origin $RepoUrl
    Write-Host "  ✅ Remote 'origin' добавлен: $RepoUrl" -ForegroundColor Green
}

# Push
Write-Host "`n🚀 Push на GitHub..." -ForegroundColor Yellow
Write-Host "  📡 URL: $RepoUrl" -ForegroundColor Cyan
Write-Host "  ⚠️ Убедитесь, что у вас есть доступ к репозиторию!" -ForegroundColor Yellow

$confirm = Read-Host "`nПродолжить push? (y/n)"
if ($confirm -eq "y") {
    git push -u origin main
    if ($LASTEXITCODE -ne 0) {
        # Попробуем master вместо main
        Write-Host "  ⚠️ Попытка push в ветку 'master'..." -ForegroundColor Yellow
        git push -u origin master
    }
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "`n✅ УСПЕШНО! Код отправлен на GitHub!" -ForegroundColor Green
        Write-Host "   🔗 Репозиторий: $RepoUrl" -ForegroundColor Cyan
    } else {
        Write-Host "`n❌ Ошибка при push. Проверьте:" -ForegroundColor Red
        Write-Host "   1. Доступ к репозиторию" -ForegroundColor Yellow
        Write-Host "   2. Правильность URL" -ForegroundColor Yellow
        Write-Host "   3. Настройки аутентификации GitHub" -ForegroundColor Yellow
    }
} else {
    Write-Host "`n⏸️ Push отменен пользователем" -ForegroundColor Yellow
}

Write-Host "`n" + ("=" * 60)

