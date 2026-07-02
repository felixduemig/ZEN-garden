"""Second pass: spaced en-dash ' -- ' used as a sentence dash -> comma.
Line-aware safeguards: skip comment lines, table rows ('&'), and section titles.
Range/placeholder '--' (no surrounding spaces, e.g. 12--15, & -- & cells, AT--IT) stays."""
import re, glob, os

SEC = r"C:\Users\felix\Documents\GitHub\ST_Final_Report_Felix_Duemig\thesis\Sections"
title = re.compile(r"\\(sub)*section\{")
dash = re.compile(r"(?<=\S) -- (?=\S)")   # spaced sentence dash

total = 0
for f in sorted(glob.glob(os.path.join(SEC, "*.tex"))):
    if os.path.basename(f).startswith("00_"):   # FrontPage / Outline handled manually
        continue
    out, n = [], 0
    for line in open(f, encoding="utf-8").read().splitlines(keepends=True):
        s = line.lstrip()
        if s.startswith("%") or "&" in line or title.search(line):
            out.append(line); continue
        new, k = dash.subn(", ", line)
        n += k; out.append(new)
    if n:
        open(f, "w", encoding="utf-8").write("".join(out))
        print(f"{os.path.basename(f)}: replaced {n}")
        total += n
print("TOTAL spaced en-dashes replaced:", total)
