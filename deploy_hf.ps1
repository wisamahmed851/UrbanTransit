$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Deploying UrbanTransit API to Hugging Face" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 1. Ask for Hugging Face Token (hidden input)
$token = Read-Host "Please paste your Hugging Face Access Token (starts with hf_...)" -AsSecureString
$tokenStr = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto([System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($token))

if ([string]::IsNullOrWhiteSpace($tokenStr)) {
    Write-Host "Token cannot be empty. Exiting." -ForegroundColor Red
    exit
}

# 2. Setup Git remote using the token for auth
Write-Host "`nConfiguring Git Remote..." -ForegroundColor Yellow
$remoteUrl = "https://__token__:$tokenStr@huggingface.co/spaces/ArhamAzeem/UrbanTransitAPI"

# Remove old 'hf' remote if it exists
git remote remove hf 2>$null
git remote add hf $remoteUrl

# 3. Track large files using Git LFS
Write-Host "`nSetting up Git LFS for large ML models..." -ForegroundColor Yellow
git lfs install
git lfs track "*.pkl"
git add .gitattributes

# 4. Add required files
Write-Host "`nStaging files for deployment..." -ForegroundColor Yellow
git add hf_app.py requirements.txt src/ config.py models/ database/ .env.example

# 5. Commit
Write-Host "`nCommitting changes..." -ForegroundColor Yellow
git commit -m "Automated Deployment to Hugging Face Spaces" 2>$null

# 6. Push
Write-Host "`nPushing 1.7GB of models and code to Hugging Face (This will take a few minutes)..." -ForegroundColor Magenta
git push hf main --force

Write-Host "`n==========================================" -ForegroundColor Green
Write-Host "Deployment Completed! Check your Hugging Face Space page." -ForegroundColor Green
Write-Host "Don't forget to add your TiDB MYSQL_ variables in the Hugging Face Space Settings!" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Green
