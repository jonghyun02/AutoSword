"""
강화 매크로 (데이터 수집용)

골드에 따라 목표 강화 레벨을 자동 조정하며 무한 반복
"""
import time
import sys
import enhance_db
from enhance_common import (
    setup_logger,
    check_enhancement_result,
    parse_gold_from_enhance,
    parse_gold_from_sell,
    should_sell_item,
    should_sell_destroyed_item,
    get_target_level_by_gold,
    get_latest_message,
    wait_for_bot_response,
    send_sell_command,
    send_enhance_command,
)

# 로거 설정
setup_logger("enhance_data")


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
            gold = parse_gold_from_enhance(enhance_result)
            if gold is not None:
                current_gold = gold
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
            gold = parse_gold_from_enhance(enhance_result)
            if gold is not None:
                current_gold = gold
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


def run_enhance_macro(target_window_title, target_level=9, delay=1.0):
    """
    강화 매크로 실행 (무한 루프)
    
    Args:
        target_window_title: 대상 프로그램 창 제목
        target_level: 초기 목표 강화 레벨 (골드에 따라 자동 조정됨)
        delay: 강화 후 결과 확인까지 대기 시간 (초)
    """
    current_level = 0
    current_gold = None
    total_cycles = 0
    attempt_count = 0
    success_count = 0
    maintain_count = 0
    destroy_count = 0
    sell_count = 0
    
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
            new_target = get_target_level_by_gold(current_gold)
            if new_target != target_level:
                print(f"  💰 골드 변동: {current_gold:,}G → 목표 레벨 변경: +{target_level}강 → +{new_target}강")
                target_level = new_target
        
        if result_type == "success":
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
                
                send_sell_command(target_window_title)
                time.sleep(delay)
                sell_result = wait_for_bot_response(target_window_title)
                
                gold = parse_gold_from_sell(sell_result)
                if gold is not None:
                    current_gold = gold
                    new_target = get_target_level_by_gold(current_gold)
                    if new_target != target_level:
                        print(f"  💰 판매 후 골드: {current_gold:,}G → 목표 레벨 변경: +{target_level}강 → +{new_target}강")
                        target_level = new_target
                
                _, current_gold = sell_until_good_item(target_window_title, delay, current_gold)
                target_level = get_target_level_by_gold(current_gold)
                current_level = 0
                print(f"  🔄 새 아이템으로 재시작! (목표: +{target_level}강)")
            
        elif result_type == "maintain":
            enhance_db.record_stay(current_level)
            maintain_count += 1
            print(f"  💦 강화 유지 (현재: +{current_level})")
            
        elif result_type == "destroy":
            enhance_db.record_break(current_level)
            destroy_count += 1
            print(f"  💥 강화 파괴! → +0")
            
            if should_sell_destroyed_item(result_text):
                _, current_gold = sell_until_good_item(target_window_title, delay, current_gold)
            
            target_level = get_target_level_by_gold(current_gold)
            current_level = 0
        
        elif "골드가 부족해" in result_text:
            print(f"  💸 골드 부족! 현재 아이템 판매 후 재시도...")
            
            send_sell_command(target_window_title)
            time.sleep(delay)
            sell_result = wait_for_bot_response(target_window_title)
            
            gold = parse_gold_from_sell(sell_result)
            if gold is not None:
                current_gold = gold
            
            _, current_gold = sell_until_good_item(target_window_title, delay, current_gold)
            target_level = get_target_level_by_gold(current_gold)
            current_level = 0
            print(f"  🔄 새 아이템으로 재시작! (목표: +{target_level}강)")
        
        else:
            print(f"  ⚠️ 결과를 파악할 수 없습니다.")
            print(f"  [디버그] 받은 텍스트: {result_text[:200] if result_text else 'None'}...")
        
        time.sleep(0.5)


# --- 실행 ---
if __name__ == "__main__":
    WINDOW_TITLE = "메크로용"
    TARGET_LEVEL = 10
    RESULT_DELAY = 0.1
    
    run_enhance_macro(
        target_window_title=WINDOW_TITLE,
        target_level=TARGET_LEVEL,
        delay=RESULT_DELAY
    )
