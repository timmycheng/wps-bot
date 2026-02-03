# encoding:utf-8
#
# Docker 镜像自动构建脚本 (PowerShell 版本)
# 功能:
# 1. 自动递增版本号
# 2. 构建 Docker 镜像
# 3. 保存镜像为 tar 包
#
# 使用方法:
#   .\build.ps1              # 递增 patch 版本号 (x.x.+1)
#   .\build.ps1 minor        # 递增 minor 版本号 (x.+1.0)
#   .\build.ps1 major        # 递增 major 版本号 (+1.0.0)
#   .\build.ps1 1.2.3        # 指定版本号
#

param(
    [string]$BumpType = "patch"
)

# 配置
$ImageName = "wps-bot"
$VersionFile = ".version"
$Dockerfile = "Dockerfile"

# 获取当前版本号
function Get-CurrentVersion {
    if (Test-Path $VersionFile) {
        return Get-Content $VersionFile -Raw
    } else {
        return "0.0.0"
    }
}

# 递增版本号
function Bump-Version {
    param(
        [string]$Version,
        [string]$Type
    )
    
    # 解析版本号
    $parts = $Version -split '\.'
    $major = [int]$parts[0]
    $minor = [int]$parts[1]
    $patch = [int]$parts[2]
    
    switch ($Type) {
        "major" {
            $major++
            $minor = 0
            $patch = 0
        }
        "minor" {
            $minor++
            $patch = 0
        }
        "patch" {
            $patch++
        }
        default {
            # 如果传入的是具体版本号
            if ($Type -match '^\d+\.\d+\.\d+$') {
                return $Type
            } else {
                Write-Error "无效的版本号格式: $Type"
                Write-Host "用法: .\build.ps1 [major|minor|patch|x.x.x]"
                exit 1
            }
        }
    }
    
    return "$major.$minor.$patch"
}

# 主流程
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "Docker 镜像自动构建脚本" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan

# 检查 Docker 是否可用
try {
    $dockerVersion = docker version --format '{{.Server.Version}}' 2>$null
    Write-Host "Docker 版本: $dockerVersion"
} catch {
    Write-Error "Docker 未安装或未运行!"
    exit 1
}

# 获取并递增版本号
$CurrentVersion = Get-CurrentVersion
$NewVersion = Bump-Version -Version $CurrentVersion -Type $BumpType

Write-Host ""
Write-Host "版本信息:" -ForegroundColor Yellow
Write-Host "  当前版本: $CurrentVersion"
Write-Host "  新版本:   $NewVersion" -ForegroundColor Green

# 保存新版本号
$NewVersion | Set-Content $VersionFile -NoNewline
Write-Host "  已保存到: $VersionFile"

# 构建镜像标签
$ImageTag = "${ImageName}:${NewVersion}"
$ImageLatest = "${ImageName}:latest"

Write-Host ""
Write-Host "构建镜像:" -ForegroundColor Yellow
Write-Host "  镜像名称: $ImageTag"
Write-Host "  Dockerfile: $Dockerfile"

# 构建 Docker 镜像
$buildOutput = docker build -f $Dockerfile -t $ImageTag -t $ImageLatest . 2>&1
$buildExitCode = $LASTEXITCODE

if ($buildExitCode -ne 0) {
    Write-Error "Docker 构建失败!"
    Write-Host $buildOutput
    exit 1
}

Write-Host "  ✓ 构建成功" -ForegroundColor Green

# 保存镜像为 tar 包
Write-Host ""
Write-Host "保存镜像:" -ForegroundColor Yellow
$TarFile = "${ImageName}-${NewVersion}.tar"
Write-Host "  文件名: $TarFile"

docker save $ImageTag -o $TarFile 2>&1 | Out-Null

if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker 保存失败!"
    exit 1
}

# 显示文件大小
$FileSize = (Get-Item $TarFile).Length
$FileSizeFormatted = if ($FileSize -gt 1GB) { 
    "{0:N2} GB" -f ($FileSize / 1GB) 
} elseif ($FileSize -gt 1MB) { 
    "{0:N2} MB" -f ($FileSize / 1MB) 
} else { 
    "{0:N2} KB" -f ($FileSize / 1KB) 
}

Write-Host "  ✓ 保存成功 (大小: $FileSizeFormatted)" -ForegroundColor Green

# 可选：压缩镜像
Write-Host ""
$Compress = Read-Host "是否压缩镜像文件? (y/N)"
if ($Compress -match '^[Yy]$') {
    Write-Host "  压缩中..."
    $TarFileGZ = "$TarFile.gz"
    
    # 使用 .NET 压缩
    $inputStream = [System.IO.File]::OpenRead($TarFile)
    $outputStream = [System.IO.File]::Create($TarFileGZ)
    $gzipStream = New-Object System.IO.Compression.GzipStream($outputStream, [System.IO.Compression.CompressionMode]::Compress)
    $inputStream.CopyTo($gzipStream)
    $gzipStream.Close()
    $outputStream.Close()
    $inputStream.Close()
    
    Remove-Item $TarFile
    
    $CompressedSize = (Get-Item $TarFileGZ).Length
    $CompressedSizeFormatted = if ($CompressedSize -gt 1GB) { 
        "{0:N2} GB" -f ($CompressedSize / 1GB) 
    } elseif ($CompressedSize -gt 1MB) { 
        "{0:N2} MB" -f ($CompressedSize / 1MB) 
    } else { 
        "{0:N2} KB" -f ($CompressedSize / 1KB) 
    }
    
    Write-Host "  ✓ 压缩完成 (大小: $CompressedSizeFormatted)" -ForegroundColor Green
    $TarFile = $TarFileGZ
}

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "构建完成!" -ForegroundColor Green
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "镜像信息:" -ForegroundColor Yellow
Write-Host "  标签: $ImageTag"
Write-Host "  最新: $ImageLatest"
Write-Host "  文件: $TarFile"
Write-Host ""
Write-Host "使用说明:" -ForegroundColor Yellow
Write-Host "  加载镜像: docker load -i $TarFile"
Write-Host "  运行容器: docker run -d --name wps-bot -p 8080:8080 $ImageTag"
Write-Host ""

# 返回新版本号（方便其他脚本调用）
return $NewVersion
