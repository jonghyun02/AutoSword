import sqlite3
import os
import atexit

DB_PATH = os.path.join(os.path.dirname(__file__), 'enhance_data.db')

# 버퍼 설정
FLUSH_INTERVAL = 100  # 100번마다 DB에 기록
_buffer = {}  # {level: {'success': 0, 'stay': 0, 'break': 0}}
_buffer_count = 0  # 총 버퍼된 횟수


def get_connection():
    """DB 연결 반환"""
    return sqlite3.connect(DB_PATH)


def init_db():
    """DB 초기화 - 테이블이 없으면 생성하고 초기값 삽입
    
    이미 데이터가 있으면 아무것도 하지 않음 (한 번만 실행)
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # 테이블 생성
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS enhance_stats (
            Level INTEGER PRIMARY KEY,
            Try INTEGER DEFAULT 0,
            Success INTEGER DEFAULT 0,
            Stay INTEGER DEFAULT 0,
            Break INTEGER DEFAULT 0,
            SuccessPer REAL DEFAULT 0,
            StayPer REAL DEFAULT 0,
            BreakPer REAL DEFAULT 0
        )
    ''')
    
    # 데이터가 이미 있는지 확인
    cursor.execute('SELECT COUNT(*) FROM enhance_stats')
    count = cursor.fetchone()[0]
    
    if count == 0:
        # 초기 데이터 삽입 (이미지에서 가져온 값)
        initial_data = [
            # (Level, Try, Success, Stay, Break)
            (0, 4604, 4604, 0, 0),
            (1, 5065, 4549, 516, 0),
            (2, 5658, 4544, 1114, 0),
            (3, 6305, 4426, 1766, 113),
            (4, 6806, 4058, 2385, 363),
            (5, 6721, 3345, 2666, 710),
            (6, 6035, 2748, 2696, 591),
            (7, 5454, 2186, 2718, 550),
            (8, 4707, 1687, 2539, 481),
            (9, 4285, 1267, 2611, 407),
            (10, 3494, 896, 2236, 362),
            (11, 2893, 637, 1998, 258),
            (12, 2076, 448, 1442, 186),
            (13, 1485, 290, 1051, 144),
            (14, 1142, 181, 853, 108),
            (15, 723, 102, 547, 74),
            (16, 470, 48, 367, 55),
            (17, 266, 22, 218, 26),
            (18, 125, 6, 103, 16),
            (19, 46, 1, 40, 5),
        ]
        
        for level, try_count, success, stay, break_count in initial_data:
            # 퍼센트 계산 (소수점 2자리)
            success_per = round((success / try_count * 100), 2) if try_count > 0 else 0
            stay_per = round((stay / try_count * 100), 2) if try_count > 0 else 0
            break_per = round((break_count / try_count * 100), 2) if try_count > 0 else 0
            
            cursor.execute('''
                INSERT INTO enhance_stats (Level, Try, Success, Stay, Break, SuccessPer, StayPer, BreakPer)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (level, try_count, success, stay, break_count, success_per, stay_per, break_per))
        
        print("✅ DB 초기화 완료 - 초기 데이터 삽입됨")
    else:
        print("ℹ️ DB에 이미 데이터가 있음 - 초기화 건너뜀")
    
    conn.commit()
    conn.close()


def _get_buffer(level):
    """버퍼에서 해당 레벨 가져오기 (없으면 생성)"""
    if level not in _buffer:
        _buffer[level] = {'success': 0, 'stay': 0, 'break': 0}
    return _buffer[level]


def flush_buffer():
    """버퍼의 모든 데이터를 DB에 기록"""
    global _buffer, _buffer_count
    
    if not _buffer:
        return
    
    conn = get_connection()
    cursor = conn.cursor()
    
    for level, counts in _buffer.items():
        success_add = counts['success']
        stay_add = counts['stay']
        break_add = counts['break']
        try_add = success_add + stay_add + break_add
        
        if try_add == 0:
            continue
        
        # 해당 레벨이 없으면 생성
        cursor.execute('SELECT Level FROM enhance_stats WHERE Level = ?', (level,))
        if cursor.fetchone() is None:
            cursor.execute('INSERT INTO enhance_stats (Level) VALUES (?)', (level,))
        
        # 값 업데이트
        cursor.execute('''
            UPDATE enhance_stats 
            SET Try = Try + ?, Success = Success + ?, Stay = Stay + ?, Break = Break + ?
            WHERE Level = ?
        ''', (try_add, success_add, stay_add, break_add, level))
        
        # 퍼센트 재계산
        cursor.execute('SELECT Try, Success, Stay, Break FROM enhance_stats WHERE Level = ?', (level,))
        row = cursor.fetchone()
        if row:
            try_count, success, stay, break_count = row
            success_per = round((success / try_count * 100), 2) if try_count > 0 else 0
            stay_per = round((stay / try_count * 100), 2) if try_count > 0 else 0
            break_per = round((break_count / try_count * 100), 2) if try_count > 0 else 0
            
            cursor.execute('''
                UPDATE enhance_stats 
                SET SuccessPer = ?, StayPer = ?, BreakPer = ?
                WHERE Level = ?
            ''', (success_per, stay_per, break_per, level))
    
    conn.commit()
    conn.close()
    
    print(f"💾 DB 업데이트 완료 ({_buffer_count}회 강화 기록)")
    
    # 버퍼 초기화
    _buffer = {}
    _buffer_count = 0


def _check_flush():
    """버퍼가 FLUSH_INTERVAL에 도달하면 DB에 기록"""
    global _buffer_count
    if _buffer_count >= FLUSH_INTERVAL:
        flush_buffer()


def record_success(level):
    """성공 기록 - 버퍼에 추가 (100번마다 DB 업데이트)
    
    Args:
        level: 강화 전 레벨 (0강에서 1강으로 성공하면 level=0)
    """
    global _buffer_count
    buf = _get_buffer(level)
    buf['success'] += 1
    _buffer_count += 1
    _check_flush()


def record_stay(level):
    """유지 기록 - 버퍼에 추가 (100번마다 DB 업데이트)
    
    Args:
        level: 현재 레벨 (유지된 레벨)
    """
    global _buffer_count
    buf = _get_buffer(level)
    buf['stay'] += 1
    _buffer_count += 1
    _check_flush()


def record_break(level):
    """파괴 기록 - 버퍼에 추가 (100번마다 DB 업데이트)
    
    Args:
        level: 파괴 전 레벨
    """
    global _buffer_count
    buf = _get_buffer(level)
    buf['break'] += 1
    _buffer_count += 1
    _check_flush()


def get_stats(level):
    """해당 레벨의 통계 조회
    
    Returns:
        dict: {Try, Success, Stay, Break, SuccessPer, StayPer, BreakPer} 또는 None
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT Try, Success, Stay, Break, SuccessPer, StayPer, BreakPer 
        FROM enhance_stats WHERE Level = ?
    ''', (level,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            'Try': row[0],
            'Success': row[1],
            'Stay': row[2],
            'Break': row[3],
            'SuccessPer': row[4],
            'StayPer': row[5],
            'BreakPer': row[6]
        }
    return None


def get_all_stats():
    """모든 레벨의 통계 조회
    
    Returns:
        list of dict
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT Level, Try, Success, Stay, Break, SuccessPer, StayPer, BreakPer 
        FROM enhance_stats ORDER BY Level
    ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for row in rows:
        result.append({
            'Level': row[0],
            'Try': row[1],
            'Success': row[2],
            'Stay': row[3],
            'Break': row[4],
            'SuccessPer': row[5],
            'StayPer': row[6],
            'BreakPer': row[7]
        })
    return result


def print_all_stats():
    """모든 통계 출력 (디버깅용)"""
    stats = get_all_stats()
    print("\n========== 강화 통계 ==========")
    print(f"{'Level':>5} {'Try':>7} {'Success':>8} {'Stay':>6} {'Break':>6} {'SuccPer':>8} {'StayPer':>8} {'BrkPer':>8}")
    print("-" * 65)
    for s in stats:
        print(f"{s['Level']:>5} {s['Try']:>7} {s['Success']:>8} {s['Stay']:>6} {s['Break']:>6} {s['SuccessPer']:>7.1f}% {s['StayPer']:>7.1f}% {s['BreakPer']:>7.1f}%")
    print("=" * 65)


def get_buffer_count():
    """현재 버퍼에 쌓인 횟수 반환"""
    return _buffer_count


# 프로그램 종료 시 버퍼 자동 저장
atexit.register(flush_buffer)

# 모듈 로드 시 자동 초기화
init_db()


if __name__ == "__main__":
    # 테스트
    print_all_stats()
