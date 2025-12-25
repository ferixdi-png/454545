#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Sync all PR branches with main to prevent merge conflicts.

.DESCRIPTION
    This script updates all PR branches (codex/develop-*) to be in sync with main,
    automatically resolving conflicts by accepting main's version of common files.

.EXAMPLE
    .\scripts\sync_pr_branches.ps1
#>

param(
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

Write-Host "рџ”„ Syncing PR branches with main..." -ForegroundColor Cyan

# Fetch all branches
Write-Host "`nрџ“Ґ Fetching branches..." -ForegroundColor Yellow
git fetch origin --all

# Get current main commit
$mainCommit = git rev-parse origin/main
Write-Host "рџ“Ќ Main is at: $mainCommit" -ForegroundColor Green

# Find all PR branches
$prBranches = git branch -r | 
    Select-String -Pattern "codex/develop-telegram-bot" | 
    ForEach-Object { $_.ToString().Trim().Replace("origin/", "") }

if ($prBranches.Count -eq 0) {
    Write-Host "вќЊ No PR branches found" -ForegroundColor Red
    exit 1
}

Write-Host "`nрџ“‹ Found $($prBranches.Count) PR branches:" -ForegroundColor Yellow
$prBranches | ForEach-Object { Write-Host "  - $_" }

$synced = 0
$conflicts = 0
$errors = 0

foreach ($branch in $prBranches) {
    Write-Host "`nрџ”„ Processing: $branch" -ForegroundColor Cyan
    
    try {
        # Create temporary branch
        $tempBranch = "sync-$branch-$(Get-Random)"
        git checkout -b $tempBranch "origin/$branch" 2>&1 | Out-Null
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  вљ пёЏ  Failed to checkout $branch" -ForegroundColor Yellow
            $errors++
            continue
        }
        
        # Try to merge main
        $mergeOutput = git merge origin/main --no-edit --no-ff 2>&1 | Out-String
        
        if ($mergeOutput -match "CONFLICT") {
            Write-Host "  вљ пёЏ  Conflicts detected, resolving..." -ForegroundColor Yellow
            $conflicts++
            
            # Resolve conflicts by accepting main's version
            git checkout --theirs .github/workflows/ci.yml README.md app/kie/generator.py main_render.py 2>&1 | Out-Null
            git add .github/workflows/ci.yml README.md app/kie/generator.py main_render.py 2>&1 | Out-Null
            
            # Check if there are staged changes
            $staged = git diff --cached --quiet
            if ($LASTEXITCODE -ne 0) {
                git commit -m "Sync with main: resolve conflicts automatically" --no-edit 2>&1 | Out-Null
                Write-Host "  вњ… Conflicts resolved" -ForegroundColor Green
            } else {
                Write-Host "  в„№пёЏ  No conflicts to resolve" -ForegroundColor Gray
            }
        } elseif ($mergeOutput -match "Already up to date") {
            Write-Host "  вњ… Already up to date" -ForegroundColor Green
        } else {
            Write-Host "  вњ… Fast-forwarded" -ForegroundColor Green
        }
        
        # Push if not dry run
        if (-not $DryRun) {
            git push origin "$tempBranch`:$branch" --force 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  вњ… Pushed to origin/$branch" -ForegroundColor Green
                $synced++
            } else {
                Write-Host "  вќЊ Failed to push $branch" -ForegroundColor Red
                $errors++
            }
        } else {
            Write-Host "  рџ”Ќ [DRY RUN] Would push to origin/$branch" -ForegroundColor Gray
            $synced++
        }
        
        # Cleanup
        git checkout main 2>&1 | Out-Null
        git branch -D $tempBranch 2>&1 | Out-Null
        
    } catch {
        Write-Host "  вќЊ Error processing $branch`: $_" -ForegroundColor Red
        $errors++
        
        # Cleanup on error
        git checkout main 2>&1 | Out-Null
        git branch -D "sync-$branch-*" 2>&1 | Out-Null
    }
}

Write-Host "`nрџ“Љ Summary:" -ForegroundColor Cyan
Write-Host "  вњ… Synced: $synced" -ForegroundColor Green
Write-Host "  вљ пёЏ  Conflicts resolved: $conflicts" -ForegroundColor Yellow
Write-Host "  вќЊ Errors: $errors" -ForegroundColor $(if ($errors -gt 0) { "Red" } else { "Green" })

if ($DryRun) {
    Write-Host "`nрџ’Ў This was a dry run. Use without -DryRun to actually push changes." -ForegroundColor Yellow
}