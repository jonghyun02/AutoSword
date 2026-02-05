"""
강화 매크로 공통 모듈

Logger, 창 제어, 파싱, 명령 전송 등 공통 기능 제공
"""
import pyautogui
import pyperclip
import pygetwindow as gw
import time
import re
import sys
import os
import atexit
from datetime import datetime


# ============================================================
# 로그 설정
# ============================================================

def get_log_dir():
    """로그 파일 저장 디렉토리 반환 (없으면 생성)"""
    base_dir = os.path.dirname(__file__)
    log_dir = os.path.join(base_dir, "logs")
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    return log_dir


class Logger:
    """print 출력을 콘솔과 파일에 동시에 기록 (100줄마다 파일 저장)"""
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.filename = filename
        self.buffer = []
        self.line_count = 0
        self.FLUSH_INTERVAL = 100
        
    def write(self, message):
        self.terminal.write(message)
        self.buffer.append(message)
        
        # 줄바꿈 카운트
        self.line_count += message.count('\n')
        
        # 100줄마다 파일에 저장
        if self.line_count >= self.FLUSH_INTERVAL:
            self._flush_to_file()
        
    def _flush_to_file(self):
        if self.buffer:
            with open(self.filename, 'a', encoding='utf-8') as f:
                f.write(''.join(self.buffer))
            self.buffer = []
            self.line_count = 0
        
    def flush(self):
        self.terminal.flush()
        self._flush_to_file()


def setup_logger(log_prefix):
    """로거 설정 및 활성화
    
    Args:
        log_prefix: 로그 파일 접두사 (예: "enhance_data", "enhance_upgrade")
    
    Returns:
        str: 로그 파일 경로
    """
    log_dir = get_log_dir()
    log_file = os.path.join(log_dir, f"{log_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
    
    sys.stdout = Logger(log_file)
    
    # 프로그램 종료 시 남은 버퍼 저장
    def _save_remaining_log():
        if isinstance(sys.stdout, Logger):
            sys.stdout.flush()
    atexit.register(_save_remaining_log)
    
    print(f"📝 로그 파일: {log_file}")
    return log_file


# ============================================================
# 강화 결과 분석 함수
# ============================================================

def check_enhancement_result(text):
    """강화 결과 분석
    
    Returns:
        tuple: (result_type, level)
            - ("success", new_level): 성공
            - ("maintain", None): 유지
            - ("destroy", 0): 파괴
            - (None, None): 알 수 없음
    """
    # 1. 성공 패턴 (예: +1 → +2)
    success_match = re.search(r"〖✨강화 성공✨ \+(\d+) → \+(\d+)〗", text)
    if success_match:
        return "success", int(success_match.group(2))

    # 1-2. 전설 강화 성공 패턴 10강 이상부터 적용됨
    legend_success_match = re.search(r"전설의 『\[\+(\d+)\] .+』 강화에 성공", text)
    if legend_success_match:
        return "success", int(legend_success_match.group(1))

    # 2. 유지 패턴
    maintain_match = re.search(r"〖💦강화 유지💦〗", text)
    if maintain_match:
        return "maintain", None

    # 3. 파괴 패턴
    destroy_match = re.search(r"〖💥강화 파괴💥〗", text)
    if destroy_match:
        return "destroy", 0

    return None, None


def parse_gold_from_enhance(text):
    """강화 결과에서 골드 파싱 (남은 골드: 77,994G 형식)"""
    match = re.search(r"남은 골드: ([\d,]+)G", text)
    if match:
        gold_str = match.group(1).replace(',', '')
        return int(gold_str)
    return None


def parse_gold_from_sell(text):
    """판매 결과에서 골드 파싱 (현재 보유 골드: 78,004G 형식)"""
    match = re.search(r"현재 보유 골드: ([\d,]+)G", text)
    if match:
        gold_str = match.group(1).replace(',', '')
        return int(gold_str)
    return None


def get_current_item_level(text):
    """텍스트에서 현재 아이템 강화 레벨 추출
    
    예: "『[+2] 그림자 갈망하는 몽둥이』" → 2
        "획득: [+0] 낡은 검" → 0
    """
    pattern = r"\[\+(\d+)\]"
    matches = re.findall(pattern, text)
    
    if matches:
        level = int(matches[-1])
        return level
    return None


# ============================================================
# 판매 대상 판단 함수
# ============================================================

# 판매 대상 키워드 (공통)
SELL_KEYWORDS = ['검', '몽둥이', '망치', '도끼']


def should_sell_item(text):
    """텍스트 끝부분 키워드로 판매 대상 여부 판단
    
    Returns:
        bool: True면 판매 대상 (일반 아이템)
              False면 판매 비대상 (특별 아이템)
    """
    pattern = r"⚔️새로운 검 획득: \[\+\d+\] .+"
    match = re.search(pattern, text)
    if match:
        text = match.group(0)
    else:
        return True

    text = text.strip()
    
    # 광선검은 판매하지 않음
    if text.endswith('광선검'):
        return False
    
    for keyword in SELL_KEYWORDS:
        if text.endswith(keyword):
            return True
    
    return False


def should_sell_destroyed_item(text, print_log=True):
    """파괴 시 새 아이템 판매 여부 판단
    
    Returns:
        bool: True면 판매 대상 (일반 아이템)
              False면 판매 비대상 (특별 아이템)
    """
    pattern = r"『\[\+\d+\] ([^』]+)』"
    matches = re.findall(pattern, text)
    
    if len(matches) >= 2:
        item_name = matches[1].strip()
    elif len(matches) == 1:
        item_name = matches[0].strip()
    else:
        return True
    
    # 광선검은 판매하지 않음
    if item_name.endswith('광선검'):
        if print_log:
            print(f"    🌟 광선검 획득!: {item_name}")
        return False
    
    for keyword in SELL_KEYWORDS:
        if item_name.endswith(keyword):
            if print_log:
                print(f"    🗡️ 일반 아이템: {item_name}")
            return True
    
    if print_log:
        print(f"    ✨ 특별 아이템: {item_name}")
    return False


def get_item_type_from_current_text(text):
    """현재 텍스트에서 아이템 타입 판단
    
    Returns:
        bool: True면 판매 대상 (일반 아이템)
              False면 판매 비대상 (특별 아이템)
    """
    pattern = r"『\[\+\d+\] ([^』]+)』"
    matches = re.findall(pattern, text)
    
    if matches:
        item_name = matches[-1].strip()
        
        if item_name.endswith('광선검'):
            return False
        
        for keyword in SELL_KEYWORDS:
            if item_name.endswith(keyword):
                return True
        
        return False
    
    return True


# ============================================================
# 창 제어 및 메시지 처리
# ============================================================

# 창 찾기 실패 카운터
_window_not_found_count = 0
MAX_WINDOW_NOT_FOUND = 180


def reset_window_counter():
    """창 찾기 실패 카운터 리셋"""
    global _window_not_found_count
    _window_not_found_count = 0


def get_latest_message(target_window_title):
    """창에서 가장 최근 메시지를 가져오는 함수"""
    global _window_not_found_count
    try:
        windows = gw.getWindowsWithTitle(target_window_title)
        
        if not windows:
            _window_not_found_count += 1
            print(f"오류: '{target_window_title}' 창을 찾을 수 없습니다. ({_window_not_found_count}/{MAX_WINDOW_NOT_FOUND})")
            time.sleep(1)
            if _window_not_found_count >= MAX_WINDOW_NOT_FOUND:
                print(f"\n❌ 창을 {MAX_WINDOW_NOT_FOUND}번 찾을 수 없어 프로그램을 종료합니다.")
                sys.exit(1)
            return None
        
        _window_not_found_count = 0

        target_window = windows[0]
        
        if target_window.isMinimized:
            target_window.restore()
        target_window.activate()
        
        time.sleep(0.1)

        # 창 중앙 클릭
        center_x = target_window.left + (target_window.width // 10)
        center_y = target_window.top + (target_window.height // 2)
        pyautogui.click(center_x, center_y)
        
        # 전체 선택 및 복사
        pyautogui.hotkey('ctrl', 'a')
        pyautogui.hotkey('ctrl', 'c')
        
        text_data = pyperclip.paste()
        
        keyword = "@사용자"
        last_index = text_data.rfind(keyword)
        
        if last_index != -1:
            return text_data[last_index:]
        else:
            return text_data

    except Exception as e:
        print(f"텍스트 추출 중 오류: {e}")
        return None


def wait_for_bot_response(target_window_title, max_retries=180):
    """봇 응답을 기다리는 함수
    
    Returns:
        str: 봇 응답이 포함된 메시지
    """
    result_text = None
    for i in range(max_retries): 
        result_text = get_latest_message(target_window_title)
        
        if result_text is None:
            time.sleep(0.5)
            continue
        
        text_stripped = result_text.strip()
        
        if text_stripped.endswith('/판매') or text_stripped.endswith('/강화'):
            print(f"    ⏳ 봇 응답 대기 중... ({i + 1}/{max_retries})")
            time.sleep(0.5)
            continue
        
        return result_text
    
    print("    ⚠️ 봇 응답 대기 시간 초과. 아마 서버가 터졌을수도")
    return result_text


# ============================================================
# 명령어 전송
# ============================================================

def send_sell_command(target_window_title):
    """판매 명령어를 입력하는 함수"""
    try:
        windows = gw.getWindowsWithTitle(target_window_title)
        
        if not windows:
            print(f"오류: '{target_window_title}' 창을 찾을 수 없습니다.")
            return False

        target_window = windows[0]
        
        if target_window.isMinimized:
            target_window.restore()
        target_window.activate()
        
        time.sleep(0.1)
        center_x = target_window.left + (target_window.width // 10)
        center_y = target_window.bottom - 100
        pyautogui.click(center_x, center_y)

        pyperclip.copy('/판매')
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.1)
        
        pyautogui.press('space')
        time.sleep(0.1)
        
        pyautogui.press('enter')
        
        return True

    except Exception as e:
        print(f"명령어 입력 중 오류: {e}")
        return False


def send_enhance_command(target_window_title):
    """강화 명령어를 입력하는 함수"""
    try:
        windows = gw.getWindowsWithTitle(target_window_title)
        
        if not windows:
            print(f"오류: '{target_window_title}' 창을 찾을 수 없습니다.")
            time.sleep(1)
            return False

        target_window = windows[0]
        
        if target_window.isMinimized:
            target_window.restore()
        target_window.activate()
        
        time.sleep(0.1)
        center_x = target_window.left + (target_window.width // 10)
        center_y = target_window.bottom - 100
        pyautogui.click(center_x, center_y)

        pyperclip.copy('/강화')
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.1)
        
        pyautogui.press('space')
        time.sleep(0.1)
        
        pyautogui.press('enter')
        
        return True

    except Exception as e:
        print(f"명령어 입력 중 오류: {e}")
        return False


# ============================================================
# 골드 기반 목표 레벨 결정 (enhance_macro_data 전용)
# ============================================================

def get_target_level_by_gold(gold):
    """골드에 따른 목표 레벨 결정
    
    골드 <= 2만: 6강
    골드 >= 2만: 7강
    골드 >= 14만: 9강
    골드 >= 34만: 10강
    골드 >= 76만: 11강
    골드 >= 160만: 12강
    골드 >= 400만: 13강
    """
    if gold is None:
        return 7
    
    if gold >= 4000000:
        return 13
    elif gold >= 1600000:
        return 12
    elif gold >= 760000:
        return 11
    elif gold >= 340000:
        return 10
    elif gold >= 140000:
        return 9
    elif gold >= 20000:
        return 7
    else:
        return 6
