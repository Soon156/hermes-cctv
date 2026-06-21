#!/usr/bin/env bash
# shellcheck disable=SC2059
# Hermes CCTV — interactive first-time setup wizard
set -euo pipefail

# ── Colors ──────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
DIM='\033[2m'

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_FILE="$PROJECT_DIR/config.yaml"
SKILL_DIR="$HOME/.hermes/skills/hermes-cctv"
SCRIPT_DIR="$HOME/.hermes/scripts"
CONTROL_DIR="$HOME/.hermes/cctv"

# ── Banner ──────────────────────────────────────────────
banner() {
    clear 2>/dev/null || true
    printf "${CYAN}"
    printf "╔══════════════════════════════════════════╗\n"
    printf "║       Hermes CCTV — Setup Wizard        ║\n"
    printf "║           v0.1.0                        ║\n"
    printf "╚══════════════════════════════════════════╝\n"
    printf "${NC}\n"
    printf "  ${DIM}Values in [brackets] are defaults — press Enter to accept.${NC}\n"
    echo ""
}

# ── Helpers ─────────────────────────────────────────────
lower() { echo "$1" | tr '[:upper:]' '[:lower:]'; }
ok()   { printf "  ${GREEN}✓${NC} %s\n" "$1"; }
warn() { printf "  ${YELLOW}⚠${NC} %s\n" "$1"; }
fail() { printf "  ${RED}✗${NC} %s\n" "$1"; exit 1; }
info() { printf "  ${BLUE}ℹ${NC} %s\n" "$1"; }

# cfg reads a "key: value" line from the existing config.yaml (first match),
# stripping the trailing "# comment" and surrounding whitespace. Empty if
# the file or key is absent — callers fall back to a built-in default.
cfg() {
    [ -f "$CONFIG_FILE" ] || return 0
    # A missing key makes grep exit 1; with `set -o pipefail` that would
    # abort the script, so swallow it and just return an empty value.
    grep -E "^[[:space:]]*$1:" "$CONFIG_FILE" 2>/dev/null \
        | head -1 \
        | sed -E "s/^[[:space:]]*$1:[[:space:]]*//; s/[[:space:]]*#.*$//" \
        | tr -d '\r' \
        | sed -E 's/[[:space:]]+$//' \
        || true
}

# show_current_config prints the existing config.yaml (if any) so the user
# can see what they're editing before the prompts pre-fill from it.
show_current_config() {
    if [ -f "$CONFIG_FILE" ]; then
        printf "  ${BOLD}Current configuration${NC} ${DIM}(%s)${NC}\n" "$CONFIG_FILE"
        printf "  ${DIM}Prompts below are pre-filled with these values — Enter keeps them.${NC}\n\n"
        while IFS= read -r line; do
            printf "    ${DIM}%s${NC}\n" "$line"
        done < "$CONFIG_FILE"
    else
        info "No existing config.yaml — prompts will use built-in defaults."
    fi
    echo ""
}

# ask prints a highlighted input prompt and returns the user's response.
# The prompt text should include a [default] in brackets if one exists.
# An optional second argument is shown as a dim hint line above the prompt
# (e.g. the suggested range) to signal the value is customizable.
# Prints the prompt to stderr so it's visible even inside $(...) command substitution.
ask() {
    if [ -n "${2:-}" ]; then
        printf "\n  ${DIM}↳ %s${NC}" "$2" >&2
    fi
    printf "\n  ${CYAN}${BOLD}▸${NC} ${BOLD}%s${NC} " "$1" >&2
    read -r REPLY
    echo "$REPLY"
}

# confirm asks a yes/no question. Returns 0 for yes, 1 for no.
# Default is yes when prompt ends in [Y/n], no when [y/N].
confirm() {
    local prompt="$1"
    local default_yes=true
    if echo "$prompt" | grep -q '\[y/N\]'; then
        default_yes=false
    fi
    printf "\n  ${CYAN}${BOLD}▸${NC} ${BOLD}%s${NC} " "$prompt" >&2
    read -r REPLY
    local ans
    ans=$(echo "$REPLY" | tr '[:upper:]' '[:lower:]')
    if [ -z "$ans" ]; then
        $default_yes && return 0 || return 1
    fi
    case "$ans" in
        y|yes) return 0 ;;
        *)     return 1 ;;
    esac
}

# ── Step 1: Prerequisites ───────────────────────────────
check_prereqs() {
    printf "${BOLD}Step 1/7${NC} — Checking prerequisites\n\n"

    # Python
    if command -v python3 >/dev/null 2>&1; then
        PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
        PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
        if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 10 ]; then
            ok "Python $PY_VER"
        else
            fail "Python 3.10+ required (found $PY_VER). Install from https://python.org"
        fi
    else
        fail "Python 3 not found. Install from https://python.org"
    fi

    # Camera
    CAM_FOUND=false
    if python3 -c "import cv2; cap=cv2.VideoCapture(0); print(cap.isOpened()); cap.release()" 2>/dev/null | grep -q "True"; then
        ok "Camera device 0 detected"
        CAM_FOUND=true
    elif python3 -c "import cv2; cap=cv2.VideoCapture(1); print(cap.isOpened()); cap.release()" 2>/dev/null | grep -q "True"; then
        ok "Camera device 1 detected"
        CAM_FOUND=true
    else
        warn "No camera detected (OpenCV not installed yet or camera unavailable)"
        warn "You can configure the camera device ID later in config.yaml"
    fi

    # Hermes
    if command -v hermes >/dev/null 2>&1; then
        ok "Hermes Agent CLI found"
        HERMES_FOUND=true
    else
        warn "Hermes Agent CLI not found"
        warn "Gateway control (/cctv on|off) and notifications need Hermes"
        warn "Install: curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash"
        HERMES_FOUND=false
    fi

    echo ""
}

# ── Step 2: Python environment ──────────────────────────
setup_venv() {
    printf "${BOLD}Step 2/7${NC} — Setting up Python environment\n\n"

    if [ -d "$PROJECT_DIR/venv" ]; then
        info "Virtual environment already exists"
        if confirm "Recreate? [y/N]"; then
            rm -rf "$PROJECT_DIR/venv"
            info "Removed old venv"
        else
            ok "Keeping existing venv"
            echo ""
            return
        fi
    fi

    printf "  Creating virtual environment..."
    python3 -m venv "$PROJECT_DIR/venv" 2>&1 | tail -1
    ok "venv created"

    printf "  Installing dependencies..."
    "$PROJECT_DIR/venv/bin/pip" install -q -e "$PROJECT_DIR[dev]" 2>&1 | tail -1
    ok "Dependencies installed"

    echo ""
}

# ── Step 3: Camera ──────────────────────────────────────
configure_camera() {
    printf "${BOLD}Step 3/7${NC} — Camera settings\n\n"

    printf "  Available cameras (OpenCV detection):\n"
    "$PROJECT_DIR/venv/bin/python3" "$PROJECT_DIR/scripts/detect-cameras.py" 2>/dev/null || {
        warn "No cameras detected (or OpenCV not installed)"
        warn "You can configure the camera device ID later in config.yaml"
    }

    DEFAULT_DEV="$(cfg device_id)"; DEFAULT_DEV="${DEFAULT_DEV:-0}"
    REPLY=$(ask "Camera device ID [$DEFAULT_DEV]" "0 = built-in/default camera, 1+ = additional cameras (see list above)")
    DEVICE_ID="${REPLY:-$DEFAULT_DEV}"

    DEFAULT_WIDTH="$(cfg width)"; DEFAULT_WIDTH="${DEFAULT_WIDTH:-640}"
    REPLY=$(ask "Resolution width [$DEFAULT_WIDTH]" "common: 640 / 1280 / 1920 — higher = sharper but more CPU & disk")
    WIDTH="${REPLY:-$DEFAULT_WIDTH}"

    DEFAULT_HEIGHT="$(cfg height)"; DEFAULT_HEIGHT="${DEFAULT_HEIGHT:-480}"
    REPLY=$(ask "Resolution height [$DEFAULT_HEIGHT]" "match the width: 480 (640) / 720 (1280) / 1080 (1920)")
    HEIGHT="${REPLY:-$DEFAULT_HEIGHT}"

    DEFAULT_FPS="$(cfg fps)"; DEFAULT_FPS="${DEFAULT_FPS:-15}"
    REPLY=$(ask "FPS [$DEFAULT_FPS]" "suggested 10–30 — higher = smoother but more CPU; 15 is plenty for CCTV")
    FPS="${REPLY:-$DEFAULT_FPS}"

    ok "Camera: device=$DEVICE_ID, ${WIDTH}x${HEIGHT} @ ${FPS}fps"
    echo ""
}

# ── Step 4: Motion sensitivity ──────────────────────────
configure_motion() {
    printf "${BOLD}Step 4/7${NC} — Motion detection\n\n"

    # Pre-fill from the existing config and pick the matching preset.
    CUR_THRESHOLD="$(cfg threshold)"; CUR_THRESHOLD="${CUR_THRESHOLD:-30}"
    CUR_MIN_AREA="$(cfg min_area)";   CUR_MIN_AREA="${CUR_MIN_AREA:-2500}"
    case "$CUR_THRESHOLD/$CUR_MIN_AREA" in
        40/5000) PRESET_DEFAULT=1 ;;
        30/2500) PRESET_DEFAULT=2 ;;
        20/1000) PRESET_DEFAULT=3 ;;
        *)       PRESET_DEFAULT=4 ;;
    esac

    printf "  Sensitivity presets ${DIM}(current: threshold=%s, min_area=%s)${NC}:\n" \
        "$CUR_THRESHOLD" "$CUR_MIN_AREA"
    printf "    ${GREEN}1${NC} — Low  (threshold=40, min_area=5000) — only large movement\n"
    printf "    ${YELLOW}2${NC} — Medium (threshold=30, min_area=2500) — default (recommended)\n"
    printf "    ${RED}3${NC} — High (threshold=20, min_area=1000) — detects everything\n"
    printf "    ${CYAN}4${NC} — Custom (keep/edit current)\n"

    REPLY=$(ask "Sensitivity [$PRESET_DEFAULT]")
    case "${REPLY:-$PRESET_DEFAULT}" in
        1) THRESHOLD=40; MIN_AREA=5000; LABEL="Low" ;;
        2) THRESHOLD=30; MIN_AREA=2500; LABEL="Medium" ;;
        3) THRESHOLD=20; MIN_AREA=1000; LABEL="High" ;;
        4)
            REPLY=$(ask "  Threshold (0-255, lower=more sensitive) [$CUR_THRESHOLD]")
            THRESHOLD="${REPLY:-$CUR_THRESHOLD}"
            REPLY=$(ask "  Min contour area (pixels) [$CUR_MIN_AREA]")
            MIN_AREA="${REPLY:-$CUR_MIN_AREA}"
            LABEL="Custom"
            ;;
    esac

    ok "Motion sensitivity: $LABEL (threshold=$THRESHOLD, min_area=$MIN_AREA)"
    echo ""
}

# ── Step 5: Recording ───────────────────────────────────
configure_recording() {
    printf "${BOLD}Step 5/7${NC} — Recording settings\n\n"

    DEFAULT_DIR="$(cfg output_dir)"; DEFAULT_DIR="${DEFAULT_DIR:-$HOME/hermes-cctv/clips}"
    REPLY=$(ask "Clip output directory [$DEFAULT_DIR]" "where motion clips are saved — needs free disk space")
    OUTPUT_DIR="${REPLY:-$DEFAULT_DIR}"

    DEFAULT_PRE="$(cfg pre_motion_buffer)"; DEFAULT_PRE="${DEFAULT_PRE:-2}"
    REPLY=$(ask "Pre-motion buffer (seconds before motion) [$DEFAULT_PRE]" "suggested 1–5 — seconds of footage kept before motion starts")
    PRE_BUFFER="${REPLY:-$DEFAULT_PRE}"

    DEFAULT_POST="$(cfg post_motion_padding)"; DEFAULT_POST="${DEFAULT_POST:-3}"
    REPLY=$(ask "Post-motion padding (seconds after motion stops) [$DEFAULT_POST]" "suggested 2–10 — keeps recording this long after motion ends")
    POST_PAD="${REPLY:-$DEFAULT_POST}"

    DEFAULT_MAX="$(cfg max_clip_seconds)"; DEFAULT_MAX="${DEFAULT_MAX:-60}"
    REPLY=$(ask "Max clip duration (seconds) [$DEFAULT_MAX]" "suggested 30–300 — caps a single clip; 0 = unlimited")
    MAX_CLIP="${REPLY:-$DEFAULT_MAX}"

    ok "Recording → $OUTPUT_DIR (buffer=${PRE_BUFFER}s, pad=${POST_PAD}s, max=${MAX_CLIP}s)"
    echo ""
}

# ── Step 6: Hermes integration ──────────────────────────
configure_hermes() {
    printf "${BOLD}Step 6/7${NC} — Hermes Gateway integration\n\n"

    if [ "$HERMES_FOUND" != "true" ]; then
        warn "Hermes CLI not available — skipping gateway integration"
        warn "Run this step manually after installing Hermes:"
        warn "  cd $PROJECT_DIR && bash setup.sh --hermes-only"
        echo ""
        return
    fi

    # ── 6a: Install skill ──
    printf "  Installing CCTV skill...\n"
    mkdir -p "$SKILL_DIR"
    cp "$PROJECT_DIR/skills/hermes-cctv/SKILL.md" "$SKILL_DIR/SKILL.md"
    ok "Skill installed → $SKILL_DIR/SKILL.md"
    info "Commands available: /cctv on | off | status"

    # ── 6b: Install gateway plugin (registers /cctv slash commands) ──
    printf "  Installing gateway plugin...\n"
    PLUGIN_DIR="$HOME/.hermes/plugins/hermes-cctv"
    mkdir -p "$PLUGIN_DIR"
    cp "$PROJECT_DIR/plugins/hermes-cctv/__init__.py" "$PLUGIN_DIR/__init__.py"
    ok "Plugin installed → $PLUGIN_DIR/__init__.py"
    info "Gateway restart required: hermes gateway restart"

    # ── 6c: Install notification script ──
    printf "  Installing notification script...\n"
    mkdir -p "$SCRIPT_DIR"
    cp "$PROJECT_DIR/scripts/cctv-notify.py" "$SCRIPT_DIR/cctv-notify.py"
    chmod +x "$SCRIPT_DIR/cctv-notify.py"
    ok "Notification script → $SCRIPT_DIR/cctv-notify.py"

    # ── 6d: Create control directory ──
    mkdir -p "$CONTROL_DIR"
    echo "on" > "$CONTROL_DIR/control"
    ok "Control directory → $CONTROL_DIR/"

    # ── 6e: Cron job ──
    printf "  Creating notification cron job...\n"
    REPLY=$(ask "  Check interval in minutes [1]" "suggested 1–5 — how often Hermes checks for new motion clips to alert on")
    INTERVAL="${REPLY:-1}"

    if hermes cron create "every ${INTERVAL}m" \
        --name "CCTV Motion Alerts" \
        --script "cctv-notify.py" \
        --no_agent true \
        --deliver origin 2>/dev/null; then
        ok "Cron job: checks every ${INTERVAL}m, delivers to gateway"
    else
        # Try without deliver flag if it fails
        if hermes cron create "every ${INTERVAL}m" \
            --name "CCTV Motion Alerts" \
            --script "cctv-notify.py" \
            --no_agent true 2>/dev/null; then
            ok "Cron job: checks every ${INTERVAL}m (delivery: auto-detect)"
        else
            warn "Could not create cron job automatically"
            warn "Create manually:"
            warn "  hermes cron create \"every ${INTERVAL}m\" --name \"CCTV Motion Alerts\" --script cctv-notify.py --no_agent true --deliver origin"
        fi
    fi

    echo ""
}

# service_installed returns 0 if the background service is already registered.
service_installed() {
    case "$(uname -s)" in
        Darwin) [ -f "$HOME/Library/LaunchAgents/com.hermes.cctv.plist" ] ;;
        Linux)  [ -f "$HOME/.config/systemd/user/hermes-cctv.service" ] ;;
        MINGW*|MSYS*|CYGWIN*)
            local d="${APPDATA:-$USERPROFILE/AppData/Roaming}/Microsoft/Windows/Start Menu/Programs/Startup"
            [ -f "$d/hermes-cctv.vbs" ] ;;
        *) return 1 ;;
    esac
}

# ── Step 7: Auto-start ──────────────────────────────────
configure_autostart() {
    printf "${BOLD}Step 7/7${NC} — Auto-start on boot\n\n"

    case "$(uname -s)" in
        Darwin)   printf "  Platform: macOS → LaunchAgent\n" ;;
        Linux)    printf "  Platform: Linux → systemd user service\n" ;;
        MINGW*|MSYS*|CYGWIN*)
                  printf "  Platform: Windows → Startup folder launcher\n" ;;
    esac

    if service_installed; then
        info "Background service is already registered."
        if confirm "Re-register it with the current settings? [Y/n]"; then
            bash "$PROJECT_DIR/hermes-cctv" install
        else
            ok "Keeping existing registration (config still updated)."
        fi
    else
        printf "  The daemon will start on login and restart if it crashes.\n"
        if confirm "Install auto-start? [Y/n]"; then
            bash "$PROJECT_DIR/hermes-cctv" install
        else
            info "Skipped. Start manually: cd $PROJECT_DIR && source venv/bin/activate && python3 -m hermes_cctv.cctv"
        fi
    fi

    echo ""
}

# ── Write config ────────────────────────────────────────
write_config() {
    cat > "$CONFIG_FILE" <<YAML
camera:
  device_id: ${DEVICE_ID:-0}
  width: ${WIDTH:-640}
  height: ${HEIGHT:-480}
  fps: ${FPS:-15}

motion:
  enabled: true
  threshold: ${THRESHOLD:-30}
  min_area: ${MIN_AREA:-2500}
  blur_kernel: 21
  dilate_iterations: 2
  confirm_frames: 3

recording:
  output_dir: ${OUTPUT_DIR:-~/hermes-cctv/clips}
  snapshot_dir: ${SNAPSHOT_DIR:-~/hermes-cctv/snapshots}
  pre_motion_buffer: ${PRE_BUFFER:-2}
  post_motion_padding: ${POST_PAD:-3}
  codec: mp4v
  max_clip_seconds: ${MAX_CLIP:-300}
  max_storage_mb: ${MAX_STORAGE:-500}

hermes:
  control_file: ~/.hermes/cctv/control
  events_file: ~/.hermes/cctv/events.jsonl
YAML
    ok "Config written → $CONFIG_FILE"
}

# ── Summary ──────────────────────────────────────────────
print_summary() {
    echo ""
    printf "${GREEN}${BOLD}╔══════════════════════════════════════════╗${NC}\n"
    printf "${GREEN}${BOLD}║         Setup Complete!                 ║${NC}\n"
    printf "${GREEN}${BOLD}╚══════════════════════════════════════════╝${NC}\n"
    echo ""
    printf "  ${BOLD}Start the daemon:${NC}\n"
    printf "    cd $PROJECT_DIR\n"
    printf "    source venv/bin/activate\n"
    printf "    python3 -m hermes_cctv.cctv\n"
    echo ""
    printf "  ${BOLD}Gateway commands${NC} (from Telegram/Discord):\n"
    printf "    /cctv status  — check if monitoring\n"
    printf "    /cctv off     — pause motion detection\n"
    printf "    /cctv on      — resume monitoring\n"
    echo ""
    printf "  ${BOLD}Config:${NC}  $CONFIG_FILE\n"
    printf "  ${BOLD}Clips:${NC}   ${OUTPUT_DIR:-~/hermes-cctv/clips}\n"
    printf "  ${BOLD}Logs:${NC}    ~/Library/Logs/hermes-cctv*.log (macOS)\n"
    echo ""
}

# ── Hermes-only mode ────────────────────────────────────
hermes_only() {
    printf "${CYAN}${BOLD}Hermes Integration Setup${NC}\n\n"
    HERMES_FOUND=true
    configure_hermes
    print_summary
    exit 0
}

# ── Main ────────────────────────────────────────────────
main() {
    if [ "${1:-}" = "--hermes-only" ]; then
        hermes_only
    fi

    banner
    show_current_config
    check_prereqs
    setup_venv
    configure_camera
    configure_motion
    configure_recording
    configure_hermes
    write_config
    configure_autostart
    print_summary
}

main "$@"
