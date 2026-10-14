#!/bin/zsh
# Package yun-laya for other people: build the .app, zip it, checksum it, optionally publish.
#
# Why ditto instead of "访达右键压缩" or plain `zip`: ditto is the tool Apple itself uses
# to ship bundles — it keeps POSIX permissions, extended attributes and resource forks.
# More to the point, this script is the thing that *checks* the artifact: it unpacks the
# zip again and verifies the launcher came out executable, so a broken zip cannot be
# published silently.
#
# Usage:
#   ./packaging/release.sh                     # -> dist/yun-laya-macos-v<version>.zip + SHA256SUMS
#   ./packaging/release.sh --out /tmp/rel      # somewhere else
#   ./packaging/release.sh --sign "Developer ID Application: X (TEAM)"
#                                              # 有开发者证书才用；--sign - 是 ad-hoc（不解决 Gatekeeper）
#   ./packaging/release.sh --publish           # 建 GitHub Release 并上传（需要 gh 已登录）
#   ./packaging/release.sh --publish --target <commit>
#                                              # 把 release 钉在某个提交上（默认是默认分支最新提交）
#
# The build itself lives in build_app.sh — one build entry point, not two.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/dist"
SIGN=""
TARGET=""
PUBLISH=0

while [ $# -gt 0 ]; do
    case "$1" in
        --out)     OUT="${2:-}";     [ -n "$OUT" ]    || { echo "--out 需要目录" >&2; exit 2; }; shift 2 ;;
        --sign)    SIGN="${2:-}";    [ -n "$SIGN" ]   || { echo "--sign 需要证书名（ad-hoc 写 -）" >&2; exit 2; }; shift 2 ;;
        --target)  TARGET="${2:-}";  [ -n "$TARGET" ] || { echo "--target 需要提交/分支名" >&2; exit 2; }; shift 2 ;;
        --publish) PUBLISH=1; shift ;;
        -h|--help) sed -n '2,24p' "$0"; exit 0 ;;
        *) echo "未知参数：$1（--help 看用法）" >&2; exit 2 ;;
    esac
done

# This personal fork has only the original project's upstream remote. Publishing with
# gh's implicit repository selection could create a release in that project.
if [ "$PUBLISH" = 1 ]; then
    echo "yun-laya 尚未配置自己的发布仓库；当前只支持本地打包。" >&2
    exit 2
fi

VERSION="$(sed -n 's/^version *= *"\([^"]*\)".*/\1/p' "$ROOT/pyproject.toml" | head -1)"
if [ -z "$VERSION" ]; then
    echo "读不到 pyproject.toml 里的 version" >&2
    exit 1
fi
mkdir -p "$OUT"

# GitHub's release API only resolves a full commit SHA or a branch name for target_commitish
# (a short SHA comes back as "target_commitish is invalid"), so resolve it here
if [ -n "$TARGET" ]; then
    if ! TARGET_SHA="$(git -C "$ROOT" rev-parse --verify "$TARGET^{commit}" 2>/dev/null)" || [ -z "$TARGET_SHA" ]; then
        echo "--target 找不到这个提交：$TARGET" >&2
        exit 2
    fi
    TARGET="$TARGET_SHA"
fi

echo "==> 构建 .app"
"$ROOT/packaging/build_app.sh"
APP="$ROOT/yun-laya.app"

# the zip carries whatever is on disk, so say it out loud when that is not a commit
if [ -n "$(git -C "$ROOT" status --porcelain)" ]; then
    echo "    注意：工作区有未提交改动，zip 里是当前磁盘内容（不是某个提交的状态）"
fi

if [ -n "$SIGN" ]; then
    echo "==> 签名：$SIGN"
    # --deep: this bundle has no nested code, but it seals the launcher script too
    codesign --force --deep --sign "$SIGN" "$APP"
    codesign --verify --strict "$APP"
    echo "    签名已校验"
else
    echo "==> 跳过签名（本机没有开发者证书）"
fi

ZIP="$OUT/yun-laya-macos-v$VERSION.zip"
rm -f "$ZIP"
echo "==> 压缩"
# --keepParent: the zip must contain yun-laya.app/ itself, so unzipping gives an app
ditto -c -k --sequesterRsrc --keepParent "$APP" "$ZIP"
( cd "$OUT" && shasum -a 256 "$(basename "$ZIP")" > SHA256SUMS )
# fixed asset name so releases/latest/download/<name> is a permanent link (brew taps,
# installers, docs): uploaded alongside the versioned zip on every release (#31)
STABLE="$OUT/yun-laya-macos-latest.zip"
cp "$ZIP" "$STABLE"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "==> 校验（把 zip 解压回来，模拟别人拿到的样子）"
ditto -x -k "$ZIP" "$TMP"
check() {
    if ! eval "$2" >/dev/null 2>&1; then
        echo "    ✗ $1" >&2
        exit 1
    fi
    echo "    ✓ $1"
}
check "解压得到 yun-laya.app"      "[ -d '$TMP/yun-laya.app' ]"
check "启动器带可执行权限"            "[ -x '$TMP/yun-laya.app/Contents/MacOS/yun-laya' ]"
check "启动器是原生 Mach-O"           "file '$TMP/yun-laya.app/Contents/MacOS/yun-laya' | grep -q 'Mach-O'"
check "bootstrap 带可执行权限"        "[ -x '$TMP/yun-laya.app/Contents/Resources/launcher.zsh' ]"
check "Info.plist 合法"             "plutil -lint '$TMP/yun-laya.app/Contents/Info.plist'"
check "图标在"                      "[ -f '$TMP/yun-laya.app/Contents/Resources/AppIcon.icns' ]"
check "包内 Python 版本已钉住"        "[ -f '$TMP/yun-laya.app/Contents/Resources/app/.python-version' ]"

echo "==> 完成"
du -sh "$ZIP" | awk '{print "    zip 体积: " $1}'
echo "    文件: $ZIP"
echo "    校验: $(cat "$OUT/SHA256SUMS")"

if [ "$PUBLISH" = 1 ]; then
    echo "==> 建 GitHub Release"
    command -v gh >/dev/null 2>&1 || { echo "    没装 gh，先 brew install gh" >&2; exit 1; }
    TAG="v$VERSION"
    if git -C "$ROOT" rev-parse -q --verify "refs/tags/$TAG" >/dev/null; then
        echo "    标签 $TAG 已存在，先在 pyproject.toml 里升版本" >&2
        exit 1
    fi
    NOTES="$TMP/notes.md"
    {
        echo "需要 **macOS 13+**。下载即用：解压后把 \`yun-laya.app\` 拖进「应用程序」。"
        echo
        echo "**第一次打开**：右键（或按住 Control 点）→ 打开 → 再点「打开」。未做 Apple 公证，双击会被 Gatekeeper 拦，只需这一次。"
        echo "若弹「**已损坏，无法打开**」（浏览器下载常见，右键无效）：终端执行 \`sudo xattr -r -d com.apple.quarantine /Applications/yun-laya.app\` 后再打开。"
        echo "**第一次启动**：联网装依赖（uv 缓存命中就很快）；只需给 \`yun-laya\` 授予「屏幕录制」权限，然后退出重开，无需单独授权 \`python3.12\`。"
        echo "**判断层默认跑本地模型，首次要下载约 3.8 GB**（之后离线可用）。不想下载：在 \`~/.config/yun-laya/env\` 里给判断层配一个 key 走云端，见 README「配置」。"
        echo
        echo "### 本次包含"
        PREV="$(git -C "$ROOT" describe --tags --abbrev=0 2>/dev/null || true)"
        if [ -n "$PREV" ]; then
            # awk 而非 head：head 截断会让 git log 收到 SIGPIPE，pipefail+set -e 下
            # 静默杀死整个脚本（退出 141）——v0.5.0 发布时实测死过两次
            git -C "$ROOT" log --pretty='- %s' "$PREV..HEAD" | awk 'NR<=20'
        else
            git -C "$ROOT" log --pretty='- %s' | awk 'NR<=20'
        fi
    } > "$NOTES"
    RELEASE_ARGS=("$TAG" "$ZIP" "$STABLE" "$OUT/SHA256SUMS" --title "yun-laya $TAG" --notes-file "$NOTES" --latest)
    # pin the tag: without --target gh tags the default branch tip, which may have moved
    # since the zip was built
    [ -n "$TARGET" ] && RELEASE_ARGS+=(--target "$TARGET")
    gh release create "${RELEASE_ARGS[@]}"
    echo "    已发布 $TAG（含稳定名资产 yun-laya-macos-latest.zip）"

    # post-publish self-check (#31): never trust the default "Latest" pointer — a late
    # hotfix of an old version would silently re-point every latest/ download URL
    echo "==> 发布自检（Latest 指针 + 稳定链接）"
    latest=""
    for _ in 1 2 3; do
        sleep 5
        latest="$(gh api repos/:owner/:repo/releases/latest --jq .tag_name 2>/dev/null || true)"
        [ "$latest" = "$TAG" ] && break
    done
    if [ "$latest" != "$TAG" ]; then
        echo "    ✗ Latest 指针指向 ${latest:-<无>} 而非 $TAG，手动修正：gh release edit $TAG --latest" >&2
        exit 1
    fi
    echo "    ✓ Latest 指针 = $TAG"
    slug="$(gh repo view --json nameWithOwner --jq .nameWithOwner)"
    code="$(curl -sIL -o /dev/null -w '%{http_code}' "https://github.com/$slug/releases/latest/download/yun-laya-macos-latest.zip" || true)"
    if [ "$code" != "200" ]; then
        echo "    ✗ 稳定链接不可用（HTTP $code），检查资产 yun-laya-macos-latest.zip 是否上传成功" >&2
        exit 1
    fi
    echo "    ✓ 稳定链接可下载（releases/latest/download/yun-laya-macos-latest.zip）"
else
    echo
    echo "    已生成本地安装包；此个人项目未配置发布仓库。"
fi
