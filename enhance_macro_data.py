import pyautogui
import pyperclip
import pygetwindow as gw
import time
import re
import sys
import os
from datetime import datetime
import enhance_db

# 로그 파일 설정
LOG_DIR = os.path.dirname(__file__)
LOG_FILE = os.path.join(LOG_DIR, f"enhance_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")

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

import atexit
# 프로그램 종료 시 남은 버퍼 저장
def _save_remaining_log():
    if isinstance(sys.stdout, Logger):
        sys.stdout.flush()
atexit.register(_save_remaining_log)

# 로거 활성화
sys.stdout = Logger(LOG_FILE)
print(f"📝 로그 파일: {LOG_FILE}")

# 강화 결과 분석 함수
def check_enhancement_result(text):
    # 1. 성공 패턴 (예: +1 → +2)
    success_match = re.search(r"〖✨강화 성공✨ \+(\d+) → \+(\d+)〗", text)
    if success_match:
        return "success", int(success_match.group(2))  # 강화된 레벨 반환

    # 2. 유지 패턴
    maintain_match = re.search(r"〖💦강화 유지💦〗", text)
    if maintain_match:
        return "maintain", None

    # 3. 파괴 패턴
    destroy_match = re.search(r"〖💥강화 파괴💥〗", text)
    if destroy_match:
        return "destroy", 0  # 파괴되면 0강으로 리셋

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
        return 7  # 기본값
    
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


# 창 찾기 실패 카운터
_window_not_found_count = 0
MAX_WINDOW_NOT_FOUND = 180

def get_latest_message(target_window_title):
    """창에서 가장 최근 메시지를 가져오는 함수"""
    global _window_not_found_count
    try:
        windows = gw.getWindowsWithTitle(target_window_title)
        
        if not windows:
            _window_not_found_count += 1
            print(f"오류: '{target_window_title}' 창을 찾을 수 없습니다. ({_window_not_found_count}/{MAX_WINDOW_NOT_FOUND})")
            
            if _window_not_found_count >= MAX_WINDOW_NOT_FOUND:
                print(f"\n❌ 창을 {MAX_WINDOW_NOT_FOUND}번 찾을 수 없어 프로그램을 종료합니다.")
                sys.exit(1)
            return None
        
        # 창을 찾으면 카운터 리셋
        _window_not_found_count = 0

        target_window = windows[0]
        
        if target_window.isMinimized:
            target_window.restore()
        target_window.activate()
        
        time.sleep(0.1)

        # 창 중앙 클릭
        center_x = target_window.left + (target_window.width // 2)
        center_y = target_window.top + (target_window.height // 2)
        pyautogui.click(center_x, center_y)
        
        # 전체 선택 및 복사
        pyautogui.hotkey('ctrl', 'a')
        pyautogui.hotkey('ctrl', 'c')
        
        text_data = pyperclip.paste()
        
        # '@사용자' 이후의 가장 마지막 메시지 추출
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
    
    메시지 끝이 /판매 또는 /강화로 끝나면 1초 대기 후 재시도
    봇이 응답할 때까지 기다림
    
    Returns:
        str: 봇 응답이 포함된 메시지
    """
    for i in range(max_retries): 
        
        result_text = get_latest_message(target_window_title)
        
        if result_text is None:
            time.sleep(0.5)
            continue
        
        # 메시지 끝부분 확인 (공백 제거)
        text_stripped = result_text.strip()
        
        # /판매 또는 /강화로 끝나면 아직 봇이 응답 안 한 것
        if text_stripped.endswith('/판매') or text_stripped.endswith('/강화'):
            print(f"    ⏳ 봇 응답 대기 중... ({i + 1}/{max_retries})")
            time.sleep(0.5)
            continue
        
        # 봇이 응답함
        return result_text
    
    print("    ⚠️ 봇 응답 대기 시간 초과. 아마 서버가 터졌을수도")
    return result_text  # 마지막으로 받은 텍스트라도 반환

def get_current_item_level(text):
    """텍스트에서 현재 아이템 강화 레벨 추출
    
    예: "『[+2] 그림자 갈망하는 몽둥이』" → 2
        "획득: [+0] 낡은 검" → 0
    """
    # 패턴 정의: [+숫자] 형태를 모두 찾음
    pattern = r"\[\+(\d+)\]"
    
    # 모두 찾기 (리스트 형태로 반환됨)
    matches = re.findall(pattern, text)
    
    if matches:
        # 가장 마지막에 발견된 것이 현재 상태일 확률이 높음
        level = int(matches[-1])
        return level
    else:
        return None

def should_sell_item(text):
    """텍스트 끝부분에 '검' 또는 '몽둥이'가 있으면 판매 대상으로 판단
    
    예: "새로운 검 획득: [+0] 낡은 몽둥이" → True (몽둥이로 끝남)
        "새로운 검 획득: [+0] 낡은 검" → True (검으로 끝남)
    """
    pattern = r"⚔️새로운 검 획득: \[\+\d+\] .+"
    match = re.search(pattern, text)
    if match:
        text = match.group(0)
    else:
        return True

    # 공백 제거 후 끝부분 확인
    text = text.strip()
    
    # 광선검은 판매하지 않음
    if text.endswith('광선검'):
        return False
    
    # 판매 대상 키워드
    sell_keywords = ['검', '몽둥이','망치']
    
    for keyword in sell_keywords:
        if text.endswith(keyword):
            return True
    
    return False

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
        # 채팅창 클릭
        center_x = target_window.left + (target_window.width // 2)
        center_y = target_window.bottom - 100
        pyautogui.click(center_x, center_y)

        # '/강화' 붙여넣기
        pyperclip.copy('/판매')
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.1)
        
        # 스페이스바 직접 누르기
        pyautogui.press('space')
        time.sleep(0.1)
        
        # 엔터 입력으로 명령 실행
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
            return False

        target_window = windows[0]
        
        if target_window.isMinimized:
            target_window.restore()
        target_window.activate()
        
        time.sleep(0.1)
        # 채팅창 클릭
        center_x = target_window.left + (target_window.width // 2)
        center_y = target_window.bottom - 100
        pyautogui.click(center_x, center_y)

        # '/강화' 붙여넣기
        pyperclip.copy('/강화')
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.1)
        
        # 스페이스바 직접 누르기
        pyautogui.press('space')
        time.sleep(0.1)
        
        # 엔터 입력으로 명령 실행
        pyautogui.press('enter')
        
        return True

    except Exception as e:
        print(f"명령어 입력 중 오류: {e}")
        return False


def sell_until_good_item(target_window_title, delay, current_gold=None):
    
    """검 또는 몽둥이가 아닐 때까지 판매 반복
    
    0강검은 판매 불가 → 강화 1회 후 판매 진행
    
    Returns:
        tuple: (result_text, current_gold)
    """
    print("  🔄 좋은 아이템 나올 때까지 판매 중...")
    result_text = wait_for_bot_response(target_window_title)
    
    sell_count = 0
    while result_text and should_sell_item(result_text):
        # 0강검 판매 불가 메시지 감지
        if "0강검은 가치가 없어서 판매할 수 없다네" in result_text:
            print("    ⚠️ 0강검 판매 불가! 강화 1회 진행...")
            send_enhance_command(target_window_title)
            time.sleep(delay)
            enhance_result = wait_for_bot_response(target_window_title)
            # 강화 결과에서 골드 파싱
            gold = parse_gold_from_enhance(enhance_result)
            if gold is not None:
                current_gold = gold
            # 강화 후 다시 판매 시도
            send_sell_command(target_window_title)
            time.sleep(delay)
            result_text = wait_for_bot_response(target_window_title)
            continue
        
        # 〖검 판매〗 메시지 감지 시 강화 1회 후 판매
        if "〖검 판매〗" in result_text:
            print("    🔨 검 판매 감지! 강화 1회 진행...")
            send_enhance_command(target_window_title)
            time.sleep(delay)
            enhance_result = wait_for_bot_response(target_window_title)
            # 강화 결과에서 골드 파싱
            gold = parse_gold_from_enhance(enhance_result)
            if gold is not None:
                current_gold = gold
            # 강화 후 다시 판매 시도
            send_sell_command(target_window_title)
            time.sleep(delay)
            result_text = wait_for_bot_response(target_window_title)
            continue
        
        # 판매 결과에서 골드 파싱
        gold = parse_gold_from_sell(result_text)
        if gold is not None:
            current_gold = gold
        
        sell_count += 1
        print(f"    판매 #{sell_count}")
        send_sell_command(target_window_title)
        time.sleep(delay)
        result_text = wait_for_bot_response(target_window_title)
    
    # 마지막 결과에서도 골드 파싱 시도
    gold = parse_gold_from_sell(result_text)
    if gold is not None:
        current_gold = gold
    
    print(f"  ✅ 좋은 아이템 획득! (판매 {sell_count}회)")
    return result_text, current_gold

def should_sell_destroyed_item(text):
    """파괴 시 새 아이템 판매 여부 판단
    
    파괴 메시지에서 두 번째 『[+0] 아이템명』 형식의 아이템 이름 추출 후
    검, 몽둥이, 망치로 끝나면 판매, 광선검으로 끝나면 판매 안 함
    
    예: 『[+0] 내일 시들 것 같은 할인 꽃다발』 → False (꽃다발로 끝남)
        『[+0] 낡은 검』 → True (검으로 끝남)
        『[+0] 광선검』 → False (광선검으로 끝남)
    """
    # 『[+숫자] 아이템명』 패턴을 모두 찾음
    pattern = r"『\[\+\d+\] ([^』]+)』"
    matches = re.findall(pattern, text)
    
    if len(matches) >= 2:
        # 두 번째 아이템이 파괴 후 새로 획득한 아이템
        item_name = matches[1].strip()
    elif len(matches) == 1:
        item_name = matches[0].strip()
    else:
        # 패턴을 찾지 못하면 기본적으로 판매 진행
        return True
    
    # 광선검은 판매하지 않음
    if item_name.endswith('광선검'):
        print(f"    🌟 광선검 획득! 판매하지 않음: {item_name}")
        return False
    
    # 판매 대상 키워드
    sell_keywords = ['검', '몽둥이', '망치']
    
    for keyword in sell_keywords:
        if item_name.endswith(keyword):
            print(f"    🗡️ 판매 대상 아이템: {item_name}")
            return True
    
    # 그 외 아이템은 판매하지 않음
    print(f"    ✨ 좋은 아이템 획득! 판매하지 않음: {item_name}")
    return False

def run_enhance_macro(target_window_title, target_level=9, delay=1.0):
    """
    강화 매크로 실행 (무한 루프)
    
    Args:
        target_window_title: 대상 프로그램 창 제목
        target_level: 초기 목표 강화 레벨 (골드에 따라 자동 조정됨)
        delay: 강화 후 결과 확인까지 대기 시간 (초)
    """
    current_level = 0
    current_gold = None  # 현재 골드
    total_cycles = 0  # 목표 달성 횟수
    attempt_count = 0
    success_count = 0
    maintain_count = 0
    destroy_count = 0
    sell_count = 0  # 목표 달성 후 판매 횟수
    
    print(f"========================================")
    print(f"🔥 강화 매크로 시작! (무한 모드)")
    print(f"초기 목표: +{target_level}강 (골드에 따라 자동 조정)")
    print(f"대상 창: {target_window_title}")
    print("1초 후 시작합니다...")
    print(f"========================================")
    time.sleep(1)

    # 초기: 검 또는 몽둥이가 아닐때까지 판매
    _, current_gold = sell_until_good_item(target_window_title, delay, current_gold)
    
    # 골드에 따른 목표 레벨 설정
    target_level = get_target_level_by_gold(current_gold)
    print(f"  💰 현재 골드: {current_gold:,}G → 목표 레벨: +{target_level}강" if current_gold else f"  💰 골드 정보 없음 → 목표 레벨: +{target_level}강")

    # 무한 루프
    while True:
        attempt_count += 1
        print(f"\n[사이클 #{total_cycles + 1}] [시도 #{attempt_count}] 현재 레벨: +{current_level} | 목표: +{target_level}강 | 골드: {current_gold:,}G" if current_gold else f"\n[사이클 #{total_cycles + 1}] [시도 #{attempt_count}] 현재 레벨: +{current_level} | 목표: +{target_level}강")
        
        # 1. 강화 명령 입력
        if not send_enhance_command(target_window_title):
            print("명령어 입력 실패. 재시도...")
            continue
        
        # 2. 결과 대기
        print(f"  결과 대기 중... ({delay}초)")
        time.sleep(delay)
        
        # 3. 결과 텍스트 가져오기 (봇 응답 대기)
        result_text = wait_for_bot_response(target_window_title)
        
        if result_text is None:
            print("  결과를 읽을 수 없습니다. 재시도...")
            continue
        
        # 4. 결과 분석
        result_type, new_level = check_enhancement_result(result_text)
        
        # 강화 결과에서 골드 파싱
        gold = parse_gold_from_enhance(result_text)
        if gold is not None:
            current_gold = gold
            # 골드에 따른 목표 레벨 업데이트
            new_target = get_target_level_by_gold(current_gold)
            if new_target != target_level:
                print(f"  💰 골드 변동: {current_gold:,}G → 목표 레벨 변경: +{target_level}강 → +{new_target}강")
                target_level = new_target
        
        if result_type == "success":
            # DB에 성공 기록 (강화 전 레벨 기준)
            enhance_db.record_success(current_level)
            current_level = new_level
            success_count += 1
            print(f"  ✨ 강화 성공! → +{current_level}")
            
            # 목표 레벨 도달 시 판매 후 재시작
            if current_level >= target_level:
                total_cycles += 1
                sell_count += 1
                print(f"\n  🎉 목표 +{target_level}강 달성! 판매 진행...")
                print(f"  📊 누적 통계: 사이클 {total_cycles}회 완료")
                
                # 판매
                send_sell_command(target_window_title)
                time.sleep(delay)
                sell_result = wait_for_bot_response(target_window_title)
                
                # 판매 결과에서 골드 파싱
                gold = parse_gold_from_sell(sell_result)
                if gold is not None:
                    current_gold = gold
                    # 골드에 따른 목표 레벨 업데이트
                    new_target = get_target_level_by_gold(current_gold)
                    if new_target != target_level:
                        print(f"  💰 판매 후 골드: {current_gold:,}G → 목표 레벨 변경: +{target_level}강 → +{new_target}강")
                        target_level = new_target
                
                # 검/몽둥이 아닐 때까지 판매
                _, current_gold = sell_until_good_item(target_window_title, delay, current_gold)
                
                # 골드에 따른 목표 레벨 업데이트
                target_level = get_target_level_by_gold(current_gold)
                
                # 레벨 리셋
                current_level = 0
                print(f"  🔄 새 아이템으로 재시작! (목표: +{target_level}강)")
            
        elif result_type == "maintain":
            # DB에 유지 기록
            enhance_db.record_stay(current_level)
            maintain_count += 1
            print(f"  💦 강화 유지 (현재: +{current_level})")
            
        elif result_type == "destroy":
            # DB에 파괴 기록 (파괴 전 레벨 기준)
            enhance_db.record_break(current_level)
            destroy_count += 1
            print(f"  💥 강화 파괴! → +0")
            
            # 파괴 시 새 아이템 확인 후 조건부 판매
            if should_sell_destroyed_item(result_text):
                # 검/몽둥이/망치면 판매 후 좋은 아이템 나올 때까지 반복
                _, current_gold = sell_until_good_item(target_window_title, delay, current_gold)
            else:
                # 광선검 또는 좋은 아이템이면 판매하지 않음
                pass
            
            # 골드에 따른 목표 레벨 업데이트
            target_level = get_target_level_by_gold(current_gold)
            current_level = 0
        
        elif "골드가 부족해" in result_text:
            print(f"  💸 골드 부족! 현재 아이템 판매 후 재시도...")
            
            # 현재 아이템 판매
            send_sell_command(target_window_title)
            time.sleep(delay)
            sell_result = wait_for_bot_response(target_window_title)
            
            # 판매 결과에서 골드 파싱
            gold = parse_gold_from_sell(sell_result)
            if gold is not None:
                current_gold = gold
            
            # 검/몽둥이 아닐 때까지 판매
            _, current_gold = sell_until_good_item(target_window_title, delay, current_gold)
            
            # 골드에 따른 목표 레벨 업데이트  
            target_level = get_target_level_by_gold(current_gold)
            current_level = 0
            print(f"  🔄 새 아이템으로 재시작! (목표: +{target_level}강)")
        
        else:
            print(f"  ⚠️ 결과를 파악할 수 없습니다.")
            print(f"  [디버그] 받은 텍스트: {result_text[:200] if result_text else 'None'}...")
        
        # 다음 시도 전 짧은 대기
        time.sleep(0.5)


# --- 실행 ---
if __name__ == "__main__":
    # 설정
    WINDOW_TITLE = "메크로용"  # 실제 프로그램 창 제목
    TARGET_LEVEL = 10         # 목표 강화 레벨
    RESULT_DELAY = 0.1        # 강화 후 결과 대기 시간 (초)
    
    run_enhance_macro(
        target_window_title=WINDOW_TITLE,
        target_level=TARGET_LEVEL,
        delay=RESULT_DELAY
    )

