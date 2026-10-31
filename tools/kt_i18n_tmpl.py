"""코틀린 문자열 템플릿("…${x}…", "…$x…")을 trf("…%s…", x) 로 바꾼다(한글이 든 것만, 데이터성 줄 제외). 키 목록을 json 으로 저장."""
import io, json, os, re, sys

D = r"C:\MyData\claude program\1. 개발중\iamtalkernote-android\app\src\main\java\kr\iamtalker\notes" + "\\"
SKIP_FILES = {"AppThemes.kt", "Holidays.kt", "HashTags.kt", "Meta.kt", "NoteText.kt", "Markdown.kt", "HelpText.kt", "Lang.kt", "I18nEn.kt", "EmbeddedSync.kt", "CrashLog.kt", "Planner.kt", "Query.kt"}
SKIP_SUB = ["Regex(", "detail =", "Log.", "journal(", "SimpleDateFormat(", "(충돌 ", "(복원", "제목 없음", "substringAfter(", "note(ctx", "EmbeddedSync.note", "putDevice", "tr(\"", "trf(\""]
H = re.compile(r"[가-힣]")
keys = {}


def parse_literal(line, i):
    """line[i] == '"' 에서 시작하는 문자열 리터럴을 파싱 → (끝 인덱스, 템플릿 문자열, 인자 목록) 또는 None"""
    j = i + 1
    tmpl, args = [], []
    while j < len(line):
        c = line[j]
        if c == "\\" and j + 1 < len(line):
            tmpl.append(line[j:j + 2])
            j += 2
        elif c == '"':
            return j + 1, "".join(tmpl), args
        elif c == "$" and j + 1 < len(line) and line[j + 1] == "{":
            depth, k = 1, j + 2
            while k < len(line) and depth:
                if line[k] == "{":
                    depth += 1
                elif line[k] == "}":
                    depth -= 1
                elif line[k] == '"':      # 식 안의 문자열: 건너뛴다
                    k += 1
                    while k < len(line) and line[k] != '"':
                        k += 2 if line[k] == "\\" else 1
                k += 1
            expr = line[j + 2:k - 1]
            if H.search(expr):
                return None
            args.append(expr)
            tmpl.append("%s")
            j = k
        elif c == "$" and j + 1 < len(line) and (line[j + 1].isalpha() or line[j + 1] == "_"):
            k = j + 1
            while k < len(line) and (line[k].isalnum() or line[k] == "_"):
                k += 1
            args.append(line[j + 1:k])
            tmpl.append("%s")
            j = k
        elif c == "%":
            tmpl.append("%%")
            j += 1
        else:
            tmpl.append(c)
            j += 1
    return None


for f in sorted(os.listdir(D)):
    if not f.endswith(".kt") or f in SKIP_FILES:
        continue
    lines = io.open(D + f, encoding="utf-8", newline="").read().split("\n")
    changed = False
    for n, ln in enumerate(lines):
        s = ln.strip()
        if s.startswith("//") or s.startswith("*") or s.startswith("/*") or '"""' in ln or any(x in ln for x in SKIP_SUB) or "$" not in ln or not H.search(ln):
            continue
        out, i = [], 0
        while i < len(ln):
            if ln[i] == '"':
                r = parse_literal(ln, i)
                if r is None:
                    out.append(ln[i])
                    i += 1
                    continue
                end, tmpl, args = r
                lit = ln[i:end]
                if H.search(tmpl) and args:
                    keys[tmpl] = f
                    out.append('trf("' + tmpl + '", ' + ", ".join(args) + ")")
                else:
                    out.append(lit)
                i = end
            else:
                out.append(ln[i])
                i += 1
        new = "".join(out)
        if new != ln:
            lines[n] = new
            changed = True
    if changed:
        io.open(D + f, "w", encoding="utf-8", newline="").write("\n".join(lines))
io.open(sys.argv[1], "w", encoding="utf-8").write(json.dumps(keys, ensure_ascii=False, indent=0))
print(len(keys), "templates")
