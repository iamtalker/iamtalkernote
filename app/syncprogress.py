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


def line(total_files, need_files, total_bytes, need_bytes, rate, all_files=0):
    """'파일 전체 N개 · 받음 M개 · 남음 K개 · P% · 용량 a / b · 속도 · 남은 시간'.
    all_files(숨긴 단계까지 합친 전체 파일 수)를 주면 전체·남음·퍼센트를 그 기준으로 센다(받음은 지금 열린 범위에서 센 값)"""
    got = max(total_files - need_files, 0)
    if all_files > 0:
        all_files = max(all_files, got)
        s = "파일 전체 %s개 · 받음 %s개 · 남음 %s개 · %d%% · 이번 단계 용량 %s / %s" % (
            format(all_files, ","), format(got, ","), format(all_files - got, ","), got * 100 // all_files,
            size(max(total_bytes - need_bytes, 0)), size(total_bytes))
        if need_bytes > 0 and rate > 0:
            s += " · 속도 %s/초 · 이번 단계 남은 시간 %s" % (size(int(rate)), remaining(need_bytes, rate))
        return s
    pct = int((total_bytes - need_bytes) * 100 / total_bytes) if total_bytes > 0 else 100
    s = "파일 전체 %d개 · 받음 %d개 · 남음 %d개 · %d%% · 용량 %s / %s" % (total_files, got, need_files, pct, size(max(total_bytes - need_bytes, 0)), size(total_bytes))
    if need_bytes > 0 and rate > 0:
        s += " · 속도 %s/초 · 남은 시간 %s" % (size(int(rate)), remaining(need_bytes, rate))
    return s


FRESH = 600   # 폰이 센 값은 이 초 안의 것만 믿는다


def read_phone(directory, now=None):
    """폰이 설정 폴더에 적어 둔 실제 진행(progress.json) → dict 또는 None(없거나 오래됨·깨짐)"""
    import json
    import os
    now = time.time() if now is None else now
    try:
        with open(os.path.join(directory, "progress.json"), encoding="utf-8") as fh:
            d = json.load(fh)
        if now - d["updated"] / 1000 > FRESH:
            return None
        out = {k: int(d[k]) for k in ("notesHave", "notesAll", "mediaHave", "mediaAll")}
        out["updated"] = int(d["updated"]) / 1000.0
        return out
    except (OSError, ValueError, KeyError, TypeError):
        return None


def phone_line(d, rate=0.0):
    """폰이 직접 센 값으로 만든 줄: 전체·글·그림 개수와 퍼센트(속도를 알면 남은 시간)"""
    have = d["notesHave"] + d["mediaHave"]
    total = d["notesAll"] + d["mediaAll"]

    def pct(a, b):
        return a * 100 // b if b else 100
    s = ("폰에 실제로 있는 파일: 전체 %s개 중 %s개 (%d%%)" + chr(10) + "글 %s / %s개 · 그림 %s / %s개") % (
        format(total, ","), format(have, ","), pct(have, total), format(d["notesHave"], ","), format(d["notesAll"], ","),
        format(d["mediaHave"], ","), format(d["mediaAll"], ","))
    if rate > 0 and total > have:
        sec = int((total - have) / rate)
        s += chr(10) + "초당 %.1f개 · 남은 시간 %s" % (rate, remaining(sec * rate, rate))   # 파일 수 기준
    return s


class CountRate:
    """합친 파일 개수(글+그림)가 늘어나는 속도(초당)와 글·그림 각각의 속도. 용량이 아니라 개수로 재는 이유: 큰 파일 몇 개가 지나가는 순간의 용량 속도(MB/초)는
    작은 파일 수만 개를 받는 실제 진행과 맞지 않았다. 최근 WINDOW 초의 표본(폰이 센 값은 2분마다 갱신)으로 재고, 단계 사이의 쉬는 시간도 평균에 들어간다."""
    WINDOW = 300
    MIN_SPAN = 60

    def __init__(self):
        self.samples = []   # (시각, 글, 그림)

    def update(self, t, notes, media):
        """표본을 더하고 (전체/초, 글/초, 그림/초)를 돌려준다. 아직 모르면 (0, 0, 0)"""
        if self.samples and self.samples[-1][0] == t:
            self.samples[-1] = (t, notes, media)
        else:
            if self.samples and (notes + media) < (self.samples[-1][1] + self.samples[-1][2]):
                self.samples = []   # 줄었다 = 폴더를 다시 훑는 중 등 → 다시 센다
            self.samples.append((t, notes, media))
        while len(self.samples) > 2 and t - self.samples[0][0] > self.WINDOW:
            self.samples.pop(0)
        t0, n0, m0 = self.samples[0]
        span = t - t0
        if span < self.MIN_SPAN:
            return 0.0, 0.0, 0.0
        return ((notes + media) - (n0 + m0)) / span, (notes - n0) / span, (media - m0) / span


def eta_text(left, rate):
    """남은 개수와 초당 개수 → 남은 시간 글자(속도를 모르면 '계산 중')"""
    if left <= 0:
        return "0분"
    if rate <= 0:
        return "계산 중"
    return remaining(left, rate)   # remaining(need, rate): need/rate 초


def phone_block(d, rates=(0.0, 0.0, 0.0), stage="", pp=None, bytes_rate=0.0):
    """폰 동기화 화면과 같은 문구의 진행 표시.
    전체 N / M개 (P%) · 글 a / b개 (p%) · 그림 c / d개 (p%) · 전체 M개 중 받음 N개 · 남음 K개 · 속도 · 남은 시간 · 지금 받는 범위 용량"""
    have = d["notesHave"] + d["mediaHave"]
    total = d["notesAll"] + d["mediaAll"]

    def pct(a, b):
        return a * 100 // b if b else 100
    nl = chr(10)
    s = stage
    s += "전체 %s / %s개 (%d%%)" % (format(have, ","), format(total, ","), pct(have, total)) + nl
    s += "글 %s / %s개 (%d%%) · 그림 %s / %s개 (%d%%)" % (
        format(d["notesHave"], ","), format(d["notesAll"], ","), pct(d["notesHave"], d["notesAll"]),
        format(d["mediaHave"], ","), format(d["mediaAll"], ","), pct(d["mediaHave"], d["mediaAll"])) + nl
    s += "전체 %s개 중 받음 %s개 · 남음 %s개" % (format(total, ","), format(have, ","), format(max(total - have, 0), ","))
    r, rn, rm = rates
    if total > have:
        s += nl + "속도 초당 %.1f개 (글 분당 %d개 · 그림 분당 %d개) · 남은 시간 %s" % (r, round(rn * 60), round(rm * 60), eta_text(total - have, r))
    if pp is not None:   # (전체 용량, 남은 용량): 지금 열린 범위의 용량. 속도(MB/초)는 참고용 — 큰 파일 몇 개에 크게 좌우된다
        tb, nb = pp
        if tb > 0 and nb > 0:
            s += nl + "지금 받는 범위 용량 %s / %s" % (size(max(tb - nb, 0)), size(tb))
            if bytes_rate > 0:
                s += " · 순간 속도 %s/초" % size(int(bytes_rate))
    return s
