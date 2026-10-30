"""방향별 동기화 정식 시험: PC(시험용 Syncthing) ↔ 안드로이드 에뮬레이터의 Syncthing-Fork.

사용자 노트 폴더에서 **무작위로 뽑은 복사본**(원본은 읽기만 한다)으로
시나리오 3개(양방향 / PC→모바일 / 모바일→PC) × 모듈 3개(노트 md · 미디어 · 외부 폴더 mp3/pdf)를 돌리고 파일 SHA-256 으로 비교한다.
출력에는 파일 이름·내용을 찍지 않는다(개수와 판정만). 임시 APPDATA 를 쓰므로 실제 설정은 건드리지 않는다.

준비: 에뮬레이터에 Syncthing-Fork 를 설치·실행하고 API 키를 알아 둔다. 내려받아 풀어 둔 syncthing.exe 의 위치를 --syncthing 으로 준다
(방화벽 창을 피하려면 같은 경로를 재사용한다).

예:  py -3 tools/sync_matrix.py --fork-key <API키> --vault <노트폴더> --adb <adb.exe> --syncthing <syncthing.exe>
환경 변수: SCN=양방향,PC→모바일 (일부 시나리오만), SMALL=1 (작은 표본), WAIT=150 (단계별 대기 초)
"""
import argparse, hashlib, json, os, random, shutil, ssl, subprocess, sys, tempfile, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser(description="방향별 동기화 시험(에뮬레이터)")
ap.add_argument("--fork-key", required=True, help="에뮬레이터 Syncthing-Fork 의 API 키")
ap.add_argument("--vault", required=True, help="표본을 뽑을 노트 폴더(읽기만 함)")
ap.add_argument("--adb", default="adb", help="adb 실행 파일")
ap.add_argument("--syncthing", required=True, help="syncthing.exe 경로")
ap.add_argument("--import-folder", help="mp3 표본을 뽑을 폴더(없으면 config.json 의 가져온 폴더 첫 번째)")
ap.add_argument("--out", default=os.path.join(HERE, "matrix_results.json"), help="결과 JSON 저장 위치")
ap.add_argument("--seed", type=int, default=20261030)
ARGS = ap.parse_args()
ADB = ARGS.adb
FORK_KEY = ARGS.fork_key
SRC_VAULT = ARGS.vault
random.seed(ARGS.seed)
tmp = tempfile.mkdtemp(prefix="matrix-")
_real_appdata = os.environ.get("APPDATA", "")
os.environ["APPDATA"] = os.path.join(tmp, "appdata")
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "app"))
import store as st, syncengine as se, syncpolicy as sp
SRC = ARGS.syncthing
se.exe_path = lambda: SRC
se.installed = lambda: True
PHONE_BASE = "/sdcard/Documents/syncmatrix"
PHONE_REAL = "/storage/emulated/0/Documents/syncmatrix"
BAD = set("'\"\\$`")

ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
subprocess.run([ADB, "forward", "tcp:18384", "tcp:8384"], capture_output=True)


def fork(path, method="GET", body=None):
    r = urllib.request.Request("https://127.0.0.1:18384" + path, method=method, headers={"X-API-Key": FORK_KEY, "Content-Type": "application/json"},
                               data=None if body is None else json.dumps(body).encode())
    with urllib.request.urlopen(r, timeout=30, context=ctx) as x:
        t = x.read().decode()
        return json.loads(t) if t.strip() else None


def adb(*args, check=False):
    r = subprocess.run([ADB, *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    return r.stdout


def sh(cmd):
    return adb("shell", cmd)


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# ------------------------------------------------------------------ 표본 뽑기(읽기 전용)
def ok_name(rel):
    return not (set(rel) & BAD) and len(rel) < 150


def pick_md(n):
    out = []
    for dp, dn, fn in os.walk(SRC_VAULT):
        dn[:] = [d for d in dn if not d.startswith(".") and d != "_resources"]
        for f in fn:
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, SRC_VAULT).replace("\\", "/")
            if f.lower().endswith(".md") and ok_name(rel):
                try:
                    if os.path.getsize(p) <= 500_000:
                        out.append((p, rel))
                except OSError:
                    pass
    random.shuffle(out)
    return out[:n]


def pick_media(n):
    out = []
    res = os.path.join(SRC_VAULT, ".resources")
    names = os.listdir(res)
    random.shuffle(names)
    for f in names:
        p = os.path.join(res, f)
        if os.path.isfile(p) and f.lower().rsplit(".", 1)[-1] in ("jpg", "png", "gif", "webp", "jpeg") and ok_name(f):
            try:
                if os.path.getsize(p) <= 5 * 2**20:
                    out.append((p, f))
            except OSError:
                pass
        if len(out) >= n:
            break
    return out


def pick_ext(ext, folder, n):
    out = []
    for dp, dn, fn in os.walk(folder):
        for f in fn:
            if f.lower().endswith("." + ext):
                p = os.path.join(dp, f)
                try:
                    if os.path.getsize(p) <= 12 * 2**20 and ok_name(f):
                        out.append((p, "x%d.%s" % (len(out), ext)))   # 이름은 안전한 이름으로 바꿔서 둔다
                except OSError:
                    pass
    random.shuffle(out)
    return [(p, "s%d_%d.%s" % (i, random.randint(0, 9999), ext)) for i, (p, _) in enumerate(out[:n])]


imp_folder = ARGS.import_folder
if not imp_folder:
    cfg = json.load(open(os.path.join(_real_appdata, "iamtalkernote", "config.json"), encoding="utf-8"))   # 읽기 전용(가져온 폴더 위치만 본다)
    imp_folder = cfg["imports"]["folders"][0]["path"]
POOL = {
    "md": pick_md(120 + 20),
    "media": pick_media(40),
    "mp3": pick_ext("mp3", imp_folder, 12),
    "pdf": pick_ext("pdf", os.path.join(SRC_VAULT, ".resources"), 12),
}
print("표본 풀:", {k: len(v) for k, v in POOL.items()}, flush=True)


# ------------------------------------------------------------------ 목록·조작
def pc_list(d, skip=()):
    out = {}
    for dp, dn, fn in os.walk(d):
        dn[:] = [x for x in dn if x not in (".stfolder", ".stversions") and os.path.relpath(os.path.join(dp, x), d).replace("\\", "/") not in skip]
        for f in fn:
            if f.startswith(".syncthing.") or f.endswith(".tmp") or f == ".stignore":
                continue
            p = os.path.join(dp, f)
            out[os.path.relpath(p, d).replace("\\", "/")] = sha(p)
    return out


def phone_list(d, skip=()):
    out = {}
    txt = sh("cd '%s' 2>/dev/null && find . -type f ! -path './.stfolder/*' ! -path './.stversions/*' -exec sha256sum {} +" % d)
    for line in txt.splitlines():
        if "  ./" not in line:
            continue
        h, rel = line.split("  ./", 1)
        rel = rel.strip()
        if rel.split("/")[0] in (".stfolder", ".stversions") or any(rel == s or rel.startswith(s + "/") for s in skip):
            continue
        if rel.rsplit("/", 1)[-1].startswith(".syncthing.") or rel.endswith(".tmp") or rel.endswith(".stignore"):
            continue
        out[rel] = h
    return out


def put_pc(base, items, prefix=""):
    names = {}
    for src, rel in items:
        dst = os.path.join(base, prefix + rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
        names[prefix + rel] = sha(dst)
    return names


def put_phone(base, items, prefix=""):
    names = {}
    stage = tempfile.mkdtemp(dir=tmp)
    for src, rel in items:
        dst = os.path.join(stage, prefix + rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
        names[prefix + rel] = sha(dst)
    # 폴더째 push 가 멈추는 일이 있어 파일을 하나씩 보낸다(폴더는 한 번에 만든다)
    dirs = sorted({os.path.dirname(base + "/" + k) for k in names} | {base})
    for i in range(0, len(dirs), 20):
        sh("mkdir -p " + " ".join("'%s'" % d for d in dirs[i:i + 20]))
    for k in names:
        adb("push", os.path.join(stage, *k.split("/")), base + "/" + k)
    return names


def phone_append(base, rel, text):
    sh("printf '%s' >> '%s/%s'" % (text, base, rel))


def phone_rm(base, rel):
    sh("rm -f '%s/%s'" % (base, rel))


def pc_append(base, rel, text):
    with open(os.path.join(base, rel), "ab") as f:
        f.write(text.encode())


# ------------------------------------------------------------------ 엔진 준비·연결
e = se.Engine()
results = []


def rec(scn, mod, desc, ok):
    results.append((scn, mod, desc, bool(ok)))
    print(("  ✔ " if ok else "  ✘ ") + f"[{scn}/{mod}] {desc}", flush=True)


def scan_all(ids):
    for i in ids:
        for fn in (lambda: e.api("/rest/db/scan?folder=" + i, "POST"), lambda: fork("/rest/db/scan?folder=" + i, "POST")):
            try:
                fn()
            except Exception:
                pass


def wait_until(pred, ids, timeout=150, every=3, label=""):
    t0 = time.time()
    end = t0 + timeout
    last = None
    while time.time() < end:
        scan_all(ids)
        time.sleep(every)
        print(f"   …{label} 대기 {int(time.time() - t0)}초", flush=True)
        try:
            last = pred()
        except Exception as ex:  # noqa: BLE001
            last = False
        if last:
            return True
    return False


try:
    assert e.start()
    e.api("/rest/config/options", "PATCH", {"listenAddresses": ["tcp://127.0.0.1:22001"], "globalAnnounceEnabled": False, "localAnnounceEnabled": False,
                                            "relaysEnabled": False, "natEnabled": False})
    pc_id = e.my_id()
    me = fork("/rest/system/status")["myID"]
    for d in fork("/rest/config")["devices"]:
        if d["deviceID"] != me:
            fork("/rest/config/devices/" + d["deviceID"], "DELETE")
    fork("/rest/config/devices/" + pc_id, "PUT", {"deviceID": pc_id, "name": "PC", "addresses": ["tcp://10.0.2.2:22001"], "autoAcceptFolders": False})
    for _ in range(60):
        if any(i == me for i, _ in e.pending_devices()):
            break
        time.sleep(1)
    e.add_peer(me, "내 폰")
    print("연결 준비: PC↔폰 기기 등록 완료", flush=True)

    only = os.environ.get("SCN")
    for scn, D in [x for x in (("양방향", sp.BOTH), ("PC→모바일", sp.PC2MOBILE), ("모바일→PC", sp.MOBILE2PC)) if not only or x[0] in only.split(",")]:
        tag = {"양방향": "both", "PC→모바일": "p2m", "모바일→PC": "m2p"}[scn]
        print(f"\n=== 시나리오: {scn} ===", flush=True)
        try:
            vault = os.path.join(tmp, "pc", tag, "vault")
            ext = os.path.join(tmp, "pc", tag, "ext")
            pvault = f"{PHONE_BASE}/{tag}/vault"
            pvault_real = f"{PHONE_REAL}/{tag}/vault"
            pext = pvault + "-files/자료"
            pext_real = pvault_real + "-files/자료"
            md, media, mp3, pdf = list(POOL["md"]), list(POOL["media"]), list(POOL["mp3"]), list(POOL["pdf"])
            random.shuffle(md); random.shuffle(media); random.shuffle(mp3); random.shuffle(pdf)
            # 모듈 정의: 이름, PC 경로, 폰 경로(셸용), 폰 실제 경로, 제외할 하위 경로, PC 원본 P, 폰 원본 Q, PC 새 N, 폰 새 M
            Z = dict(md=(100, 10, 3, 3), media=(20, 5, 2, 2), mp3=(3, 1, 0, 1), pdf=(2, 1, 1, 0))
            if os.environ.get("SMALL"):
                Z = dict(md=(8, 3, 1, 1), media=(3, 2, 1, 1), mp3=(2, 1, 0, 1), pdf=(1, 1, 1, 0))

            def cut(lst, a, b, c, d):
                return lst[:a], lst[a:a + b], lst[a + b:a + b + c], lst[a + b + c:a + b + c + d]
            mdP, mdQ, mdNP, mdNQ = cut(md, *Z["md"])
            meP, meQ, meNP, meNQ = cut(media, *Z["media"])
            m3P, m3Q, m3NP, m3NQ = cut(mp3, *Z["mp3"])
            pfP, pfQ, pfNP, pfNQ = cut(pdf, *Z["pdf"])
            S = {
                "노트": dict(pc=vault, ph=pvault, real=pvault_real, skip=(".resources", ".sync"), pfx_q="폰에서/", P=mdP, Q=mdQ, NP=mdNP, NQ=mdNQ),
                "미디어": dict(pc=os.path.join(vault, ".resources"), ph=pvault + "/.resources", real=pvault_real + "/.resources", skip=(), pfx_q="from_phone_",
                            P=meP, Q=meQ, NP=meNP, NQ=meNQ),
                "외부": dict(pc=ext, ph=pext, real=pext_real, skip=(), pfx_q="from_phone_", P=m3P + pfP, Q=m3Q + pfQ, NP=m3NP + pfNP, NQ=m3NQ + pfNQ),
            }
            for m, s in S.items():
                os.makedirs(s["pc"], exist_ok=True)
                s["p"] = put_pc(s["pc"], s["P"])
                s["q"] = put_phone(s["ph"], s["Q"], s["pfx_q"])
            print("  준비: " + ", ".join(f"{m} PC {len(s['p'])}·폰 {len(s['q'])}" for m, s in S.items()), flush=True)

            policy = sp.new_legacy_policy()   # 이 시험은 모듈마다 폴더·방향을 나눈 옛 방식을 확인한다
            for mid in ("imported", "history", "trash"):
                sp.set_direction(policy, mid, sp.OFF)
            sp.set_direction(policy, "markdown", D); sp.set_direction(policy, "media", D)
            sp.add_external(policy, "x1", "자료", D)
            sp.save(vault, policy)
            plans = sp.plan(policy, vault, "pc", {"x1": ext})
            mod2id = {p["module"]: p["id"] for p in plans}
            ids = list(mod2id.values())
            e.apply(plans)

            # 폰: 공유 요청 수락(경로 규칙은 폰 앱 ForkSync.localPath 와 같다) → 정책이 도착하면 방향 맞춤
            for _ in range(60):
                off = fork("/rest/cluster/pending/folders") or {}
                if all(i in off for i in ids):
                    break
                time.sleep(1)
            tmpl = fork("/rest/config/defaults/folder")
            for fid, info in (fork("/rest/cluster/pending/folders") or {}).items():
                label = next(iter(info["offeredBy"].values()))["label"]
                kind = fid.split("-")[2]
                path = {"mar": pvault_real, "med": pvault_real + "/.resources", "ext": pext_real}[kind]
                fo = dict(tmpl, id=fid, label=label, path=path, type="sendreceive", paused=False, devices=[{"deviceID": me}, {"deviceID": pc_id}])
                fork("/rest/config/folders/" + fid, "PUT", fo)
            reconciled = {"v": False}

            def reconcile():
                txt = sh("cat '%s/.sync/policy.json' 2>/dev/null" % pvault)
                if reconciled["v"] or not txt.strip().startswith("{"):
                    return
                pol = json.loads(txt)
                have = {f["id"]: f for f in fork("/rest/config")["folders"]}
                for mid, m in pol["modules"].items():
                    want = {"both": "sendreceive", "pc2mobile": "receiveonly", "mobile2pc": "sendonly"}.get(m["direction"])
                    fo = have.get(sp.folder_id(pol, mid))
                    if want and fo and fo["type"] != want:
                        fo["type"] = want
                        fork("/rest/config/folders/" + fo["id"], "PUT", fo)
                reconciled["v"] = True

            def snap(m):
                s = S[m]
                return pc_list(s["pc"], s["skip"]), phone_list(s["ph"], s["skip"])

            # ---- 1단계: 처음 맞추기
            def phaseA_ok():
                reconcile()
                for m, s in S.items():
                    pcl, phl = snap(m)
                    if D == sp.BOTH:
                        if not (pcl == phl and len(pcl) == len(s["p"]) + len(s["q"])):
                            return False
                    elif D == sp.PC2MOBILE:
                        if not all(phl.get(k) == v for k, v in s["p"].items()):
                            return False
                    else:
                        if not all(pcl.get(k) == v for k, v in s["q"].items()):
                            return False
                return True
            okA = wait_until(phaseA_ok, ids, timeout=int(os.environ.get("WAIT", "150")), label="1단계")
            time.sleep(8)
            for m, s in S.items():
                pcl, phl = snap(m)
                P, Q = s["p"], s["q"]
                if D == sp.BOTH:
                    rec(scn, m, f"처음 맞춤: 양쪽이 같고 합집합({len(P)}+{len(Q)}={len(pcl)}개)", pcl == phl and len(pcl) == len(P) + len(Q))
                elif D == sp.PC2MOBILE:
                    rec(scn, m, f"PC 파일 {len(P)}개가 폰에 해시까지 같게 도착", all(phl.get(k) == v for k, v in P.items()))
                    rec(scn, m, "폰이 미리 가진 파일 %d개는 PC 로 올라가지 않음" % len(Q), not any(k in pcl for k in Q))
                else:
                    rec(scn, m, f"폰 파일 {len(Q)}개가 PC 에 해시까지 같게 도착", all(pcl.get(k) == v for k, v in Q.items()))
                    rec(scn, m, "PC 가 미리 가진 파일 %d개는 폰으로 내려가지 않음" % len(P), not any(k in phl for k in P))

            # ---- 2단계: 양쪽에서 수정·삭제·새 파일
            B = {}
            for m, s in S.items():
                ps = sorted(s["p"]); qs = sorted(s["q"])
                p1, p2, p3 = ps[0], ps[1], ps[2]
                q1, q2 = qs[0], qs[1]
                pc_append(s["pc"], p1, "\nEDIT-PC")                      # PC 가 PC 파일 수정
                os.remove(os.path.join(s["pc"], p2))                      # PC 가 PC 파일 삭제
                newp = put_pc(s["pc"], s["NP"], "pc_new_")                # PC 새 파일
                phone_append(s["ph"], q1, "\\nEDIT-PH")                  # 폰이 폰 파일 수정
                phone_rm(s["ph"], q2)                                     # 폰이 폰 파일 삭제
                newq = put_phone(s["ph"], s["NQ"], "ph_new_")            # 폰 새 파일
                if D != sp.MOBILE2PC:
                    phone_append(s["ph"], p3, "\\nEDIT-PH")              # 폰이 PC 에서 받은 파일을 수정
                B[m] = dict(p1=p1, p2=p2, p3=p3, q1=q1, q2=q2, newp=newp, newq=newq)
            time.sleep(4)

            def phaseB_ok():
                for m, s in S.items():
                    b = B[m]; pcl, phl = snap(m)
                    if D == sp.BOTH:
                        if pcl != phl or b["p2"] in pcl or b["q2"] in pcl or not all(k in pcl for k in list(b["newp"]) + list(b["newq"])):
                            return False
                        if pcl.get(b["p3"]) == s["p"][b["p3"]]:
                            return False
                    elif D == sp.PC2MOBILE:
                        if b["p2"] in phl or not all(k in phl for k in b["newp"]) or phl.get(b["p1"]) != pcl.get(b["p1"]):
                            return False
                    else:
                        if b["q2"] in pcl or not all(k in pcl for k in b["newq"]) or pcl.get(b["q1"]) != phl.get(b["q1"]):
                            return False
                return True
            okB = wait_until(phaseB_ok, ids, timeout=int(os.environ.get("WAIT", "150")), label="2단계")
            time.sleep(10)
            for m, s in S.items():
                b = B[m]; pcl, phl = snap(m); P, Q = s["p"], s["q"]
                if D == sp.BOTH:
                    rec(scn, m, "수정·삭제·새 파일이 양쪽에서 서로 전달되어 PC 와 폰이 완전히 같음", pcl == phl)
                    rec(scn, m, "폰이 고친 'PC 파일'이 PC 에 반영됨", pcl.get(b["p3"]) != P[b["p3"]] and pcl.get(b["p3"]) == phl.get(b["p3"]))
                    rec(scn, m, "PC 삭제가 폰에, 폰 삭제가 PC 에 반영됨", b["p2"] not in phl and b["q2"] not in pcl)
                elif D == sp.PC2MOBILE:
                    rec(scn, m, "PC 의 수정·삭제·새 파일이 폰에 전달됨", phl.get(b["p1"]) == pcl.get(b["p1"]) and b["p2"] not in phl and all(k in phl for k in b["newp"]))
                    rec(scn, m, "폰의 새 파일·수정·삭제는 PC 에 전달되지 않음", not any(k in pcl for k in list(b["newq"]) + list(s["q"])))
                    rec(scn, m, "폰이 고친 'PC 파일'이 PC 를 바꾸지 않음", pcl.get(b["p3"]) == P[b["p3"]])
                else:
                    rec(scn, m, "폰의 수정·삭제·새 파일이 PC 에 전달됨", pcl.get(b["q1"]) == phl.get(b["q1"]) and b["q2"] not in pcl and all(k in pcl for k in b["newq"]))
                    rec(scn, m, "PC 의 새 파일·수정·삭제는 폰에 전달되지 않음", not any(k in phl for k in list(b["newp"]) + list(P)))
        except Exception as ex:  # noqa: BLE001
            rec(scn, "시나리오", f"실행 중 오류: {type(ex).__name__} {str(ex)[:120]}", False)
        finally:
            # 시나리오 정리: 양쪽 폴더 설정 제거
            try:
                e.apply([])
            except Exception:
                pass
            try:
                for f in fork("/rest/config")["folders"]:
                    fork("/rest/config/folders/" + f["id"], "DELETE")
            except Exception:
                pass
            sh("rm -rf '%s/%s' '%s/%s/vault-files'" % (PHONE_BASE, tag, PHONE_BASE, tag))
finally:
    summary = {}
    for scn, mod, desc, ok in results:
        summary.setdefault(scn, [0, 0])[0 if ok else 1] += 1
    print("\n=== 요약 (통과/실패) ===")
    for k, (a, b) in summary.items():
        print(f"{k}: {a}/{a + b}")
    json.dump(results, open(ARGS.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    try:
        e.stop()
    except Exception:
        pass
    try:
        me2 = fork("/rest/system/status")["myID"]
        for d in fork("/rest/config")["devices"]:
            if d["deviceID"] != me2:
                fork("/rest/config/devices/" + d["deviceID"], "DELETE")
    except Exception:
        pass
    sh("rm -rf '%s'" % PHONE_BASE)
    time.sleep(1)
    shutil.rmtree(tmp, ignore_errors=True)
