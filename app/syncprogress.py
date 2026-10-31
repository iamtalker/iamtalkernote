"""동기화 진행 상황 표시용 계산: 받는 속도와 남은 시간(최근 90초 동안 남은 용량이 줄어든 만큼), 글자 만들기. 폰 앱 Eta.kt 와 같은 규칙."""
import time

WINDOW = 90
MIN_SPAN = 15


class Eta:
    def __init__(self):
        self.samples = []

    def update(self, need_bytes, now=None):
        """지금 남은 용량 → 초당 바이트(아직 모르면 0). 남은 용량이 늘면(새 단계가 열림) 다시 센다"""
        now = time.time() if now is None else now
        if self.samples and need_bytes > self.samples[-1][1]:
            self.samples = []
        self.samples.append((now, need_bytes))
        while len(self.samples) > 2 and now - self.samples[0][0] > WINDOW:
            self.samples.pop(0)
        t0, b0 = self.samples[0]
        if now - t0 < MIN_SPAN or b0 <= need_bytes:
            return 0.0
        return (b0 - need_bytes) / (now - t0)


def size(b):
    if b >= 1 << 30:
        return "%.1fGB" % (b / (1 << 30))
    if b >= 1 << 20:
        return "%.0fMB" % (b / (1 << 20))
    return "%.0fKB" % (b / 1024)


def remaining(need_bytes, rate):
    """남은 시간 글자. 속도를 모르면 빈 글(보여 주지 않는다)"""
    if need_bytes <= 0 or rate <= 0:
        return ""
    sec = int(need_bytes / rate)
    if sec < 60:
        return "1분 미만"
    if sec < 3600:
        return "약 %d분" % (sec // 60)
    if sec < 86400:
        return "약 %d시간 %d분" % (sec // 3600, sec % 3600 // 60)
    return "약 %d일 %d시간" % (sec // 86400, sec % 86400 // 3600)


def line(total_files, need_files, total_bytes, need_bytes, rate):
    """'파일 전체 N개 · 받음 M개 · 남음 K개 · P% · 용량 a / b · 속도 · 남은 시간'"""
    got = max(total_files - need_files, 0)
    pct = int((total_bytes - need_bytes) * 100 / total_bytes) if total_bytes > 0 else 100
    s = "파일 전체 %d개 · 받음 %d개 · 남음 %d개 · %d%% · 용량 %s / %s" % (total_files, got, need_files, pct, size(max(total_bytes - need_bytes, 0)), size(total_bytes))
    if need_bytes > 0 and rate > 0:
        s += " · 속도 %s/초 · 남은 시간 %s" % (size(int(rate)), remaining(need_bytes, rate))
    return s
