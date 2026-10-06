#!/usr/bin/env python3
"""
smb-player - Gamepad-friendly SMB Media Player with Bulletproof Virtual Keyboard
"""

import curses
import json
import locale
import os
import subprocess
import sys
import time
import unicodedata

try:
    locale.setlocale(locale.LC_ALL, "")
except Exception:
    pass


def char_width(c):
    return 2 if unicodedata.east_asian_width(c) in ('F', 'W') else 1


def str_display_width(s):
    return sum(char_width(c) for c in s)


def clip_str(s, max_width):
    curr = 0
    res = []
    for c in s:
        w = char_width(c)
        if curr + w > max_width:
            break
        res.append(c)
        curr += w
    return "".join(res)

VIDEO_EXTENSIONS = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv",
    ".ts", ".m4v", ".webm", ".iso", ".mpg", ".mpeg"
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
STATE_PATH = os.path.join(BASE_DIR, "state.json")
INPUT_CONF_PATH = os.path.join(BASE_DIR, "input.conf")
MOUNT_SCRIPT = os.path.join(BASE_DIR, "smb_mount.sh")
WATCH_LATER_DIR = os.path.join(BASE_DIR, "watch_later")


def get_battery_info():
    """Returns a battery string like '🔋 91%' or '⚡ 91%' or None."""
    try:
        if os.path.exists("/sys/class/power_supply"):
            for d in os.listdir("/sys/class/power_supply"):
                if d.startswith("bat"):
                    cap_file = os.path.join("/sys/class/power_supply", d, "capacity")
                    stat_file = os.path.join("/sys/class/power_supply", d, "status")
                    if os.path.exists(cap_file):
                        with open(cap_file, "r") as f:
                            cap = f.read().strip()
                        is_charging = False
                        if os.path.exists(stat_file):
                            with open(stat_file, "r") as f:
                                is_charging = "charging" in f.read().strip().lower()
                        icon = "⚡" if is_charging else "🔋"
                        return f"{icon} {cap}%"
    except Exception:
        pass
    return None


def safe_curs_set(visibility):
    """Safely set cursor visibility without raising error if unsupported."""
    try:
        curses.curs_set(visibility)
    except Exception:
        pass


def safe_addstr(win, y, x, text, attr=0):
    """Safely write to a curses window without crashing on borders/edges."""
    try:
        h, w = win.getmaxyx()
        if y < 0 or y >= h or x < 0 or x >= w:
            return
        max_len = w - x - 1
        if max_len <= 0:
            return
        clipped = clip_str(str(text), max_len)
        win.addstr(y, x, clipped, attr)
    except curses.error:
        pass


def load_config():
    default_config = {
        "smb_host": "192.168.0.1",
        "smb_port": 445,
        "smb_share": "share",
        "smb_user": "",
        "smb_pass": "",
        "mount_point": "/storage/smb_player_mount"
    }
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                default_config.update(data)
        except Exception:
            pass
    return default_config


def save_config(config):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def load_state():
    default_state = {
        "last_dir": "",
        "recent": [],
        "favorites": [],
        "sort_mode": "name"  # "name" or "mtime"
    }
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                default_state.update(data)
        except Exception:
            pass
    return default_state


def save_state(state):
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


def is_mounted(mount_point):
    try:
        res = subprocess.run(["mountpoint", "-q", mount_point], capture_output=True)
        return res.returncode == 0
    except Exception:
        return os.path.exists(mount_point) and os.listdir(mount_point) != []


def run_mount():
    try:
        res = subprocess.run([MOUNT_SCRIPT, "mount"], capture_output=True, text=True)
        return res.returncode == 0, res.stdout + res.stderr
    except Exception as e:
        return False, str(e)


def run_unmount():
    try:
        subprocess.run([MOUNT_SCRIPT, "unmount"], capture_output=True)
    except Exception:
        pass


def play_video(file_path, video_list=None, start_index=0, state=None):
    os.makedirs(WATCH_LATER_DIR, exist_ok=True)
    
    cmd = [
        "mpv",
        "--vo=wlshm",
        "--fs",
        "--no-terminal",
        "--really-quiet",
        "--force-window=immediate",
        "--sub-auto=fuzzy",
        # Subtitle styling optimized for 5.5-6 inch 1080p handhelds
        "--sub-font=Noto Sans CJK SC,sans-serif",
        "--sub-font-size=48",
        "--sub-border-size=3.2",
        "--sub-color=#FFFFFFFF",
        "--sub-border-color=#FF000000",
        "--sub-shadow-offset=1.5",
        "--sub-shadow-color=#80000000",
        "--sub-pos=95",
        # Audio Volume Boost (up to 200%)
        "--volume-max=200",
        f"--input-conf={INPUT_CONF_PATH}",
        "--save-position-on-quit",
        f"--watch-later-directory={WATCH_LATER_DIR}"
    ]

    playlist_file = None
    if video_list and len(video_list) > 1:
        playlist_file = "/tmp/chore_playlist.m3u"
        try:
            with open(playlist_file, "w", encoding="utf-8") as f:
                for v in video_list:
                    f.write(v + "\n")
            cmd.extend([
                f"--playlist={playlist_file}",
                f"--playlist-start={start_index}"
            ])
        except Exception:
            cmd.append(file_path)
    else:
        cmd.append(file_path)

    # Save to recent history and last directory in state
    if state is not None:
        recent = state.setdefault("recent", [])
        state["recent"] = [r for r in recent if r.get("path") != file_path]
        state["recent"].insert(0, {
            "path": file_path,
            "name": os.path.basename(file_path),
            "time": int(time.time())
        })
        state["recent"] = state["recent"][:10]
        state["last_dir"] = os.path.dirname(file_path)
        save_state(state)
    
    curses.def_prog_mode()
    curses.endwin()
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    finally:
        # Re-enforce Sway fullscreen on foot window after video closes
        try:
            import glob
            socks = glob.glob("/var/run/0-runtime-dir/sway-ipc.*.sock")
            if socks:
                env = os.environ.copy()
                env["SWAYSOCK"] = socks[0]
                # Reset tiling focus and re-maximize smb-player
                subprocess.run(["swaymsg", "focus parent"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(["swaymsg", "fullscreen disable"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(["swaymsg", '[app_id="smb-player"] focus'], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(["swaymsg", '[app_id="smb-player"] fullscreen enable'], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

        curses.reset_prog_mode()
        curses.doupdate()
        if playlist_file and os.path.exists(playlist_file):
            try:
                os.remove(playlist_file)
            except Exception:
                pass


class VirtualKeyboard:
    """Gamepad-navigable On-Screen Keyboard (OSK)"""
    
    LAYOUT_LOWER = [
        ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-", "_"],
        ["q", "w", "e", "r", "t", "y", "u", "i", "o", "p", "/", "@"],
        ["a", "s", "d", "f", "g", "h", "j", "k", "l", ".", ":", "!"],
        ["z", "x", "c", "v", "b", "n", "m", "?", "#", "$", "%", "&"],
        ["[CAPS]", "[SYM]", "[SPACE]", "[DEL]", "[취소]", "[완료]"]
    ]

    LAYOUT_UPPER = [
        ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "-", "_"],
        ["Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P", "/", "@"],
        ["A", "S", "D", "F", "G", "H", "J", "K", "L", ".", ":", "!"],
        ["Z", "X", "C", "V", "B", "N", "M", "?", "#", "$", "%", "&"],
        ["[caps]", "[SYM]", "[SPACE]", "[DEL]", "[취소]", "[완료]"]
    ]

    LAYOUT_SYM = [
        ["~", "`", "!", "@", "#", "$", "%", "^", "&", "*", "(", ")"],
        ["+", "=", "{", "}", "[", "]", "\\", "|", ";", "'", "\"", "<"],
        [">", "/", "?", ",", ".", "-", "_", ":", "%", "$", "*", "#"],
        ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "@", "."],
        ["[ABC]", "[123]", "[SPACE]", "[DEL]", "[취소]", "[완료]"]
    ]

    def __init__(self, stdscr, title="입력", initial_text="", is_password=False):
        self.stdscr = stdscr
        self.title = title
        self.buf = list(str(initial_text))
        self.is_password = is_password
        self.show_password = not is_password
        self.mode = "lower"
        self.row = 1
        self.col = 0

    def get_layout(self):
        if self.mode == "upper":
            return self.LAYOUT_UPPER
        elif self.mode == "sym":
            return self.LAYOUT_SYM
        return self.LAYOUT_LOWER

    def run(self):
        safe_curs_set(0)
        h, w = self.stdscr.getmaxyx()
        win_w = min(66, w - 4)
        win_h = 16
        win_y = max(1, (h - win_h) // 2)
        win_x = max(1, (w - win_w) // 2)
        
        kb_win = curses.newwin(win_h, win_w, win_y, win_x)
        kb_win.keypad(True)

        while True:
            kb_win.erase()
            try:
                kb_win.box()
            except curses.error:
                pass
            
            # Title
            title_str = f" [가상 키보드] {self.title} "
            safe_addstr(kb_win, 0, 2, title_str, curses.color_pair(2) | curses.A_BOLD)

            # Input field
            if self.is_password and not self.show_password:
                display_val = "*" * len(self.buf)
            else:
                display_val = "".join(self.buf)
            
            safe_addstr(kb_win, 2, 3, "내용: ", curses.A_BOLD)
            val_box = f" {display_val}_ "
            val_box = val_box + " " * max(0, win_w - 14 - len(val_box))
            safe_addstr(kb_win, 2, 9, val_box, curses.color_pair(1) | curses.A_REVERSE)

            layout = self.get_layout()
            self.row = max(0, min(self.row, len(layout) - 1))
            self.col = max(0, min(self.col, len(layout[self.row]) - 1))

            # Render Keys
            start_y = 5
            for r_idx, row_keys in enumerate(layout):
                # Calculate spacing
                total_key_len = sum(len(k) + 2 for k in row_keys)
                cur_x = max(2, (win_w - total_key_len) // 2)
                
                for c_idx, key in enumerate(row_keys):
                    is_active = (r_idx == self.row and c_idx == self.col)
                    key_text = f" {key} "
                    
                    if is_active:
                        safe_addstr(kb_win, start_y + r_idx * 2, cur_x, key_text, curses.color_pair(3) | curses.A_BOLD)
                    else:
                        safe_addstr(kb_win, start_y + r_idx * 2, cur_x, key_text)
                    cur_x += len(key) + 2

            # Footer / Help
            help_str = "D-pad: 이동 | A: 입력 | B: 지움 | Start: 완료"
            safe_addstr(kb_win, win_h - 1, max(2, (win_w - len(help_str)) // 2), help_str, curses.A_DIM)
            
            kb_win.refresh()

            ch = kb_win.getch()
            layout = self.get_layout()

            if ch in [curses.KEY_UP, ord('k')]:
                if self.row > 0:
                    self.row -= 1
                    self.col = min(self.col, len(layout[self.row]) - 1)
            elif ch in [curses.KEY_DOWN, ord('j')]:
                if self.row < len(layout) - 1:
                    self.row += 1
                    self.col = min(self.col, len(layout[self.row]) - 1)
            elif ch in [curses.KEY_LEFT, ord('h')]:
                if self.col > 0:
                    self.col -= 1
                else:
                    self.col = len(layout[self.row]) - 1
            elif ch in [curses.KEY_RIGHT, ord('l')]:
                if self.col < len(layout[self.row]) - 1:
                    self.col += 1
                else:
                    self.col = 0
            elif ch in [curses.KEY_ENTER, 10, 13, 32]:  # Confirm Key
                sel_key = layout[self.row][self.col]
                
                if sel_key == "[DEL]":
                    if self.buf:
                        self.buf.pop()
                elif sel_key == "[CLEAR]":
                    self.buf.clear()
                elif sel_key == "[SPACE]":
                    self.buf.append(" ")
                elif sel_key in ["[CAPS]", "[caps]"]:
                    self.mode = "upper" if self.mode == "lower" else "lower"
                elif sel_key in ["[SYM]", "[123]"]:
                    self.mode = "sym"
                elif sel_key == "[ABC]":
                    self.mode = "lower"
                elif sel_key == "[취소]":
                    return None
                elif sel_key == "[완료]":
                    return "".join(self.buf)
                else:
                    self.buf.append(sel_key)
            elif ch in [curses.KEY_BACKSPACE, 127, 8, ord('x'), ord('X')]:  # Backspace
                if self.buf:
                    self.buf.pop()
            elif ch in [27]:  # ESC / Back button
                if self.buf:
                    self.buf.pop()
                else:
                    return None
            elif ch in [ord('\t')]:  # Tab toggle caps
                self.mode = "upper" if self.mode == "lower" else "lower"
            elif 32 <= ch <= 126:  # Direct typing fallback
                self.buf.append(chr(ch))


class SMBPlayerUI:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.config = load_config()
        self.state = load_state()
        self.mount_point = self.config.get("mount_point", "/storage/smb_player_mount")
        
        last_d = self.state.get("last_dir", "")
        if last_d and os.path.isdir(last_d) and last_d.startswith(self.mount_point):
            self.current_dir = last_d
        else:
            self.current_dir = self.mount_point

        self.selected_idx = 0
        self.scroll_offset = 0
        self.items = []
        self.status_msg = ""
        self.status_time = 0
        self.unmounted_idx = 0
        
        safe_curs_set(0)
        self.stdscr.timeout(100)
        self.init_colors()
        
    def init_colors(self):
        try:
            curses.start_color()
        except Exception:
            pass

        has_default_colors = False
        try:
            curses.use_default_colors()
            has_default_colors = True
        except Exception:
            pass

        bg = -1 if has_default_colors else curses.COLOR_BLACK

        pairs = [
            (1, curses.COLOR_WHITE, bg),
            (2, curses.COLOR_BLACK, curses.COLOR_CYAN),
            (3, curses.COLOR_BLACK, curses.COLOR_YELLOW),
            (4, curses.COLOR_CYAN, bg),
            (5, curses.COLOR_GREEN, bg),
            (6, curses.COLOR_WHITE, curses.COLOR_BLUE),
            (7, curses.COLOR_RED, bg),
        ]
        for pair_id, fg, b_color in pairs:
            try:
                curses.init_pair(pair_id, fg, b_color)
            except Exception:
                pass

    def set_status(self, msg, duration=3):
        self.status_msg = msg
        self.status_time = time.time() + duration

    def scan_directory(self):
        if not is_mounted(self.mount_point):
            self.items = []
            return
            
        try:
            entries = os.listdir(self.current_dir)
        except Exception as e:
            self.set_status(f"폴더 읽기 오류: {e}")
            self.items = []
            return

        is_root = (os.path.abspath(self.current_dir) == os.path.abspath(self.mount_point))
        items = []

        # 1. If not root, add '..' (Upper folder)
        if not is_root:
            items.append({
                "type": "up",
                "name": ".. (상위 폴더)",
                "path": os.path.dirname(self.current_dir),
                "is_dir": True
            })
        else:
            # At root: show recent video if available
            recent = self.state.get("recent", [])
            for r in recent:
                r_path = r.get("path", "")
                if os.path.exists(r_path):
                    items.append({
                        "type": "recent",
                        "name": f"이어보기: {r.get('name', '최근 영상')}",
                        "path": r_path,
                        "is_dir": False
                    })
                    break

            # At root: show pinned favorites
            favs = self.state.get("favorites", [])
            for fav_path in favs:
                if os.path.exists(fav_path) and os.path.isdir(fav_path):
                    if os.path.abspath(fav_path) != os.path.abspath(self.mount_point):
                        rel = os.path.relpath(fav_path, self.mount_point)
                        items.append({
                            "type": "fav_root",
                            "name": f"즐겨찾기: /{rel}",
                            "path": fav_path,
                            "is_dir": True
                        })

        # Separate directory entries into subdirectories and video files
        subdirs = []
        video_files = []

        for entry in entries:
            if entry.startswith("."):
                continue
            full_path = os.path.join(self.current_dir, entry)
            try:
                if os.path.isdir(full_path):
                    subdirs.append(entry)
                else:
                    ext = os.path.splitext(entry)[1].lower()
                    if ext in VIDEO_EXTENSIONS:
                        video_files.append(entry)
            except Exception:
                continue

        # Sort subdirectories alphabetically
        subdirs.sort(key=lambda s: s.lower())

        # Sort video files: name or mtime
        sort_mode = self.state.get("sort_mode", "name")
        if sort_mode == "mtime":
            def get_mtime_safe(fname):
                try:
                    return os.path.getmtime(os.path.join(self.current_dir, fname))
                except Exception:
                    return 0
            video_files.sort(key=get_mtime_safe, reverse=True)
        else:
            video_files.sort(key=lambda s: s.lower())

        favs = self.state.get("favorites", [])
        for d in subdirs:
            full = os.path.join(self.current_dir, d)
            is_fav = full in favs
            items.append({
                "type": "fav_dir" if is_fav else "dir",
                "name": f"{d}/",
                "path": full,
                "is_dir": True
            })

        for f in video_files:
            full = os.path.join(self.current_dir, f)
            items.append({
                "type": "file",
                "name": f,
                "path": full,
                "is_dir": False
            })

        self.items = items
        if self.selected_idx >= len(self.items):
            self.selected_idx = max(0, len(self.items) - 1)

    def draw_browser(self):
        self.stdscr.erase()
        h, w = self.stdscr.getmaxyx()
        
        # 1. Header (Line 0)
        title = " SMB MEDIA PLAYER "
        sort_mode = self.state.get("sort_mode", "name")
        sort_badge = "[정렬: 최신순]" if sort_mode == "mtime" else "[정렬: 이름순]"
        
        bat = get_battery_info()
        clock_str = time.strftime("%H:%M")
        right_info = f"{bat} | {clock_str} " if bat else f"{clock_str} "
        
        # Fill whole line with cyan bar, then print left and right parts
        safe_addstr(self.stdscr, 0, 0, " " * (w - 1), curses.color_pair(2))
        safe_addstr(self.stdscr, 0, 0, f"{title}{sort_badge}", curses.color_pair(2) | curses.A_BOLD)
        right_x = max(0, w - str_display_width(right_info) - 4)
        safe_addstr(self.stdscr, 0, right_x, right_info, curses.color_pair(2) | curses.A_BOLD)

        # 2. Path Display & Host info (Line 1)
        rel_path = os.path.relpath(self.current_dir, self.mount_point)
        path_display = f" 경로: /{'' if rel_path == '.' else rel_path}"
        host_info = f"{self.config.get('smb_host')}/{self.config.get('smb_share')} "
        safe_addstr(self.stdscr, 1, 0, path_display, curses.color_pair(1) | curses.A_DIM)
        safe_addstr(self.stdscr, 1, max(0, w - str_display_width(host_info) - 2), host_info, curses.color_pair(1) | curses.A_DIM)
        safe_addstr(self.stdscr, 2, 0, "-" * (w - 1), curses.color_pair(1) | curses.A_DIM)

        # 3. Item List (Lines 3 to h - 3)
        list_top = 3
        list_bottom = h - 3
        max_rows = max(1, list_bottom - list_top)

        if not is_mounted(self.mount_point):
            host_str = self.config.get("smb_host", "SMB")
            share_str = self.config.get("smb_share", "share")
            warn_title = f"[!] SMB 공유 폴더 ({host_str}/{share_str}) 미연결"
            warn_desc = "아이디와 비밀번호 인증이 필요합니다."
            safe_addstr(self.stdscr, list_top + 1, max(2, (w - str_display_width(warn_title)) // 2), warn_title, curses.color_pair(7) | curses.A_BOLD)
            safe_addstr(self.stdscr, list_top + 2, max(2, (w - str_display_width(warn_desc)) // 2), warn_desc, curses.A_DIM)

            menu_items = [
                "[1] NAS 접속 계정/비밀번호 설정 (가상 키보드 입력)",
                "[2] 연결 다시 시도 (재마운트)",
                "[3] 플레이어 종료 (Tools 메뉴로 복귀)"
            ]
            menu_y = list_top + 5
            for idx, item in enumerate(menu_items):
                y = menu_y + idx * 2
                is_sel = (idx == self.unmounted_idx)
                if is_sel:
                    safe_addstr(self.stdscr, y, max(4, (w - len(item) - 4) // 2), f" > {item} < ", curses.color_pair(3) | curses.A_BOLD)
                else:
                    safe_addstr(self.stdscr, y, max(4, (w - len(item) - 4) // 2), f"   {item}   ")

            tip = "* config.json 파일을 직접 수정해도 됩니다 *"
            safe_addstr(self.stdscr, h - 4, max(2, (w - len(tip)) // 2), tip, curses.color_pair(4) | curses.A_DIM)
        elif not self.items:
            empty_msg = "(이 폴더에 재생 가능한 동영상 파일이 없습니다)"
            safe_addstr(self.stdscr, list_top + 3, max(2, (w - len(empty_msg)) // 2), empty_msg, curses.A_DIM)
        else:
            if self.selected_idx < self.scroll_offset:
                self.scroll_offset = self.selected_idx
            elif self.selected_idx >= self.scroll_offset + max_rows:
                self.scroll_offset = self.selected_idx - max_rows + 1

            for i in range(max_rows):
                item_idx = self.scroll_offset + i
                if item_idx >= len(self.items):
                    break
                
                item = self.items[item_idx]
                row_y = list_top + i
                itype = item.get("type", "file")
                name = item.get("name", "")

                if itype == "up":
                    tag = "[..]   "
                    color = curses.color_pair(4)
                elif itype == "recent":
                    tag = "[▶]    "
                    color = curses.color_pair(3) | curses.A_BOLD
                elif itype == "fav_root":
                    tag = "[★]    "
                    color = curses.color_pair(2) | curses.A_BOLD
                elif itype == "fav_dir":
                    tag = "[★DIR] "
                    color = curses.color_pair(2)
                elif itype == "dir":
                    tag = "[DIR]  "
                    color = curses.color_pair(4)
                else:  # file
                    tag = "[MOV]  "
                    color = curses.color_pair(5)

                prefix = " > " if item_idx == self.selected_idx else "   "
                tag_name = f"{tag}{name}"
                max_content_w = w - 4
                tag_name_clipped = clip_str(tag_name, max_content_w)
                pad_spaces = " " * max(0, max_content_w - str_display_width(tag_name_clipped))
                line_str = f"{prefix}{tag_name_clipped}{pad_spaces}"

                if item_idx == self.selected_idx:
                    safe_addstr(self.stdscr, row_y, 0, line_str, curses.color_pair(3) | curses.A_BOLD)
                else:
                    safe_addstr(self.stdscr, row_y, 0, line_str, color)

        # 4. Footer & Controls
        footer_y = h - 2
        status_y = h - 1
        
        if self.status_msg and time.time() < self.status_time:
            safe_addstr(self.stdscr, footer_y, 1, f"ℹ {self.status_msg}", curses.color_pair(7) | curses.A_BOLD)
        else:
            item_count_str = f"항목: {len(self.items)}개"
            safe_addstr(self.stdscr, footer_y, w - str_display_width(item_count_str) - 2, item_count_str, curses.A_DIM)

        safe_addstr(self.stdscr, status_y, 0, " " * (w - 1), curses.color_pair(6))
        help_text = " [D-pad/L1/R1] 이동  [A] 재생/선택  [B] 뒤로  [Y] 정렬  [Select/F] ★즐겨찾기  [X] 설정  [Start] 종료 "
        safe_addstr(self.stdscr, status_y, 0, help_text, curses.color_pair(6))

        self.stdscr.refresh()

    def edit_settings(self):
        safe_curs_set(0)
        h, w = self.stdscr.getmaxyx()
        fields = [
            ("SMB IP/호스트", "smb_host", False),
            ("공유 폴더명", "smb_share", False),
            ("아이디 (User)", "smb_user", False),
            ("비밀번호 (Pass)", "smb_pass", True),
        ]
        
        field_idx = 0
        while True:
            self.stdscr.erase()
            title = " [SMB 접속 설정] (D-pad로 선택 후 A를 눌러 가상 키보드로 입력) "
            safe_addstr(self.stdscr, 1, 2, title, curses.color_pair(2) | curses.A_BOLD)

            for idx, (label, key, is_pw) in enumerate(fields):
                val = str(self.config.get(key, ""))
                if is_pw and val:
                    val = "*" * len(val)
                elif not val:
                    val = "(미설정)"
                row_str = f"{label:16}: {val}"
                y = 4 + idx * 2
                if idx == field_idx:
                    safe_addstr(self.stdscr, y, 4, f" > {row_str} ", curses.color_pair(3) | curses.A_BOLD)
                else:
                    safe_addstr(self.stdscr, y, 6, row_str)

            btn_idx = len(fields)
            btn_save = "[ 연결 테스트 및 마운트 실행 ]"
            btn_exit = "[ 저장 후 나가기 ]"
            
            y_btns = 4 + len(fields) * 2 + 1
            if field_idx == btn_idx:
                safe_addstr(self.stdscr, y_btns, 6, f"> {btn_save} <", curses.color_pair(3) | curses.A_BOLD)
            else:
                safe_addstr(self.stdscr, y_btns, 8, btn_save)

            if field_idx == btn_idx + 1:
                safe_addstr(self.stdscr, y_btns + 2, 6, f"> {btn_exit} <", curses.color_pair(3) | curses.A_BOLD)
            else:
                safe_addstr(self.stdscr, y_btns + 2, 8, btn_exit)

            safe_addstr(self.stdscr, h - 2, 2, "D-pad: 이동 | A: 가상 키보드로 수정 / 실행 | B: 이전", curses.A_DIM)
            self.stdscr.refresh()

            ch = self.stdscr.getch()
            if ch in [curses.KEY_UP, ord('k')]:
                field_idx = (field_idx - 1) % (len(fields) + 2)
            elif ch in [curses.KEY_DOWN, ord('j')]:
                field_idx = (field_idx + 1) % (len(fields) + 2)
            elif ch in [27, ord('q'), ord('Q')]:  # ESC or Start (Back to browser)
                break
            elif ch in [curses.KEY_ENTER, 10, 13, 32]:  # Enter / Space
                if field_idx < len(fields):
                    label, key, is_pw = fields[field_idx]
                    kb = VirtualKeyboard(
                        self.stdscr,
                        title=label,
                        initial_text=self.config.get(key, ""),
                        is_password=is_pw
                    )
                    new_val = kb.run()
                    if new_val is not None:
                        self.config[key] = new_val
                        save_config(self.config)
                elif field_idx == btn_idx:  # Test mount
                    save_config(self.config)
                    # Non-blocking progress display
                    host_str = self.config.get("smb_host", "SMB")
                    self.show_loading_box("마운트 시도 중...", f"서버({host_str}) 연결을 시도하고 있습니다...")
                    ok, msg = run_mount()
                    if ok:
                        self.set_status("마운트 성공! 공유 폴더에 연결되었습니다.")
                        break
                    else:
                        self.show_message("마운트 실패", f"오류 메시지:\n{msg[:200]}")
                elif field_idx == btn_idx + 1:  # Exit
                    save_config(self.config)
                    break

    def show_loading_box(self, title, text):
        h, w = self.stdscr.getmaxyx()
        win_w = min(60, w - 4)
        lines = text.split("\n")
        win_h = min(10, len(lines) + 4)
        
        msg_win = curses.newwin(win_h, win_w, (h - win_h) // 2, (w - win_w) // 2)
        try:
            msg_win.box()
        except curses.error:
            pass
        safe_addstr(msg_win, 1, 2, title, curses.color_pair(2) | curses.A_BOLD)
        for i, line in enumerate(lines[:win_h - 3]):
            safe_addstr(msg_win, 2 + i, 2, line)
        msg_win.refresh()

    def show_message(self, title, text):
        h, w = self.stdscr.getmaxyx()
        win_w = min(70, w - 4)
        lines = text.split("\n")
        win_h = min(15, len(lines) + 6)
        
        msg_win = curses.newwin(win_h, win_w, (h - win_h) // 2, (w - win_w) // 2)
        try:
            msg_win.box()
        except curses.error:
            pass
        safe_addstr(msg_win, 1, 2, title, curses.color_pair(2) | curses.A_BOLD)
        
        for i, line in enumerate(lines[:win_h - 4]):
            safe_addstr(msg_win, 3 + i, 2, line)
            
        safe_addstr(msg_win, win_h - 2, 2, "[ A 또는 B 버튼을 눌러 닫기 ]", curses.A_DIM)
        msg_win.refresh()
        
        msg_win.timeout(-1)
        msg_win.getch()
        msg_win.timeout(100)

    def confirm_exit(self):
        h, w = self.stdscr.getmaxyx()
        win_w = min(50, w - 4)
        win_h = 7
        exit_win = curses.newwin(win_h, win_w, (h - win_h) // 2, (w - win_w) // 2)
        try:
            exit_win.box()
        except curses.error:
            pass
        safe_addstr(exit_win, 1, 2, " [플레이어 종료] ", curses.color_pair(2) | curses.A_BOLD)
        safe_addstr(exit_win, 3, max(2, (win_w - 24) // 2), "종료하고 나가시겠습니까?")
        safe_addstr(exit_win, 5, max(2, (win_w - 28) // 2), "[A: 예 / 종료]   [B: 취소]", curses.A_BOLD)
        exit_win.refresh()

        exit_win.timeout(-1)
        while True:
            k = exit_win.getch()
            if k in [curses.KEY_ENTER, 10, 13, 32, ord('y'), ord('Y'), ord('q'), ord('Q')]:
                return True
            elif k in [27, ord('n'), ord('N')]:
                return False

    def handle_input(self):
        ch = self.stdscr.getch()
        if ch == -1:
            return True

        if not is_mounted(self.mount_point):
            if ch in [curses.KEY_UP, ord('k')]:
                self.unmounted_idx = (self.unmounted_idx - 1) % 3
            elif ch in [curses.KEY_DOWN, ord('j')]:
                self.unmounted_idx = (self.unmounted_idx + 1) % 3
            elif ch in [curses.KEY_ENTER, 10, 13, 32]:
                if self.unmounted_idx == 0:
                    self.edit_settings()
                    self.scan_directory()
                elif self.unmounted_idx == 1:
                    host_str = self.config.get("smb_host", "SMB")
                    self.show_loading_box("연결 시도 중...", f"서버({host_str}) 연결을 시도하고 있습니다...")
                    ok, msg = run_mount()
                    if ok:
                        self.set_status("마운트 성공! 공유 폴더에 연결되었습니다.")
                        self.scan_directory()
                    else:
                        self.show_message("연결 실패", f"오류:\n{msg[:200]}")
                elif self.unmounted_idx == 2:
                    if self.confirm_exit():
                        return False
            elif ch in [27]:  # ESC
                if self.confirm_exit():
                    return False
            elif ch in [ord('x'), ord('X'), ord('y'), ord('Y'), ord('\t')]:
                self.edit_settings()
                self.scan_directory()
            elif ch in [ord('q'), ord('Q')]:
                if self.confirm_exit():
                    return False
            return True

        if ch in [curses.KEY_UP, ord('k')]:
            if self.selected_idx > 0:
                self.selected_idx -= 1
        elif ch in [curses.KEY_DOWN, ord('j')]:
            if self.selected_idx < len(self.items) - 1:
                self.selected_idx += 1
        elif ch in [curses.KEY_PPAGE]:
            self.selected_idx = max(0, self.selected_idx - 10)
        elif ch in [curses.KEY_NPAGE]:
            self.selected_idx = min(len(self.items) - 1, self.selected_idx + 10)
        elif ch in [curses.KEY_ENTER, 10, 13, 32]:
            if self.items:
                item = self.items[self.selected_idx]
                if item["is_dir"]:
                    self.current_dir = item["path"]
                    self.selected_idx = 0
                    self.scroll_offset = 0
                    self.state["last_dir"] = self.current_dir
                    save_state(self.state)
                    self.scan_directory()
                else:
                    # Video play: build playlist of files in the current dir for continuous play
                    video_list = [it["path"] for it in self.items if it.get("type") == "file"]
                    if item["path"] in video_list:
                        s_idx = video_list.index(item["path"])
                    else:
                        video_list = [item["path"]]
                        s_idx = 0
                    play_video(item["path"], video_list=video_list, start_index=s_idx, state=self.state)
                    self.stdscr.clear()
                    self.scan_directory()
        elif ch in [27]:  # ESC / B button
            if os.path.abspath(self.current_dir) != os.path.abspath(self.mount_point):
                self.current_dir = os.path.dirname(self.current_dir)
                self.selected_idx = 0
                self.scroll_offset = 0
                self.state["last_dir"] = self.current_dir
                save_state(self.state)
                self.scan_directory()
            else:
                if self.confirm_exit():
                    return False
        elif ch in [ord('y'), ord('Y')]:  # Y button: Toggle sort (Name <-> Date)
            cur_sort = self.state.get("sort_mode", "name")
            new_sort = "mtime" if cur_sort == "name" else "name"
            self.state["sort_mode"] = new_sort
            save_state(self.state)
            self.set_status(f"정렬 방식 변경: {'최신 등록순' if new_sort == 'mtime' else '이름순'}")
            self.scan_directory()
        elif ch in [ord('f'), ord('F')]:  # Select button or 'f': Toggle favorite
            if self.items:
                item = self.items[self.selected_idx]
                target_path = None
                itype = item.get("type", "")
                if item.get("is_dir") and itype not in ["up", "fav_root"]:
                    target_path = item["path"]
                elif itype == "fav_root":
                    target_path = item["path"]
                elif itype == "up" or not item.get("is_dir"):
                    if os.path.abspath(self.current_dir) != os.path.abspath(self.mount_point):
                        target_path = self.current_dir

                if target_path:
                    favs = self.state.setdefault("favorites", [])
                    if target_path in favs:
                        favs.remove(target_path)
                        self.set_status(f"즐겨찾기 해제: {os.path.basename(target_path)}")
                    else:
                        favs.append(target_path)
                        self.set_status(f"★ 즐겨찾기 추가: {os.path.basename(target_path)}")
                    save_state(self.state)
                    self.scan_directory()
                else:
                    self.set_status("루트 폴더는 즐겨찾기에 등록할 수 없습니다.")
        elif ch in [ord('x'), ord('X'), ord('\t')]:  # X button: Settings
            self.edit_settings()
            self.scan_directory()
        elif ch in [ord('r'), ord('R')]:
            self.scan_directory()
            self.set_status("목록을 새로고침했습니다.")
        elif ch in [ord('q'), ord('Q')]:
            if self.confirm_exit():
                return False

        return True

    def run(self):
        if not is_mounted(self.mount_point):
            ok, msg = run_mount()
            if ok:
                self.set_status("SMB 공유 폴더가 성공적으로 마운트되었습니다.")
                last_d = self.state.get("last_dir", "")
                if last_d and os.path.isdir(last_d) and last_d.startswith(self.mount_point):
                    self.current_dir = last_d

        self.scan_directory()

        running = True
        while running:
            self.draw_browser()
            running = self.handle_input()


def main():
    try:
        # Fallback if TERM is not proper
        if not os.environ.get("TERM"):
            os.environ["TERM"] = "linux"
        curses.wrapper(lambda stdscr: SMBPlayerUI(stdscr).run())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        # Log unexpected error to /tmp
        with open("/tmp/smb_player_crash.log", "w", encoding="utf-8") as f:
            import traceback
            traceback.print_exc(file=f)
        # Retry with xterm-256color if curses cbreak failed
        if "cbreak" in str(e):
            try:
                os.environ["TERM"] = "xterm-256color"
                curses.wrapper(lambda stdscr: SMBPlayerUI(stdscr).run())
            except Exception:
                pass
    finally:
        print("\nSMB Player를 종료합니다.")


if __name__ == "__main__":
    main()
