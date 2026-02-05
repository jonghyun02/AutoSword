"""
강화 업그레이드 매크로

- 판매 없이 무조건 강화
- should_sell_item=False (광선검 등): 13강에서 판매
- should_sell_item=True (검, 몽둥이, 망치, 도끼): 17강까지 강화
- 17강 성공 시 프로그램 종료
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
    get_item_type_from_current_text,
    get_latest_message,
    wait_for_bot_response,
    send_sell_command,
    send_enhance_command,
)

# 로거 설정
setup_logger("enhance_upgrade")


def run_enhance_upgrade_macro(target_window_title, delay=1.0):
    """
    강화 업그레이드 매크로 실행
    
    - 판매 없이 무조건 강화
    - should_sell_item=False (광선검 등): 13강에서 판매
    - should_sell_item=True (검, 몽둥이, 망치, 도끼): 17강까지 강화
    - 17강 성공 시 프로그램 종료
    
    Args:
        target_window_title: 대상 프로그램 창 제목
        delay: 강화 후 결과 확인까지 대기 시간 (초)
    """
    current_level = 0
    current_gold = None
    is_sell_item = True  # True: 17강 목표, False: 13강 목표
    attempt_count = 0
    success_count = 0
    maintain_count = 0
    destroy_count = 0
    
    print(f"========================================")
    print(f"🔥 강화 업그레이드 매크로 시작!")
    print(f"📋 규칙:")
    print(f"   - 일반 아이템 (검/몽둥이/망치/도끼): 17강까지 강화")
    print(f"   - 특별 아이템 (광선검 등): 13강에서 판매")
    print(f"   - 17강 성공 시 프로그램 종료")
    print(f"대상 창: {target_window_title}")
    print("1초 후 시작합니다...")
    print(f"========================================")
    time.sleep(1)

    # 초기 아이템 타입 확인
    initial_text = get_latest_message(target_window_title)
    if initial_text:
        is_sell_item = get_item_type_from_current_text(initial_text)
        target_level = 17 if is_sell_item else 13
        print(f"  📌 현재 아이템 타입: {'일반 (17강 목표)' if is_sell_item else '특별 (13강 목표)'}")
    else:
        target_level = 17
        print(f"  📌 아이템 타입 확인 불가, 기본 17강 목표")

    # 무한 루프
    while True:
        attempt_count += 1
        target_level = 17 if is_sell_item else 13
        print(f"\n[시도 #{attempt_count}] 현재 레벨: +{current_level} | 목표: +{target_level}강 | 타입: {'일반' if is_sell_item else '특별'}" + (f" | 골드: {current_gold:,}G" if current_gold else ""))
        
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
        
        if result_type == "success":
            enhance_db.record_success(current_level)
            current_level = new_level
            success_count += 1
            print(f"  ✨ 강화 성공! → +{current_level}")
            
            # 17강 달성 시 프로그램 종료
            if current_level >= 17:
                print(f"\n🎊🎊🎊🎊🎊🎊🎊🎊🎊🎊🎊🎊🎊🎊🎊")
                print(f"🏆 +17강 달성! 프로그램을 종료합니다!")
                print(f"🎊🎊🎊🎊🎊🎊🎊🎊🎊🎊🎊🎊🎊🎊🎊")
                print(f"\n📊 최종 통계:")
                print(f"   총 시도: {attempt_count}회")
                print(f"   성공: {success_count}회")
                print(f"   유지: {maintain_count}회")
                print(f"   파괴: {destroy_count}회")
                sys.exit(0)
            
            # 특별 아이템(should_sell_item=False)이 13강 도달 시 판매
            if not is_sell_item and current_level >= 13:
                print(f"\n  🎉 특별 아이템 +13강 달성! 판매 진행...")
                
                send_sell_command(target_window_title)
                time.sleep(delay)
                sell_result = wait_for_bot_response(target_window_title)
                
                gold = parse_gold_from_sell(sell_result)
                if gold is not None:
                    current_gold = gold
                
                is_sell_item = should_sell_item(sell_result)
                current_level = 0
                target_level = 17 if is_sell_item else 13
                print(f"  🔄 새 아이템으로 재시작! (타입: {'일반 → 17강 목표' if is_sell_item else '특별 → 13강 목표'})")
            
        elif result_type == "maintain":
            enhance_db.record_stay(current_level)
            maintain_count += 1
            print(f"  💦 강화 유지 (현재: +{current_level})")
            
        elif result_type == "destroy":
            enhance_db.record_break(current_level)
            destroy_count += 1
            print(f"  💥 강화 파괴! → +0")
            
            # 파괴 시 새 아이템 타입 확인 (로그 메시지 출력 포함)
            is_sell_item = should_sell_destroyed_item(result_text, print_log=True)
            current_level = 0
            target_level = 17 if is_sell_item else 13
            print(f"  🔄 새 아이템! (목표: +{target_level}강)")
        
        elif "골드가 부족해" in result_text:
            print(f"  💸 골드 부족! 현재 아이템 판매 후 재시도...")
            
            send_sell_command(target_window_title)
            time.sleep(delay)
            sell_result = wait_for_bot_response(target_window_title)
            
            gold = parse_gold_from_sell(sell_result)
            if gold is not None:
                current_gold = gold
            
            is_sell_item = should_sell_item(sell_result)
            current_level = 0
            target_level = 17 if is_sell_item else 13
            print(f"  🔄 새 아이템으로 재시작! (목표: +{target_level}강)")
        
        else:
            print(f"  ⚠️ 결과를 파악할 수 없습니다.")
            print(f"  [디버그] 받은 텍스트: {result_text[:200] if result_text else 'None'}...")
        
        time.sleep(0.5)


# --- 실행 ---
if __name__ == "__main__":
    WINDOW_TITLE = "메크로용"
    RESULT_DELAY = 0.1
    
    run_enhance_upgrade_macro(
        target_window_title=WINDOW_TITLE,
        delay=RESULT_DELAY
    )
