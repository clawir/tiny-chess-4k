import json, os, urllib.request as U

E = os.environ["MAKEFUN_ENV_URL"]
KN = (18, 33, 31, 14, -14, -31, -33, -18)
KG = (1, -1, 16, -16, 17, 15, -17, -15)
DG = (17, 15, -17, -15)
OG = (1, -1, 16, -16)
VAL = {"p": 100, "n": 320, "b": 330, "r": 500, "q": 900, "k": 0}
CAP = 90000
N = [0]


class Stop(Exception):
    pass


def post(p, b):
    r = U.Request(E + p, json.dumps(b).encode(), {"content-type": "application/json"})
    return json.load(U.urlopen(r))


def parse(fen):
    b = [0] * 128
    f = fen.split()
    for i, row in enumerate(f[0].split("/")):
        x = 0
        for c in row:
            if c.isdigit():
                x += int(c)
            else:
                b[(7 - i) * 16 + x] = c
                x += 1
    ep = -1
    if len(f) > 3 and f[3] != "-":
        ep = (int(f[3][1]) - 1) * 16 + "abcdefgh".index(f[3][0])
    return b, f[1] == "w", ep


def atk(b, s, u):
    for o in ((-15, -17) if u else (15, 17)):
        q = s + o
        if not q & 0x88:
            p = b[q]
            if p and p.isupper() == u and p.lower() == "p":
                return 1
    for o in KN:
        q = s + o
        if not q & 0x88:
            p = b[q]
            if p and p.isupper() == u and p.lower() == "n":
                return 1
    for o in KG:
        q = s + o
        if not q & 0x88:
            p = b[q]
            if p and p.isupper() == u and p.lower() == "k":
                return 1
    for ds, ts in ((DG, "bq"), (OG, "rq")):
        for o in ds:
            q = s + o
            while not q & 0x88:
                p = b[q]
                if p:
                    if p.isupper() == u and p.lower() in ts:
                        return 1
                    break
                q += o
    return 0


def gen(b, u, ep):
    M = []
    for s in range(128):
        if s & 0x88:
            continue
        p = b[s]
        if not p or p.isupper() != u:
            continue
        t = p.lower()
        if t == "p":
            d = 16 if u else -16
            q = s + d
            if not q & 0x88 and not b[q]:
                if q >> 4 in (0, 7):
                    M += [s | q << 8 | i << 16 for i in (2, 3, 4, 5)]
                else:
                    M.append(s | q << 8)
                q2 = s + 2 * d
                if s >> 4 in (1, 6) and not b[q2]:
                    M.append(s | q2 << 8)
            for o in (d - 1, d + 1):
                q = s + o
                if q & 0x88:
                    continue
                v = b[q]
                if v and v.isupper() != u:
                    if q >> 4 in (0, 7):
                        M += [s | q << 8 | i << 16 for i in (2, 3, 4, 5)]
                    else:
                        M.append(s | q << 8)
                elif q == ep:
                    M.append(s | q << 8 | 1 << 20)
        elif t in "nk":
            for o in (KN if t == "n" else KG):
                q = s + o
                if q & 0x88:
                    continue
                v = b[q]
                if not v or v.isupper() != u:
                    M.append(s | q << 8)
        else:
            for dd in ((DG, OG) if t == "q" else ((DG,) if t == "b" else (OG,))):
                for o in dd:
                    q = s + o
                    while not q & 0x88:
                        v = b[q]
                        if v:
                            if v.isupper() != u:
                                M.append(s | q << 8)
                            break
                        M.append(s | q << 8)
                        q += o
    return M


def mv(b, m):
    f = m & 255
    t = (m >> 8) & 255
    pr = (m >> 16) & 7
    p = b[f]
    cs = t - 16 if p.isupper() else t + 16
    cap = b[t]
    if (m >> 20) & 1:
        cap = b[cs]
        b[cs] = 0
    b[t] = p if not pr else ("NBRQ" if p.isupper() else "nbrq")[pr - 2]
    b[f] = 0
    return f, cap, cs, p


def um(b, m, u):
    f, cap, cs, p = u
    b[f] = p
    b[(m >> 8) & 255] = 0 if (m >> 20) & 1 else cap
    if (m >> 20) & 1:
        b[cs] = cap


def ok(b, m, u):
    w = mv(b, m)
    good = not atk(b, b.index("K" if u else "k"), not u)
    um(b, m, w)
    return good


def ev(b):
    s = 0
    for i in range(128):
        if i & 0x88:
            continue
        p = b[i]
        if not p:
            continue
        t = p.lower()
        u = p.isupper()
        r = i >> 4
        x = (r * 8 + (i & 7)) if u else ((7 - r) * 8 + (i & 7))
        v = VAL[t] + PST[PI[t] * 64 + x]
        s += v if u else -v
    return s


def order(M, b, kill):
    def k(m):
        c = b[(m >> 8) & 255]
        if c:
            return -(VAL[c.lower()] * 16 - VAL[b[m & 255].lower()])
        return 0 if m == kill else 1
    M.sort(key=k)
    return M


def qs(b, u, ep, a, bt):
    N[0] += 1
    if N[0] > CAP:
        raise Stop
    s = ev(b) if u else -ev(b)
    if s >= bt:
        return s
    if s > a:
        a = s
    for m in order([m for m in gen(b, u, ep) if b[(m >> 8) & 255] or (m >> 16) & 7 or (m >> 20) & 1], b, -1):
        if not ok(b, m, u):
            continue
        w = mv(b, m)
        x = -qs(b, not u, -1, -bt, -a)
        um(b, m, w)
        if x >= bt:
            return x
        if x > a:
            a = x
    return a


def ab(b, u, ep, d, a, bt):
    N[0] += 1
    if N[0] > CAP:
        raise Stop
    if d < 1:
        return qs(b, u, ep, a, bt)
    best = -99999
    live = 0
    for m in order(gen(b, u, ep), b, KILL[0]):
        if not ok(b, m, u):
            continue
        live = 1
        f = m & 255
        t = (m >> 8) & 255
        w = mv(b, m)
        ne = (f + t) >> 1 if abs(t - f) == 32 and not (m >> 16) & 7 else -1
        x = -ab(b, not u, ne, d - 1, -bt, -a)
        um(b, m, w)
        if x > best:
            best = x
            if x > a:
                a = x
                if a >= bt:
                    KILL[0] = m
                    break
    if not live:
        return -29000 - d * 40 if atk(b, b.index("K" if u else "k"), not u) else 0
    return best


def uci(m):
    s = "abcdefgh"
    f = m & 255
    t = (m >> 8) & 255
    r = s[f & 7] + str((f >> 4) + 1) + s[t & 7] + str((t >> 4) + 1)
    return r + ("nbrq"[(m >> 16) - 2] if (m >> 16) & 7 else "")


PST = [ord(c) - 60 for c in "<<<<<<<<DDGJJGDDLLORROLLTTWZZWTT]]_bb_]]ddgjjgddllorrollssssssss06<BB<606<BHHB<6<BHNNHB<BHNTTNHBBHNTTNHB<BHNNHB<6<BHHB<606<BB<606:>BB>:6:>BFFB>:>BFJJFB>BFJNNJFBBFJNNJFB>BFJJFB>:>BFFB>:6:>BB>:6666<<666@@@FF@@@DDDJJDDDHHHNNHHHLLLRRLLLPPPVVPPPTTTZZTTTXXX^^XXX79<>><979<>@@><9<>@CC@><>@CEEC@>>@CEEC@><>@CC@><9<>@@><979<>><97<963369<96300369630--03630-**-0330-**-03630--03696300369<963369<"]
PI = {c: i for i, c in enumerate("pnbrqk")}
KILL = [-1]

while 1:
    g = post("/game", {})
    if g["status"] == "done":
        break
    while g["status"] == "your_move":
        b, u, ep = parse(g["fen"])
        best = None
        moves = g["legal_moves"]
        N[0] = 0
        KILL[0] = -1
        for d in range(1, 9):
            try:
                bst = None
                a = -99999
                for m in order(gen(b, u, ep), b, KILL[0]):
                    if not ok(b, m, u):
                        continue
                    w = mv(b, m)
                    x = -ab(b, not u, -1, d - 1, -99999, -a)
                    um(b, m, w)
                    if x > a:
                        a = x
                        bst = m
                if bst is not None:
                    best = bst
            except Stop:
                break
        if best is None or uci(best) not in moves:
            best = None
            for m in gen(b, u, ep):
                if ok(b, m, u) and uci(m) in moves:
                    best = m
                    break
        pick = uci(best) if best is not None else moves[0]
        g = post("/move", {"game": g["game"], "move": pick})
